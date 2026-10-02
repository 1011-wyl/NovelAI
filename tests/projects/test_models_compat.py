from __future__ import annotations

import unittest

from novel_agent.features.projects import models as new_models
from novel_agent.models import ProjectRecord, ProjectStatus


class ProjectModelsCompatTests(unittest.TestCase):
    def test_project_status_and_record_are_identical_objects(self) -> None:
        self.assertIs(ProjectStatus, new_models.ProjectStatus)
        self.assertIs(ProjectRecord, new_models.ProjectRecord)

    def test_project_status_values_frozen(self) -> None:
        self.assertEqual(
            [item.value for item in ProjectStatus],
            ["DRAFT", "ACTIVE", "PAUSED", "ARCHIVED", "HUMAN_REQUIRED"],
        )

    def test_project_record_schema_matches_feature_module(self) -> None:
        self.assertEqual(
            ProjectRecord.model_json_schema(),
            new_models.ProjectRecord.model_json_schema(),
        )


if __name__ == "__main__":
    unittest.main()
