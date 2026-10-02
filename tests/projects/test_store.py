from __future__ import annotations

import ast
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import (
    CharacterRecord,
    CreativeBrief,
    NovelCreateRequest,
    ProjectRecord,
    ProjectStatus,
    WorldFactRecord,
    new_id,
    utc_now,
)
from novel_agent.repository import RepositoryError, SQLiteRepository
from novel_agent.service import NovelAgentService


REPO_PATH = Path(__file__).resolve().parents[2] / "novel_agent" / "repository.py"


class ProjectsStoreCharacterizationTests(unittest.TestCase):
    """Freeze Repository project/brief contracts and atomic setup transactions."""

    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.repository = SQLiteRepository(Path(self.folder.name) / "projects.db")

    def tearDown(self) -> None:
        self.folder.cleanup()

    def test_repository_project_method_signatures(self) -> None:
        expected = {
            "create_project": ("project", "characters", "world_facts"),
            "list_projects": (),
            "get_project": ("project_id",),
            "update_project_status": ("project_id", "status"),
            "confirm_project": ("project_id",),
            "save_draft_brief": ("project_id", "brief", "source", "feedback"),
            "list_brief_versions": ("project_id",),
            "get_brief_version": ("project_id", "version"),
            "delete_project": ("project_id", "force"),
        }
        for name, params in expected.items():
            signature = inspect.signature(getattr(SQLiteRepository, name))
            self.assertEqual(tuple(signature.parameters)[1:], params, name)

    def test_repository_facade_no_longer_embeds_project_brief_crud_sql(self) -> None:
        tree = ast.parse(REPO_PATH.read_text(encoding="utf-8"))
        methods = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "SQLiteRepository"
            for node in node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for name in (
            "create_project",
            "list_projects",
            "get_project",
            "update_project_status",
            "confirm_project",
            "save_draft_brief",
            "list_brief_versions",
            "get_brief_version",
            "delete_project",
        ):
            source = ast.get_source_segment(REPO_PATH.read_text(encoding="utf-8"), methods[name])
            assert source is not None
            lowered = source.lower()
            self.assertNotIn("insert into projects", lowered, name)
            self.assertNotIn("insert into brief_versions", lowered, name)
            self.assertNotIn("from brief_versions", lowered, name)
            self.assertNotIn("delete from projects", lowered, name)

    def _seed_project(self) -> ProjectRecord:
        service = NovelAgentService(
            self.repository, OfflineLLMGateway(), DisabledSearchAdapter()
        )
        return service.create_novel(
            NovelCreateRequest(
                preferred_title="事务书名",
                genre="末世",
                idea="资源社区。",
                require_plan_confirmation=True,
                chapter_target_chars=800,
            )
        )

    def _sample_seed(self) -> tuple[ProjectRecord, list[CharacterRecord], list[WorldFactRecord]]:
        now = utc_now()
        brief = CreativeBrief.model_validate(
            {
                "title_candidates": ["失败书名"],
                "selected_title": "失败书名",
                "synopsis": "简介",
                "target_readers": "读者",
                "selling_points": ["卖点"],
                "protagonist": "方远",
                "main_conflict": "冲突",
                "world_rules": ["规则一"],
                "total_chapters": 10,
                "volume_count": 1,
                "opening_three_chapters": ["一", "二", "三"],
                "update_plan": "日更",
                "style_guide": ["文风"],
            }
        )
        project = ProjectRecord(
            id=new_id("novel"),
            title=brief.selected_title,
            status=ProjectStatus.DRAFT,
            request=NovelCreateRequest(genre="末世", idea="想法"),
            brief=brief,
            confirmed=False,
            current_chapter=0,
            created_at=now,
            updated_at=now,
        )
        characters = [
            CharacterRecord(
                id=new_id("char"),
                project_id=project.id,
                name="方远",
                role="protagonist",
                immutable_facts=[],
                current_state={"profile": ""},
            )
        ]
        world_facts = [
            WorldFactRecord(
                id=new_id("fact"),
                project_id=project.id,
                category="rule",
                statement="规则一",
                locked=True,
            )
        ]
        return project, characters, world_facts

    def test_create_project_writes_project_version_characters_and_world(self) -> None:
        project = self._seed_project()
        self.assertEqual(project.status, ProjectStatus.DRAFT)
        self.assertEqual(len(self.repository.list_brief_versions(project.id)), 1)
        self.assertGreaterEqual(len(self.repository.list_characters(project.id)), 1)
        self.assertGreaterEqual(len(self.repository.list_world_facts(project.id)), 1)
        self.assertIs(self.repository.projects._database, self.repository)
        self.assertIs(self.repository.briefs._database, self.repository)
        self.assertIs(self.repository.project_setup._database, self.repository)

    def test_create_project_rolls_back_when_world_insert_fails(self) -> None:
        project, characters, world_facts = self._sample_seed()
        with self.repository.connection() as conn:
            conn.execute("ALTER TABLE world_facts RENAME TO world_facts_bak")
        try:
            with self.assertRaises(Exception):
                self.repository.create_project(project, characters, world_facts)
            with self.assertRaises(RepositoryError):
                self.repository.get_project(project.id)
            self.assertEqual(self.repository.list_projects(), [])
            self.assertEqual(self.repository.list_brief_versions(project.id), [])
        finally:
            with self.repository.connection() as conn:
                conn.execute("ALTER TABLE world_facts_bak RENAME TO world_facts")

    def test_create_project_rolls_back_when_initial_brief_insert_fails(self) -> None:
        project, characters, world_facts = self._sample_seed()

        def boom(*_args, **_kwargs):
            raise RuntimeError("forced brief v1 failure")

        with patch.object(
            self.repository.project_setup._briefs,
            "insert_initial_version",
            side_effect=boom,
        ):
            with self.assertRaises(RuntimeError):
                self.repository.create_project(project, characters, world_facts)
        with self.assertRaises(RepositoryError):
            self.repository.get_project(project.id)
        self.assertEqual(self.repository.list_projects(), [])

    def test_save_draft_brief_increments_version_and_syncs(self) -> None:
        project = self._seed_project()
        data = project.brief.model_dump(mode="json")
        data["selected_title"] = "新标题"
        data["title_candidates"] = ["新标题", *project.brief.title_candidates]
        data["synopsis"] = "更新后的简介"
        data["world_rules"] = ["新硬规则"]
        updated = self.repository.save_draft_brief(
            project.id, CreativeBrief.model_validate(data), source="manual_edit"
        )
        self.assertEqual(updated.title, "新标题")
        versions = self.repository.list_brief_versions(project.id)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["source"], "manual_edit")
        self.assertEqual(versions[0]["version"], 2)
        characters = self.repository.list_characters(project.id)
        self.assertTrue(any(item.name == updated.brief.protagonist_name for item in characters))
        self.assertEqual(
            [item.statement for item in self.repository.list_world_facts(project.id)],
            ["新硬规则"],
        )

    def test_save_draft_brief_rolls_back_when_version_insert_fails(self) -> None:
        project = self._seed_project()
        data = project.brief.model_dump(mode="json")
        data["selected_title"] = "不应保存"
        data["synopsis"] = "回滚简介"
        with self.repository.connection() as conn:
            conn.execute("ALTER TABLE brief_versions RENAME TO brief_versions_bak")
        try:
            with self.assertRaises(Exception):
                self.repository.save_draft_brief(
                    project.id, CreativeBrief.model_validate(data), source="manual_edit"
                )
            reloaded = self.repository.get_project(project.id)
            self.assertEqual(reloaded.title, project.title)
            self.assertEqual(reloaded.brief.synopsis, project.brief.synopsis)
        finally:
            with self.repository.connection() as conn:
                conn.execute("ALTER TABLE brief_versions_bak RENAME TO brief_versions")
            self.assertEqual(len(self.repository.list_brief_versions(project.id)), 1)

    def test_save_draft_brief_rolls_back_when_character_sync_fails(self) -> None:
        project = self._seed_project()
        data = project.brief.model_dump(mode="json")
        data["selected_title"] = "同步失败标题"
        data["synopsis"] = "同步失败简介"
        data["world_rules"] = ["不该留下的规则"]

        def boom(*_args, **_kwargs):
            raise RuntimeError("forced character sync failure")

        with patch.object(
            self.repository.project_setup,
            "_sync_characters_and_world",
            side_effect=boom,
        ):
            with self.assertRaises(RuntimeError):
                self.repository.save_draft_brief(
                    project.id, CreativeBrief.model_validate(data), source="manual_edit"
                )
        reloaded = self.repository.get_project(project.id)
        self.assertEqual(reloaded.title, project.title)
        self.assertEqual(reloaded.brief.synopsis, project.brief.synopsis)
        self.assertEqual(len(self.repository.list_brief_versions(project.id)), 1)
        self.assertNotIn(
            "不该留下的规则",
            [item.statement for item in self.repository.list_world_facts(project.id)],
        )


if __name__ == "__main__":
    unittest.main()
