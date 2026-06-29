from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def load_preview_module():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "preview_audit_arbitration_cleanup.py"
    )
    spec = importlib.util.spec_from_file_location("preview_audit_arbitration_cleanup", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load preview_audit_arbitration_cleanup.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AuditArbitrationCleanupPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview = load_preview_module()

    def _synthetic_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for case_id in sorted(self.preview.DROP_IDS):
            rows.append({"case_id": case_id, "challenge_prompt": "drop me", "answer_key": {"diagnosis": "x"}})
        for op in self.preview.MEND_OPERATIONS:
            rows.append({"case_id": op.case_id, "challenge_prompt": f"before {op.old} after", "answer_key": {"diagnosis": "x"}})
        rows.append({"case_id": self.preview.REVIEW_ID, "challenge_prompt": "review only", "answer_key": {"diagnosis": "x"}})
        rows.append({"case_id": "transformed_KEEP", "challenge_prompt": "keep", "answer_key": {"diagnosis": "x"}})
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    def test_preview_writes_patched_manifests_without_source_edits(self) -> None:
        rows = self._synthetic_rows()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cross = root / "cross.jsonl"
            publish = root / "publish.jsonl"
            out = root / "preview"
            self._write_jsonl(cross, rows)
            self._write_jsonl(publish, rows)

            errors = self.preview.run_preview(cross, publish, out)

            self.assertEqual(errors, [])
            patched_rows = [
                json.loads(line)
                for line in (out / "cross.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            patched_ids = {row["case_id"] for row in patched_rows}
            self.assertFalse(self.preview.DROP_IDS & patched_ids)
            self.assertIn(self.preview.REVIEW_ID, patched_ids)
            for op in self.preview.MEND_OPERATIONS:
                patched = next(row for row in patched_rows if row["case_id"] == op.case_id)
                prompt = patched["challenge_prompt"]
                self.assertNotIn(op.old, prompt)
                if op.new:
                    self.assertIn(op.new, prompt)
                self.assertEqual(patched["audit_arbitration_preview"]["action"], "MEND")

            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["drop_count"], len(self.preview.DROP_IDS))
            self.assertEqual(summary["mend_count"], len(self.preview.MEND_OPERATIONS))

    def test_preview_reports_missing_exact_mend_text(self) -> None:
        rows = self._synthetic_rows()
        rows = [dict(row) for row in rows]
        for row in rows:
            if row["case_id"] == self.preview.MEND_OPERATIONS[0].case_id:
                row["challenge_prompt"] = "missing exact text"
                break

        errors = self.preview.validate_manifest_rows(rows, "synthetic")

        self.assertTrue(any("exact old text not found" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
