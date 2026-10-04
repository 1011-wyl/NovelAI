from __future__ import annotations

import unittest

from novel_agent.features.chapter_planning.anchors import resolve_opening_anchor
from novel_agent.features.chapter_planning.context import build_planning_context
from novel_agent.features.chapter_planning.models import PlanningContext, ReworkMode
from novel_agent.features.chapter_planning.rework_policy import classify_rework_mode, resolve_requested_mode
from novel_agent.features.chapter_planning.validation import validate_plan_against_anchor
from novel_agent.features.story_design.character_seed import seed_payloads_from_brief
from novel_agent.features.story_design.models import (
    CharacterProfile,
    CreativeBrief,
    NovelCreateRequest,
    OpeningChapterAnchor,
)
from novel_agent.models import ChapterPlan, IssueSeverity, ReviewDecision, ReviewIssue, ReviewReport


def _brief() -> CreativeBrief:
    return CreativeBrief.model_validate(
        {
            "title_candidates": ["基建：从解析神纹开始"],
            "selected_title": "基建：从解析神纹开始",
            "synopsis": "简介",
            "target_readers": "读者",
            "selling_points": ["卖点"],
            "protagonist": "顾宁",
            "protagonist_name": "顾宁",
            "protagonist_profile": "主角",
            "character_profiles": [
                {
                    "name": "顾宁",
                    "role": "protagonist",
                    "importance": "core",
                    "profile": "仓库管理员",
                    "personality": ["冷静"],
                    "core_goal": "活下去",
                    "stable_facts": ["没有无限资源"],
                    "initial_state": "普通人",
                    "initial_goal": "确认神纹是否可解析",
                    "initial_relationships": {},
                    "future_arc": "中后期才可能建立秩序",
                    "future_relationships": {},
                },
                {
                    "name": "顾铁山",
                    "role": "supporting",
                    "profile": "独立行动者",
                    "personality": ["务实"],
                    "core_goal": "保护同伴",
                    "relationships": {"顾宁": "被救后效忠主角"},
                    "initial_state": "尚无主从关系",
                    "initial_relationships": {},
                    "future_arc": "被救后才可能成为代理人",
                    "future_relationships": {"顾宁": "被救后效忠主角"},
                },
            ],
            "main_conflict": "冲突",
            "world_rules": ["规则"],
            "total_chapters": 120,
            "volume_count": 3,
            "opening_chapter_anchors": [
                {
                    "number": 1,
                    "title": "异常征兆",
                    "core_event": "神纹异常出现，顾宁用仓储经验抢到第一项先机",
                    "must_establish": ["能力起点"],
                    "forbidden_assumptions": ["已经效忠"],
                },
                {
                    "number": 2,
                    "title": "选择代价",
                    "core_event": "旧秩序失效，主角为一个具体选择付出代价",
                },
                {
                    "number": 3,
                    "title": "第一次对抗",
                    "core_event": "第一次公开对抗并暴露信息差",
                },
            ],
            "update_plan": "日更",
            "style_guide": ["文风"],
        }
    )


def _plan(number: int, title: str, objective: str, extra: str = "") -> ChapterPlan:
    return ChapterPlan(
        number=number,
        title=title,
        objective=objective,
        conflict="阻力",
        turning_point="转折",
        hook="钩子",
        scenes=[objective, extra] if extra else [objective],
    )


