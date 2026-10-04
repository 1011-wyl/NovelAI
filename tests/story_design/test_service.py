from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import BriefRegenerateRequest, CreativeBrief, NovelCreateRequest
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService


class TitleOnlyRevisionGateway(OfflineLLMGateway):
    def revise_brief(self, request, current, feedback, fields):
        data = current.model_dump(mode="json")
        data["selected_title"] = "局部重做后的书名"
        data["title_candidates"] = ["局部重做后的书名", *current.title_candidates]
        data["synopsis"] = "这段简介不应在只重做书名时被采用。"
        return CreativeBrief.model_validate(data)


class StoryDesignServiceCharacterizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.repository = SQLiteRepository(Path(self.folder.name) / "story.db")
        self.service = NovelAgentService(
            self.repository, OfflineLLMGateway(), DisabledSearchAdapter()
        )

    def tearDown(self) -> None:
        self.folder.cleanup()

    def test_brief_field_groups_frozen(self) -> None:
        groups = {
            "title": ["title_candidates", "selected_title"],
            "story": [
                "synopsis",
                "target_readers",
                "selling_points",
                "main_conflict",
                "reader_contract",
                "core_expectation",
            ],
            "protagonist": [
                "protagonist",
                "protagonist_name",
                "protagonist_profile",
                "character_profiles",
            ],
            "world": ["world_rules"],
            "opening": ["opening_three_chapters", "opening_chapter_anchors"],
            "style": ["style_guide"],
            "serialization": ["total_chapters", "volume_count", "update_plan"],
        }
        for section, fields in groups.items():
            self.assertEqual(NovelAgentService._brief_fields([section]), fields)

    def test_preferred_title_and_partial_regenerate_source(self) -> None:
        self.service.gateway = TitleOnlyRevisionGateway()
        project = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="指定书名",
                genre="末世",
                idea="资源社区。",
                chapter_target_chars=800,
            )
        )
        self.assertEqual(project.title, "指定书名")
        original_synopsis = project.brief.synopsis
        regenerated = self.service.regenerate_draft_brief(
            project.id,
            BriefRegenerateRequest(sections=["title"]),
        )
        versions = self.repository.list_brief_versions(project.id)
        self.assertEqual(versions[0]["source"], "partial_regenerate")
        self.assertEqual(regenerated.title, "局部重做后的书名")
        self.assertEqual(regenerated.brief.synopsis, original_synopsis)

    def test_manual_edit_and_restore_append_versions(self) -> None:
        project = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="版本书名",
                genre="末世",
                idea="资源社区。",
                chapter_target_chars=800,
            )
        )
        data = project.brief.model_dump(mode="json")
        data["synopsis"] = "手工修改简介"
        edited = self.service.update_draft_brief(
            project.id, CreativeBrief.model_validate(data)
        )
        self.assertEqual(edited.brief.synopsis, "手工修改简介")
        restored = self.service.restore_draft_brief(project.id, 1)
        versions = self.repository.list_brief_versions(project.id)
        self.assertEqual(versions[0]["source"], "restore")
        self.assertEqual([item["version"] for item in versions], [3, 2, 1])
        self.assertEqual(restored.brief.synopsis, project.brief.synopsis)

    def test_create_novel_signature_stable(self) -> None:
        signature = inspect.signature(NovelAgentService.create_novel)
        self.assertEqual(tuple(signature.parameters)[1:], ("request",))


if __name__ == "__main__":
    unittest.main()
