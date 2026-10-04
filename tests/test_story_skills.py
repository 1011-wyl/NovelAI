import tempfile
import unittest
from pathlib import Path

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import (
    ContinuityContext,
    IssueSeverity,
    NovelCreateRequest,
    ReviewDecision,
    ReviewIssue,
    ReviewReport,
)
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService
from novel_agent.story_skills import STORY_SKILLS_COMMIT, StorySkillsRuntime


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AuditingGateway(OfflineLLMGateway):
    def __init__(self) -> None:
        self.review_calls = 0
        self.last_context: ContinuityContext | None = None
        self.last_skill_instructions = ""

    def review_continuity(
        self,
        context: ContinuityContext,
        skill_instructions: str,
    ) -> ReviewReport:
        from novel_agent.features.chapter_review.quality_spec import READABILITY_DIMENSIONS

        self.review_calls += 1
        self.last_context = context
        self.last_skill_instructions = skill_instructions
        if self.review_calls == 1:
            return ReviewReport(
                decision=ReviewDecision.REVISE,
                score=55,
                issues=[
                    ReviewIssue(
                        category="character_knowledge",
                        severity=IssueSeverity.MAJOR,
                        message="人物使用了尚未建立的信息",
                        suggestion="把信息来源补入本章行动过程",
                        evidence=["测试审校证据"],
                    )
                ],
                checks={"character_knowledge": 55, **{key: 55.0 for key in READABILITY_DIMENSIONS}},
            )
        return ReviewReport(
            decision=ReviewDecision.PASS,
            score=96,
            checks={"character_knowledge": 96},
        )

    def review_readability(self, context):
        from novel_agent.features.chapter_review.quality_spec import READABILITY_DIMENSIONS

        # Story-skills MAJOR alone must not veto; keep readability below the pass line
        # so the chapter still fails for retry under the unified score rule.
        if self.review_calls == 0:
            return ReviewReport(
                decision=ReviewDecision.REVISE,
                score=55,
                checks={key: 55.0 for key in READABILITY_DIMENSIONS},
                issues=[
                    ReviewIssue(
                        category="readability.scene_causality",
                        severity=IssueSeverity.MAJOR,
                        message="场景因果偏弱",
                        suggestion="补足行动后果",
                        evidence=["测试可读性证据"],
                    )
                ],
            )
        return super().review_readability(context)


class StorySkillsRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = SQLiteRepository(Path(self.tempdir.name) / "story-skills.db")
        self.runtime = StorySkillsRuntime.load(PROJECT_ROOT, enabled=True)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @staticmethod
    def request() -> NovelCreateRequest:
        return NovelCreateRequest(
            genre="末世",
            elements=["经营建设"],
            idea="仓储管理员依靠有限经验建立社区，没有无限资源。",
            chapter_target_chars=800,
            reserve_target=1,
            require_plan_confirmation=False,
        )

    def test_vendored_skills_are_loaded_from_pinned_source(self) -> None:
        readiness = self.runtime.readiness()

        self.assertTrue(readiness["enabled"])
        self.assertEqual(readiness["version"], STORY_SKILLS_COMMIT[:12])
        self.assertEqual(
            set(readiness["skills"]),
            {"revision-continuity", "story-maintenance"},
        )
        self.assertIn(
            "Character knowledge",
            self.runtime.definitions["revision-continuity"].instructions,
        )

    def test_workflow_invokes_skill_and_holds_major_issue_for_retry(self) -> None:
        gateway = AuditingGateway()
        service = NovelAgentService(
            repository=self.repository,
            gateway=gateway,
            search=DisabledSearchAdapter(),
            story_skills=self.runtime,
            max_revision_attempts=0,
        )
        project = service.create_novel(self.request())

        result = service.generate_next_chapter(project.id)

        self.assertEqual(gateway.review_calls, 1)
        self.assertIsNotNone(gateway.last_context)
        self.assertEqual(gateway.last_context.project_id, project.id)
        self.assertIn("Continuity Audit Checklist", gateway.last_skill_instructions)
        self.assertEqual(result.review.decision, ReviewDecision.REVISE)
        self.assertEqual(result.chapter.status.value, "FAILED")
        self.assertTrue(
            any(issue.severity == IssueSeverity.MAJOR for issue in result.review.issues)
        )
        self.assertIn("story_skills_semantic", result.review.checks)
        self.assertEqual(
            [event.node for event in result.events].count("StorySkillsAudit"),
            1,
        )

    def test_deterministic_foreshadow_order_blocks_chapter(self) -> None:
        gateway = OfflineLLMGateway()
        service = NovelAgentService(
            repository=self.repository,
            gateway=gateway,
            search=DisabledSearchAdapter(),
        )
        project = service.create_novel(self.request())
        with self.repository.transaction() as conn:
            conn.execute(
                """INSERT INTO foreshadows
                (project_id,label,status,introduced_chapter,resolved_chapter)
                VALUES (?,?,?,?,?)""",
                (project.id, "损坏的罗盘", "RESOLVED", 3, 2),
            )
        roster = self.repository.list_characters(project.id)
        plan = gateway.plan_chapter(
            project.request,
            project.brief,
            1,
            [],
            [],
            roster,
        )
        content = gateway.write_chapter(
            project.request,
            project.brief,
            plan,
            project.brief.protagonist_name,
            [],
            roster,
        )

        report = self.runtime.audit(
            self.repository,
            gateway,
            project,
            plan,
            content,
        )

        self.assertEqual(report.decision, ReviewDecision.REVISE)
        self.assertTrue(
            any(issue.severity == IssueSeverity.BLOCKER for issue in report.issues)
        )
        self.assertLess(report.checks["story_skills_deterministic"], 100)


if __name__ == "__main__":
    unittest.main()
