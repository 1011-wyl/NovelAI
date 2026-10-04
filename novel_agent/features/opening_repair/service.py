from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from novel_agent.features.chapter_planning.anchors import resolve_opening_anchor
from novel_agent.features.opening_repair.errors import OpeningRepairError
from novel_agent.features.opening_repair.models import (
    OpeningRepairApplyRequest,
    OpeningRepairApplyResult,
    OpeningRepairPreview,
)
from novel_agent.features.story_design.character_seed import seed_payloads_from_brief
from novel_agent.features.story_design.models import CharacterProfile, CreativeBrief
from novel_agent.infrastructure.persistence.json_util import dump_json
from novel_agent.infrastructure.persistence.opening_repair_store import (
    OpeningRepairStoreError,
    SQLiteOpeningRepairStore,
)
from novel_agent.models import ChapterStatus, ProjectStatus, new_id, utc_now

_FORMAL = {
    ChapterStatus.READY.value,
    ChapterStatus.SCHEDULED.value,
    ChapterStatus.PUBLISHED.value,
}
_FUTURE_HINTS = ("后来", "最终", "被救后", "成为", "效忠", "掌控者", "代理人")


def eligibility_reasons(project: Any, chapters: list[Any]) -> list[str]:
    reasons: list[str] = []
    if int(getattr(project, "current_chapter", 0) or 0) != 0:
        reasons.append("项目进度已超过第 0 章，不能使用自动开篇修复")
    if not bool(getattr(project, "confirmed", False)):
        reasons.append("创作方案尚未确认")
    if getattr(project, "status", None) == ProjectStatus.ARCHIVED:
        reasons.append("归档项目不能自动修复开篇")
    statuses = []
    for chapter in chapters:
        status = chapter.status.value if hasattr(chapter.status, "value") else str(chapter.status)
        number = int(chapter.number)
        statuses.append((number, status))
        if status in _FORMAL:
            reasons.append("项目已有正式章节，不能使用自动开篇修复")
            break
    chapter_one = next((item for item in statuses if item[0] == 1), None)
    if chapter_one is None:
        reasons.append("找不到第 1 章")
    elif chapter_one[1] not in {ChapterStatus.FAILED.value, ChapterStatus.PLANNED.value}:
        reasons.append("第 1 章必须是未通过审核或待规划状态")
    return list(dict.fromkeys(reasons))


def repair_brief_for_opening(brief: CreativeBrief) -> CreativeBrief:
    profiles: list[CharacterProfile] = []
    for profile in brief.character_profiles:
        future_rel = dict(profile.future_relationships)
        future_arc = profile.future_arc
        for name, relation in (profile.relationships or {}).items():
            if any(hint in relation for hint in _FUTURE_HINTS):
                future_rel.setdefault(name, relation)
        if not future_arc and profile.profile and any(hint in profile.profile for hint in _FUTURE_HINTS):
            future_arc = profile.profile
        profiles.append(
            profile.model_copy(
                update={
                    "future_relationships": future_rel,
                    "future_arc": future_arc,
                }
            )
        )
    payload = brief.model_dump(mode="json")
    payload["character_profiles"] = [item.model_dump(mode="json") for item in profiles]
    return CreativeBrief.model_validate(payload)


