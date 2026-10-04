from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = [
    ROOT / "novel_agent",
    ROOT / "apps" / "web" / "src",
    ROOT / "tests",
]
FORBIDDEN = (
    "QUALITY_PASS_SCORE",
    "ChapterQualitySpec",
    "DEFAULT_QUALITY_SPEC",
    "READABILITY_AVERAGE_MIN_SCORE",
    "READABILITY_DIMENSION_MIN_SCORE",
    "LENGTH_PASS_RATIO",
    "LENGTH_MAJOR_RATIO",
    "def _decision_for",
    "ensure_dimension_issues",
    "score < 85",
)
SKIP_PARTS = {"CHAPTER_QUALITY_ALIGNMENT", "node_modules", "dist", "__pycache__"}


class QualityArchitectureTests(unittest.TestCase):
    def test_old_threshold_symbols_removed_from_runtime(self) -> None:
        hits: list[str] = []
        for root in SCAN_ROOTS:
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in {".py", ".ts", ".vue"}:
                    continue
                text = path.read_text(encoding="utf-8")
                if "test_architecture" in path.as_posix():
                    continue
                if any(part in path.as_posix() for part in SKIP_PARTS):
                    continue
                for token in FORBIDDEN:
                    if token in text:
                        hits.append(f"{path.relative_to(ROOT)}:{token}")
        self.assertEqual(hits, [])

    def test_decide_quality_is_the_public_entry(self) -> None:
        decision = (ROOT / "novel_agent/features/chapter_review/decision.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def decide_quality(", decision)
        gate = (ROOT / "novel_agent/features/chapter_review/quality_gate.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("decide_quality(", gate)
        deepseek = (ROOT / "novel_agent/integrations/llm/deepseek.py").read_text(encoding="utf-8")
        self.assertIn("decide_quality(", deepseek)
        self.assertNotIn("raw.decision == ReviewDecision.HUMAN_REQUIRED", deepseek)
        self.assertNotIn("report.decision == ReviewDecision.HUMAN_REQUIRED", gate)


if __name__ == "__main__":
    unittest.main()
