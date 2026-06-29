from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_validator_module():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "validate_audit_arbitration_proposal.py"
    )
    spec = importlib.util.spec_from_file_location("validate_audit_arbitration_proposal", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load validate_audit_arbitration_proposal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AuditArbitrationProposalValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_validator_module()

    def test_table_rows_skips_headers_and_separators(self) -> None:
        markdown = (
            "| case_id | tier | action | justification |\n"
            "|---|---:|---|---|\n"
            "| transformed_A | leak3 | DROP | reason |\n"
        )

        rows = self.validator.action_rows(markdown)

        self.assertEqual(rows, [{"case_id": "transformed_A", "tier": "leak3", "action": "DROP", "justification": "reason"}])

    def test_operation_case_ids_extracts_case_rows_only(self) -> None:
        markdown = (
            "| case_id | operation | exact edit intent |\n"
            "|---|---|---|\n"
            "| transformed_A | DELETE | remove sentence |\n"
            "| note | not a case | ignored |\n"
        )

        ids = self.validator.operation_case_ids(markdown)

        self.assertEqual(ids, {"transformed_A"})

    def test_validate_reports_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            errors = self.validator.validate(
                root / "missing.md",
                root / "missing.csv",
                root / "missing.jsonl",
            )

        self.assertIn("missing proposal", errors[0])


if __name__ == "__main__":
    unittest.main()
