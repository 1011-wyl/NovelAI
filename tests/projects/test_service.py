from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import NovelCreateRequest, ProjectStatus
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService


DETAIL_KEYS = {
    "project",
    "chapters",
    "latest_events",
    "characters",
    "world_facts",
    "timeline",
    "research_sources",
    "semantic_document_count",
    "reserve_count",
    "skills",
}


class ProjectServiceCharacterizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.repository = SQLiteRepository(Path(self.folder.name) / "service.db")
        self.service = NovelAgentService(
            self.repository, OfflineLLMGateway(), DisabledSearchAdapter()
        )

    def tearDown(self) -> None:
        self.folder.cleanup()

    def test_novel_agent_service_lifecycle_signatures(self) -> None:
        expected = {
            "create_novel": ("request",),
            "confirm_novel": ("project_id",),
            "update_draft_brief": ("project_id", "brief"),
            "regenerate_draft_brief": ("project_id", "change"),
            "restore_draft_brief": ("project_id", "version"),
            "pause_novel": ("project_id",),
            "resume_novel": ("project_id",),
            "project_detail": ("project_id",),
        }
        for name, params in expected.items():
            signature = inspect.signature(getattr(NovelAgentService, name))
            self.assertEqual(tuple(signature.parameters)[1:], params, name)
        delete_params = inspect.signature(NovelAgentService.delete_novel).parameters
        self.assertEqual(tuple(delete_params)[1:], ("project_id", "confirmation_title"))
        self.assertEqual(
            delete_params["confirmation_title"].kind, inspect.Parameter.KEYWORD_ONLY
        )

    def test_project_detail_fields_frozen(self) -> None:
        project = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="详情书名",
                genre="末世",
                idea="资源社区。",
                chapter_target_chars=800,
            )
        )
        detail = self.service.project_detail(project.id)
        self.assertEqual(set(detail), DETAIL_KEYS)
        self.assertIn("story_skills", detail["skills"])  # type: ignore[index]
        self.assertIn("oh_story", detail["skills"])  # type: ignore[index]

    def test_confirm_pause_resume_and_delete_draft(self) -> None:
        project = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="生命周期",
                genre="末世",
                idea="资源社区。",
                chapter_target_chars=800,
            )
        )
        confirmed = self.service.confirm_novel(project.id)
        self.assertTrue(confirmed.confirmed)
        self.assertEqual(confirmed.status, ProjectStatus.ACTIVE)
        paused = self.service.pause_novel(project.id)
        self.assertEqual(paused.status, ProjectStatus.PAUSED)
        resumed = self.service.resume_novel(project.id)
        self.assertEqual(resumed.status, ProjectStatus.ACTIVE)
        draft = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="可删草稿",
                genre="悬疑",
                idea="调查。",
                chapter_target_chars=800,
            )
        )
        self.service.delete_novel(draft.id)
        self.assertEqual(
            [item.id for item in self.repository.list_projects()],
            [resumed.id],
        )


if __name__ == "__main__":
    unittest.main()