class ChapterPlanningTests(unittest.TestCase):
    def test_seed_keeps_future_loyalty_out_of_chapter_zero(self) -> None:
        brief = _brief()
        request = NovelCreateRequest(genre="末世", idea="神纹解析")
        payloads = seed_payloads_from_brief(request, brief)
        by_name = {profile.name: state for profile, _facts, state in payloads}
        self.assertEqual(by_name["顾铁山"]["relationships"], {})
        self.assertNotIn("效忠", str(by_name["顾铁山"]))
        facts = next(facts for profile, facts, _state in payloads if profile.name == "顾宁")
        self.assertTrue(any("没有无限资源" in item for item in facts))

    def test_opening_anchors_bind_by_chapter_number(self) -> None:
        brief = _brief()
        first = resolve_opening_anchor(brief, 1)
        second = resolve_opening_anchor(brief, 2)
        assert first is not None and second is not None
        self.assertEqual(first.title, "异常征兆")
        self.assertEqual(second.title, "选择代价")
        context = build_planning_context(
            project_id="p",
            chapter_number=1,
            brief=brief,
            chapters=[],
        )
        self.assertEqual(context.recent_summaries, [])
        self.assertEqual(context.timeline, [])
        self.assertEqual(context.open_threads, [])
        self.assertEqual(context.previous_chapter_excerpt, "")

    def test_chapter_one_rejects_previous_chapter_language_and_sibling_plot(self) -> None:
        brief = _brief()
        context = PlanningContext(
            chapter_number=1,
            opening_anchor=resolve_opening_anchor(brief, 1),
        )
        bad_prev = _plan(1, "异常征兆", "承接上一章继续清点仓库")
        issues = validate_plan_against_anchor(
            bad_prev, chapter_number=1, context=context, brief=brief
        )
        self.assertTrue(any("禁用前情" in item for item in issues))
        sibling = _plan(1, "选择代价", "旧秩序失效，主角为一个具体选择付出代价")
        sibling_issues = validate_plan_against_anchor(
            sibling, chapter_number=1, context=context, brief=brief
        )
        self.assertTrue(sibling_issues)

    def test_rework_mode_splits_structural_and_language_failures(self) -> None:
        plan = _plan(1, "异常征兆", "神纹异常出现")
        structural = ReviewReport(
            decision=ReviewDecision.REVISE,
            score=40,
            issues=[
                ReviewIssue(
                    category="character state",
                    severity=IssueSeverity.MAJOR,
                    message="人物关系错误",
                    suggestion="回到初态",
                )
            ],
        )
        language = ReviewReport(
            decision=ReviewDecision.REVISE,
            score=50,
            issues=[
                ReviewIssue(
                    category="length",
                    severity=IssueSeverity.MAJOR,
                    message="字数偏短",
                    suggestion="补场景",
                )
            ],
        )
        self.assertEqual(classify_rework_mode(structural, 1, plan), ReworkMode.REPLAN)
        self.assertEqual(classify_rework_mode(language, 1, plan), ReworkMode.REUSE_PLAN)
        self.assertEqual(
            resolve_requested_mode("replan", report=language, chapter_number=1, plan=plan),
            ReworkMode.REPLAN,
        )
        from novel_agent.features.chapter_planning.errors import ReworkModeNotAllowedError

        with self.assertRaises(ReworkModeNotAllowedError):
            resolve_requested_mode("reuse_plan", report=structural, chapter_number=1, plan=plan)

    def test_chinese_ngram_allows_paraphrase_and_rejects_sibling(self) -> None:
        brief = _brief()
        context = PlanningContext(
            chapter_number=1,
            opening_anchor=resolve_opening_anchor(brief, 1),
        )
        same = _plan(1, "异常征兆", "神纹异常出现，顾宁用仓储经验抢到第一项先机")
        self.assertEqual(
            validate_plan_against_anchor(same, chapter_number=1, context=context, brief=brief),
            [],
        )
        paraphrase = _plan(1, "异常征兆", "仓库里的神纹忽然失控，顾宁凭仓储经验抢到先机")
        self.assertEqual(
            validate_plan_against_anchor(
                paraphrase, chapter_number=1, context=context, brief=brief
            ),
            [],
        )
        title_only = _plan(1, "异常征兆", "旧秩序失效，主角为一个具体选择付出代价")
        self.assertTrue(
            validate_plan_against_anchor(
                title_only, chapter_number=1, context=context, brief=brief
            )
        )
        missing_brief = brief.model_copy(deep=True)
        missing_brief.opening_chapter_anchors[0] = missing_brief.opening_chapter_anchors[0].model_copy(
            update={"must_establish": ["用仓储经验抢到第一项先机"]}
        )
        missing_context = PlanningContext(
            chapter_number=1,
            opening_anchor=resolve_opening_anchor(missing_brief, 1),
        )
        missing = _plan(1, "异常征兆", "夜里停电，大家在门口观望")
        missing_issues = validate_plan_against_anchor(
            missing, chapter_number=1, context=missing_context, brief=missing_brief
        )
        self.assertTrue(any("必须建立项" in item or "核心事件" in item for item in missing_issues))
        forbidden = _plan(1, "异常征兆", "神纹异常出现，顾宁已经效忠并掌控全局")
        forbidden_issues = validate_plan_against_anchor(
            forbidden, chapter_number=1, context=context, brief=brief
        )
        self.assertTrue(any("禁止预设" in item or "效忠" in item for item in forbidden_issues))


if __name__ == "__main__":
    unittest.main()
