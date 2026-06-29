from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_status_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "paper_run_status.py"
    spec = importlib.util.spec_from_file_location("paper_run_status", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load paper_run_status.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PaperRunStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.status = load_status_module()

    def test_score_counts_counts_not_run_and_error_separately(self) -> None:
        rows = [
            {"score": "pass"},
            {"score": "fail"},
            {"score": "not_run", "error": "api failure"},
            {"score": "weird"},
        ]

        counts = self.status.score_counts(rows)

        self.assertEqual(counts["pass"], 1)
        self.assertEqual(counts["fail"], 1)
        self.assertEqual(counts["not_run"], 1)
        self.assertEqual(counts["rows_with_error"], 1)
        self.assertEqual(counts["other"], 1)

    def test_rank_counts_uses_gold_rank_for_pass_at_k(self) -> None:
        rows = [
            {"gold_rank": 1},
            {"gold_rank": 3},
            {"gold_rank": 6},
            {"gold_rank": None},
            {"gold_rank": "1"},
        ]

        pass_at_1, pass_at_5, ranked = self.status.rank_counts(rows)

        self.assertEqual(pass_at_1, 1)
        self.assertEqual(pass_at_5, 2)
        self.assertEqual(ranked, 3)

    def test_markdown_lane_table_contains_rank_and_not_run_columns(self) -> None:
        rows = [
            {
                "name": "lane",
                "kind": "harness",
                "status": "secondary",
                "rows": 2,
                "missing_rows": 0,
                "score_pass": 1,
                "score_fail": 0,
                "score_not_run": 1,
                "rows_with_error": 1,
                "pass_at_1": 1,
                "pass_at_5": 2,
                "caveat": "rank-based",
            }
        ]

        table = self.status.markdown_lane_table(rows)

        self.assertIn("| Lane | Kind | Status | Rows | Missing |", table)
        self.assertIn("| lane | harness | secondary | 2 | 0 | 1 | 0 | 1 | 1 | 1 | 2 | rank-based |", table)

    def test_render_markdown_points_to_rerun_manifest_readme(self) -> None:
        rendered = self.status.render_markdown()

        self.assertIn("## Current Lane Status", rendered)
        self.assertIn("## Rerun Manifest Summary", rendered)
        self.assertIn("data/eval/rerun_manifests/lm4sci_20260623/README.md", rendered)
        self.assertNotIn("| Lane | Cases |", rendered)


if __name__ == "__main__":
    unittest.main()
