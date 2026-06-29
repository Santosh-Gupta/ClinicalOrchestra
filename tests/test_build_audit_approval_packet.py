from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def load_packet_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_audit_approval_packet.py"
    spec = importlib.util.spec_from_file_location("build_audit_approval_packet", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load build_audit_approval_packet.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AuditApprovalPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = load_packet_module()

    def test_generated_packet_has_required_decision_summary(self) -> None:
        text = self.packet.build_packet(
            Path("docs/AUDIT_ARBITRATION_PROPOSAL_20260623.md"),
            Path("build/audit_arbitration_preview/summary.json"),
        )

        self.assertEqual(self.packet.validate_packet(text), [])
        self.assertIn("Hard-set denominator if approved as previewed: 81 -> 68", text)
        self.assertIn("Hard-set denominator if the unresolved review case is dropped: 81 -> 68", text)
        self.assertIn("## Proposed Drops", text)
        self.assertIn("## Proposed Mends", text)
        self.assertIn("transformed_PMC13149065", text)

    def test_preview_summary_controls_denominator_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.json"
            summary.write_text(
                json.dumps(
                    {
                        "crossmodel_original_n": 81,
                        "crossmodel_preview_n": 67,
                        "publish_original_n": 151,
                        "publish_preview_n": 137,
                        "review_case_unresolved": "transformed_PMC13149065",
                    }
                ),
                encoding="utf-8",
            )

            text = self.packet.build_packet(
                Path("docs/AUDIT_ARBITRATION_PROPOSAL_20260623.md"),
                summary,
            )

        self.assertIn("Publish manifest preview denominator: 151 -> 137", text)

    def test_validate_packet_reports_missing_required_text(self) -> None:
        errors = self.packet.validate_packet("too short")

        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
