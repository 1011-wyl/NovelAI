from __future__ import annotations

import unittest

from novel_agent.features.chapter_review.decision import decide_quality
from novel_agent.features.chapter_review.quality_gate import annotate_report
from novel_agent.features.chapter_review.quality_spec import READABILITY_DIMENSIONS
from novel_agent.models import IssueSeverity, ReviewDecision, ReviewIssue, ReviewReport


def _report(score: float, **kwargs) -> ReviewReport:
    checks = {name: score for name in READABILITY_DIMENSIONS}
    checks.update(kwargs.pop("checks", {}))
    return ReviewReport(decision=ReviewDecision.REVISE, score=score, checks=checks, **kwargs)


class DecideQualityTests(unittest.TestCase):
    def test_sixty_does_not_pass(self) -> None:
        self.assertEqual(decide_quality(60.0), ReviewDecision.REVISE)

    def test_just_over_sixty_passes(self) -> None:
        self.assertEqual(decide_quality(60.01), ReviewDecision.PASS)

    def test_seventy_seven_with_minor_passes(self) -> None:
        report = annotate_report(
            _report(
                77.0,
                issues=[
                    ReviewIssue(
                        category="readability.opening_hook",
                        severity=IssueSeverity.MINOR,
                        message="开篇可再紧一点",
                        suggestion="用现场问题开篇",
                        evidence=["第一段偏缓"],
                    )
                ],
            )
        )
        self.assertEqual(report.decision, ReviewDecision.PASS)
        self.assertGreater(report.score, 60.0)

    def test_seventy_seven_with_dimension_below_75_still_passes(self) -> None:
        checks = {name: 80.0 for name in READABILITY_DIMENSIONS}
        checks["opening_hook"] = 70.0
        report = annotate_report(_report(77.0, checks=checks))
        self.assertEqual(report.decision, ReviewDecision.PASS)
        self.assertEqual(report.score, 78.75)

    def test_seventy_seven_with_average_below_82_still_passes(self) -> None:
        checks = {name: 77.0 for name in READABILITY_DIMENSIONS}
        report = annotate_report(_report(77.0, checks=checks))
        self.assertEqual(report.decision, ReviewDecision.PASS)
        self.assertLess(report.score, 82.0)

    def test_reviewer_local_decision_cannot_override_unified_score(self) -> None:
        report = annotate_report(
            ReviewReport(
                decision=ReviewDecision.REVISE,
                score=77.0,
                checks={name: 77.0 for name in READABILITY_DIMENSIONS},
                issues=[
                    ReviewIssue(
                        category="readability.dialogue_voice",
                        severity=IssueSeverity.MAJOR,
                        message="对话偏同质",
                        suggestion="区分口吻",
                        evidence=["两人同声"],
                    )
                ],
            )
        )
        self.assertEqual(report.decision, ReviewDecision.PASS)

    def test_reviewer_human_required_hint_cannot_override_unified_score(self) -> None:
        report = annotate_report(
            ReviewReport(
                decision=ReviewDecision.HUMAN_REQUIRED,
                score=77.0,
                checks={name: 77.0 for name in READABILITY_DIMENSIONS},
            )
        )
        self.assertEqual(report.decision, ReviewDecision.PASS)
        self.assertEqual(report.quality_status, "PASSED")


if __name__ == "__main__":
    unittest.main()
