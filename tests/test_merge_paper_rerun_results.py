from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def load_merge_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "merge_paper_rerun_results.py"
    spec = importlib.util.spec_from_file_location("merge_paper_rerun_results", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load merge_paper_rerun_results.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MergePaperRerunResultsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.merge = load_merge_module()

    def test_complete_rerun_replaces_base_row(self) -> None:
        base = [{"case_id": "a", "score": "not_run", "error": "quota"}]
        rerun = [{"case_id": "a", "score": "pass", "answer": "new"}]

        merged, stats = self.merge.merge_rows(base, rerun)

        self.assertEqual(merged, [{"case_id": "a", "score": "pass", "answer": "new"}])
        self.assertEqual(stats["replaced"], 1)
        self.assertEqual(stats["skipped_incomplete_rerun"], 0)

    def test_incomplete_rerun_does_not_replace_base_row_by_default(self) -> None:
        base = [{"case_id": "a", "score": "pass", "answer": "base"}]
        rerun = [{"case_id": "a", "score": "not_run", "error": "quota"}]

        merged, stats = self.merge.merge_rows(base, rerun)

        self.assertEqual(merged, base)
        self.assertEqual(stats["replaced"], 0)
        self.assertEqual(stats["skipped_incomplete_rerun"], 1)

    def test_complete_rerun_row_can_be_added_when_base_is_missing(self) -> None:
        base = [{"case_id": "a", "score": "fail"}]
        rerun = [{"case_id": "b", "score": "pass"}]

        merged, stats = self.merge.merge_rows(base, rerun)

        self.assertEqual([row["case_id"] for row in merged], ["a", "b"])
        self.assertEqual(stats["added"], 1)

    def test_cli_refuses_to_write_over_base_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text('{"case_id":"a","score":"pass"}\n', encoding="utf-8")

            code = self.merge.main(["--base", str(path), "--rerun", str(path), "--out", str(path)])

        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