@dataclass(slots=True)
class OpeningRepairService:
    repository: Any
    store: SQLiteOpeningRepairStore

    def preview(self, project_id: str) -> OpeningRepairPreview:
        project = self.repository.get_project(project_id)
        chapters = self.repository.list_chapters(project_id)
        reasons = eligibility_reasons(project, chapters)
        repaired = repair_brief_for_opening(project.brief)
        anchor = resolve_opening_anchor(repaired, 1)
        chapter_one = next((item for item in chapters if item.number == 1), None)
        characters = self.repository.list_characters(project_id)
        proposed = seed_payloads_from_brief(project.request, repaired)
        proposed_by_name = {profile.name: state for profile, _facts, state in proposed}
        character_changes: list[dict[str, Any]] = []
        for character in characters:
            current_rels = (character.current_state or {}).get("relationships") or {}
            next_state = proposed_by_name.get(character.name) or {}
            next_rels = next_state.get("relationships") or {}
            if current_rels != next_rels:
                character_changes.append(
                    {
                        "name": character.name,
                        "from_relationships": current_rels,
                        "to_relationships": next_rels,
                        "moved_to_future": True,
                    }
                )
        problems: list[str] = []
        if chapter_one and chapter_one.plan is not None and anchor is not None:
            if anchor.title and anchor.title not in (chapter_one.title or ""):
                problems.append("第一章标题未绑定第一条开篇锚点")
            if anchor.core_event and chapter_one.plan.objective:
                if anchor.core_event[:12] not in chapter_one.plan.objective and chapter_one.plan.title != anchor.title:
                    problems.append("第一章细纲可能错用了相邻开篇情节")
        for character in characters:
            rels = (character.current_state or {}).get("relationships") or {}
            if any(any(hint in str(value) for hint in _FUTURE_HINTS) for value in rels.values()):
                problems.append(f"{character.name} 的当前关系混入了尚未发生的未来结果")
        return OpeningRepairPreview(
            eligible=not reasons,
            reasons=reasons,
            project_updated_at=project.updated_at,
            detected_problems=list(dict.fromkeys(problems)),
            opening_anchor=anchor.model_dump(mode="json") if anchor else {},
            character_changes=character_changes,
            chapter_changes=[
                {
                    "chapter_number": 1,
                    "from_status": chapter_one.status.value if chapter_one else None,
                    "to_status": ChapterStatus.PLANNED.value,
                    "from_title": chapter_one.title if chapter_one else None,
                    "to_title": anchor.title if anchor else "",
                }
            ],
            preserved_artifacts=[
                "旧失败正文与细纲会写入修复快照",
                "审校报告与运行记录会写入修复快照",
                "错误第一章研究资料会写入快照并在修复后清理",
                "可在没有新正式章节前回退",
            ],
        )

    def latest_snapshot(self, project_id: str) -> dict[str, Any]:
        project = self.repository.get_project(project_id)
        chapters = self.repository.list_chapters(project_id)
        row = self.store.get_latest_applied_snapshot(project_id)
        if row is None:
            return {"snapshot": None}
        formal = any(
            (item.status.value if hasattr(item.status, "value") else str(item.status)) in _FORMAL
            for item in chapters
        ) or int(project.current_chapter or 0) > 0
        return {
            "snapshot": {
                "id": row["id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "applied_at": row["applied_at"],
                "rollback_allowed": not formal,
                "blocked_reason": (
                    "修复后已产生正式章节，不能安全回退" if formal else None
                ),
            }
        }

    def apply(self, project_id: str, request: OpeningRepairApplyRequest) -> OpeningRepairApplyResult:
        if not request.confirm:
            raise OpeningRepairError("必须明确确认后才能修复开篇数据", code="OPENING_REPAIR_NOT_ELIGIBLE")
        preview = self.preview(project_id)
        if not preview.eligible:
            raise OpeningRepairError(
                "当前项目不符合自动开篇修复条件",
                code="OPENING_REPAIR_NOT_ELIGIBLE",
                details=preview.reasons,
            )
        if request.expected_project_updated_at != preview.project_updated_at:
            raise OpeningRepairError(
                "预览已过期，请重新检查开篇数据后再确认",
                code="OPENING_REPAIR_PREVIEW_STALE",
                details={"expected": request.expected_project_updated_at, "actual": preview.project_updated_at},
            )
        snapshot_id = self._apply_transaction(project_id)
        return OpeningRepairApplyResult(
            snapshot_id=snapshot_id,
            next_action="开篇数据已修复，可重新生成第 1 章",
            preview=self.preview(project_id),
        )

    def rollback(self, project_id: str, snapshot_id: str) -> dict[str, Any]:
        snapshot = self.store.get_snapshot(snapshot_id)
        if snapshot is None or snapshot["project_id"] != project_id:
            raise OpeningRepairError("找不到该修复快照", code="OPENING_REPAIR_NOT_ELIGIBLE")
        if snapshot["status"] == "rolled_back":
            raise OpeningRepairError("该快照已经回退过", code="OPENING_REPAIR_ROLLBACK_UNSAFE")
        project = self.repository.get_project(project_id)
        chapters = self.repository.list_chapters(project_id)
        if any(
            (item.status.value if hasattr(item.status, "value") else str(item.status)) in _FORMAL
            for item in chapters
        ) or project.current_chapter > 0:
            raise OpeningRepairError(
                "修复后已产生正式章节，不能安全回退",
                code="OPENING_REPAIR_ROLLBACK_UNSAFE",
            )
        with self.repository.transaction() as conn:
            try:
                self.store.restore_payload(conn, project_id, snapshot["payload"])
                self.store.mark_rolled_back(conn, snapshot_id)
            except OpeningRepairStoreError as exc:
                raise OpeningRepairError(str(exc), code="OPENING_REPAIR_ROLLBACK_UNSAFE") from exc
        return {"rolled_back": True, "snapshot_id": snapshot_id}

    def _apply_transaction(self, project_id: str) -> str:
        now = utc_now()
        with self.repository.transaction() as conn:
            payload = self.store.capture_snapshot(conn, project_id)
            snapshot_id = self.store.insert_snapshot(
                conn, project_id=project_id, payload=payload, status="applied"
            )
            chapter_ids = [str(item["id"]) for item in payload.get("chapters") or []]
            self.store.delete_polluted_opening_research(conn, project_id, chapter_ids)
            project_row = conn.execute(
                "SELECT * FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if project_row is None:
                raise OpeningRepairError("找不到小说项目")
            brief = repair_brief_for_opening(
                CreativeBrief.model_validate_json(project_row["brief_json"])
            )
            from novel_agent.features.story_design.models import NovelCreateRequest

            request = NovelCreateRequest.model_validate_json(project_row["request_json"])
            next_version = self.repository.briefs.next_version(conn, project_id)
            self.repository.projects.update_title_and_brief(
                conn,
                project_id,
                title=brief.selected_title,
                brief=brief,
                updated_at=now,
            )
            self.repository.briefs.insert_brief_version(
                conn,
                project_id=project_id,
                version=next_version,
                brief=brief,
                source="opening_repair",
                feedback="显式开篇数据修复",
                created_at=now,
            )
            conn.execute("DELETE FROM characters WHERE project_id=?", (project_id,))
            for profile, facts, state in seed_payloads_from_brief(request, brief):
                is_protagonist = profile.name == brief.protagonist_name
                conn.execute(
                    """INSERT INTO characters
                    (id,project_id,name,role,immutable_facts_json,current_state_json,version)
                    VALUES (?,?,?,?,?,?,1)""",
                    (
                        new_id("character"),
                        project_id,
                        profile.name,
                        "protagonist" if is_protagonist else profile.role,
                        dump_json(facts),
                        dump_json(state),
                    ),
                )
            chapter = conn.execute(
                "SELECT * FROM chapters WHERE project_id=? AND number=1",
                (project_id,),
            ).fetchone()
            if chapter is not None:
                next_row = conn.execute(
                    """SELECT COALESCE(MAX(version),0)+1 AS next_version
                    FROM chapter_versions WHERE chapter_id=?""",
                    (chapter["id"],),
                ).fetchone()
                version = int(next_row["next_version"]) if next_row else 1
                conn.execute(
                    """INSERT INTO chapter_versions
                    (chapter_id,version,kind,content,metadata_json,created_at,title,source,is_official)
                    VALUES (?,?,?,?,?,?,?,?,0)""",
                    (
                        chapter["id"],
                        version,
                        "FAILED_PRE_REPAIR",
                        chapter["content"] or "",
                        dump_json({"plan": chapter["plan_json"], "status": chapter["status"]}),
                        now,
                        chapter["title"],
                        "opening_repair",
                    ),
                )
                conn.execute(
                    """UPDATE chapters SET status=?, content=NULL, summary=NULL, plan_json=NULL,
                    title=?, version=?, locked=0, updated_at=? WHERE id=?""",
                    (
                        ChapterStatus.PLANNED.value,
                        "第1章 待重新规划",
                        int(chapter["version"]) + 1,
                        now,
                        chapter["id"],
                    ),
                )
                conn.execute(
                    "DELETE FROM timeline_events WHERE project_id=? AND chapter_number=1",
                    (project_id,),
                )
            conn.execute("DELETE FROM world_facts WHERE project_id=?", (project_id,))
            for statement in brief.world_rules:
                conn.execute(
                    """INSERT INTO world_facts
                    (id,project_id,category,statement,evidence_chapter,version,locked)
                    VALUES (?,?,?,?,NULL,1,1)""",
                    (new_id("fact"), project_id, "hard_rule", statement),
                )
        return snapshot_id
