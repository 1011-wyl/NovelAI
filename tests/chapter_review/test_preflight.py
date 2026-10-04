from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novel_agent.features.chapter_review.preflight import run_preflight
from novel_agent.features.chapter_review.quality_spec import count_quality_chars
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import ChapterStatus, IssueSeverity, NovelCreateRequest, ReviewDecision
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService
from novel_agent.story_skills import StorySkillsRuntime
from novel_agent.writing_skills import OhStoryWritingRuntime


class PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(Path(self.tmp.name) / "preflight.db")
        self.service = NovelAgentService(
            self.repo,
            OfflineLLMGateway(),
            DisabledSearchAdapter(),
            story_skills=StorySkillsRuntime.disabled(),
            writing_skills=OhStoryWritingRuntime.disabled(),
            max_revision_attempts=0,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _project(self, **kwargs):
        payload = {
            "idea": "仓储管理员依靠有限经验建立社区。",
            "genre": "末世",
            "require_plan_confirmation": False,
            "chapter_target_chars": 1000,
            "exclude": [],
        }
        payload.update(kwargs)
        return self.service.create_novel(NovelCreateRequest(**payload))

    def test_body_char_count_includes_punctuation_and_only_drops_explicit_title(self) -> None:
        content = "第1章 标题\n\n甲乙，丙\n\n丁！"
        self.assertEqual(count_quality_chars(content), 6)
        self.assertEqual(count_quality_chars("他推开门。\n\n风停了。"), 9)
        self.assertEqual(count_quality_chars("Title\n\nHello, world!"), 17)

    def test_length_thresholds(self) -> None:
        project = self._project(chapter_target_chars=3000)
        result = self.service.generate_next_chapter(project.id)
        chapter = result.chapter
        assert chapter.plan is not None
        target = project.request.chapter_target_chars
        title = "第1章 测试\n\n"
        body_min = "字" * (target - 500)
        body_short = "字" * (target - 501)
        body_69 = "字" * int(target * 0.69)
        ok = run_preflight(project, chapter.plan, project.brief.protagonist_name, title + body_min, False)
        minor = run_preflight(project, chapter.plan, project.brief.protagonist_name, title + body_short, False)
        major = run_preflight(project, chapter.plan, project.brief.protagonist_name, title + body_69, False)
        self.assertFalse(any(issue.category == "length" for issue in ok.issues))
        self.assertTrue(
            any(
                issue.category == "length" and issue.severity == IssueSeverity.MINOR
                for issue in minor.issues
            )
        )
        self.assertTrue(
            any(
                issue.category == "length" and issue.severity == IssueSeverity.MINOR
                for issue in major.issues
            )
        )
        self.assertEqual(major.length_class, "severe_short")
        self.assertEqual(major.quality_status, "LENGTH_REPAIRING")

    def test_missing_protagonist_name_is_minor_not_major(self) -> None:
        project = self._project()
        result = self.service.generate_next_chapter(project.id)
        chapter = result.chapter
        assert chapter.plan is not None
        content = "第1章\n\n我推开门，把清单压在桌上。" + ("补充" * 400)
        report = run_preflight(project, chapter.plan, "林川", content, False).report
        character_issues = [issue for issue in report.issues if issue.category == "character"]
        self.assertTrue(character_issues)
        self.assertTrue(all(issue.severity == IssueSeverity.MINOR for issue in character_issues))

    def test_exclude_empty_and_chapter1_forbidden_are_blockers(self) -> None:
        project = self._project(exclude=["禁词XYZ"])
        result = self.service.generate_next_chapter(project.id)
        chapter = result.chapter
        assert chapter.plan is not None
        content = "第1章\n\n承接上一章，禁词XYZ继续出现。" + ("字" * 900)
        report = run_preflight(
            project, chapter.plan, project.brief.protagonist_name, content, False
        ).report
        self.assertNotEqual(report.decision, ReviewDecision.PASS)
        self.assertTrue(any(issue.severity == IssueSeverity.BLOCKER for issue in report.issues))
        empty = run_preflight(project, chapter.plan, project.brief.protagonist_name, "", False).report
        self.assertTrue(any("空" in issue.message for issue in empty.issues))


if __name__ == "__main__":
    unittest.main()
