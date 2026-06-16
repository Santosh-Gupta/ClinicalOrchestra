import csv
import json
import tempfile
import unittest
from pathlib import Path

from clinical_harness.deepseek_failures import (
    DeepSeekFailurePaths,
    load_failure_analysis_packets,
    write_packets_jsonl,
)


class DeepSeekFailurePacketTests(unittest.TestCase):
    def test_load_failure_analysis_packets_from_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _write_fixture_files(Path(tmpdir))

            packets = load_failure_analysis_packets(paths)

            self.assertEqual(len(packets), 2)
            packet = packets[0]
            self.assertEqual(packet.case_id, "transformed_PMC10399123")
            self.assertEqual(packet.cluster_hint, "neuro_psych")
            self.assertIn("challenge_prompt", packet.diagnostic_agent_input)
            self.assertEqual(
                packet.diagnostic_agent_input["blocked_retrieval_shortcuts"]["pmcid"],
                "PMC10399123",
            )
            self.assertEqual(
                packet.evaluator_only["expected_key_answer"],
                "Pediatric-onset multiple sclerosis",
            )
            self.assertEqual(packet.failed_model_outputs["pro"]["score_status"], "fail")
            self.assertIn("Do not propose searches using source title", packet.comparison_prompt)

    def test_neuro_psych_subset_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _write_fixture_files(Path(tmpdir))

            packets = load_failure_analysis_packets(paths, subset="neuro_psych")

            self.assertEqual([packet.case_id for packet in packets], ["transformed_PMC10399123"])

    def test_write_packets_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _write_fixture_files(Path(tmpdir))
            packets = load_failure_analysis_packets(paths, case_ids=("native_PMC3122590",))
            output_path = Path(tmpdir) / "packets.jsonl"

            write_packets_jsonl(packets, output_path)
            lines = output_path.read_text(encoding="utf-8").strip().splitlines()
            payload = json.loads(lines[0])

            self.assertEqual(len(lines), 1)
            self.assertEqual(payload["case_id"], "native_PMC3122590")
            self.assertIn("comparison_prompt", payload)


def _write_fixture_files(root: Path) -> DeepSeekFailurePaths:
    manifest_path = root / "manifest.jsonl"
    failed_ids_path = root / "failed_ids.txt"
    pro_comparison_path = root / "pro_comparison.tsv"
    pro_results_path = root / "pro_results.tsv"
    pro_scores_path = root / "pro_scores.tsv"
    flash_results_path = root / "flash_results.tsv"
    flash_scores_path = root / "flash_scores.tsv"

    cases = [
        {
            "case_id": "transformed_PMC10399123",
            "challenge_prompt": "A child has demyelinating attacks, CSF oligoclonal bands, and transient low-titer MOG antibodies.",
            "answer_rest": "The original paper diagnosed pediatric-onset multiple sclerosis.",
            "title": "Original demyelinating case",
            "journal": "Example Journal",
            "pmcid": "PMC10399123",
            "doi": "10.0000/ms",
            "license_key": "cc_by",
            "license_tier": "public_training_compatible_holdout",
        },
        {
            "case_id": "native_PMC3122590",
            "challenge_prompt": "A glans lesion is hyperkeratotic and has no dysplasia at the base.",
            "answer_rest": "{\"diagnosis\": \"Cutaneous horn\"}",
            "title": "What is your diagnosis?",
            "journal": "Derm Journal",
            "pmcid": "PMC3122590",
            "doi": "10.0000/horn",
            "license_key": "cc_by",
            "license_tier": "public_training_compatible_holdout",
        },
    ]
    manifest_path.write_text("\n".join(json.dumps(case) for case in cases) + "\n", encoding="utf-8")
    failed_ids_path.write_text("transformed_PMC10399123\nnative_PMC3122590\n", encoding="utf-8")

    _write_tsv(
        flash_results_path,
        [
            {
                "case_id": "transformed_PMC10399123",
                "model": "deepseek-v4-flash",
                "final_diagnosis": "MOGAD",
                "top_differential": "[\"MS\"]",
                "recommended_next_step": "Repeat MOG testing",
                "confidence": "0.7",
                "evidence_summary": "[\"low-titer MOG\"]",
                "uncertainty_or_missing_information": "[\"OCB interpretation\"]",
            },
            {
                "case_id": "native_PMC3122590",
                "model": "deepseek-v4-flash",
                "final_diagnosis": "Pseudoepitheliomatous keratotic balanitis",
                "top_differential": "[]",
                "recommended_next_step": "Excision",
                "confidence": "0.8",
                "evidence_summary": "hyperkeratosis",
                "uncertainty_or_missing_information": "",
            },
        ],
    )
    _write_tsv(
        pro_results_path,
        [
            {
                "case_id": "transformed_PMC10399123",
                "model": "deepseek-v4-pro",
                "final_diagnosis": "MOGAD",
                "top_differential": "[\"MS\"]",
                "recommended_next_step": "Rituximab",
                "confidence": "0.82",
                "evidence_summary": "[\"demyelination\"]",
                "uncertainty_or_missing_information": "[\"MOG titer\"]",
            },
            {
                "case_id": "native_PMC3122590",
                "model": "deepseek-v4-pro",
                "final_diagnosis": "Pseudoepitheliomatous keratotic balanitis",
                "top_differential": "[]",
                "recommended_next_step": "Excision",
                "confidence": "0.9",
                "evidence_summary": "hyperkeratosis",
                "uncertainty_or_missing_information": "",
            },
        ],
    )
    _write_tsv(
        flash_scores_path,
        [
            {
                "case_id": "transformed_PMC10399123",
                "model": "deepseek-v4-flash",
                "score_status": "fail",
                "diagnosis_status": "incorrect",
                "next_step_status": "partial",
                "rationale_status": "incorrect",
                "expected_key_answer": "Pediatric-onset multiple sclerosis",
                "expected_next_step": "MS disease-modifying therapy",
                "rationale": "Anchored on MOGAD.",
            },
            {
                "case_id": "native_PMC3122590",
                "model": "deepseek-v4-flash",
                "score_status": "fail",
                "diagnosis_status": "incorrect",
                "next_step_status": "partial",
                "rationale_status": "incorrect",
                "expected_key_answer": "Cutaneous horn",
                "expected_next_step": "Wide excision",
                "rationale": "Missed cutaneous horn.",
            },
        ],
    )
    _write_tsv(
        pro_scores_path,
        [
            {
                "case_id": "transformed_PMC10399123",
                "model": "deepseek-v4-pro",
                "score_status": "fail",
                "diagnosis_status": "incorrect",
                "next_step_status": "partial",
                "rationale_status": "incorrect",
                "expected_key_answer": "Pediatric-onset multiple sclerosis",
                "expected_next_step": "MS disease-modifying therapy",
                "rationale": "Low-titer transient MOG and CSF OCBs should suggest MS.",
            },
            {
                "case_id": "native_PMC3122590",
                "model": "deepseek-v4-pro",
                "score_status": "fail",
                "diagnosis_status": "incorrect",
                "next_step_status": "partial",
                "rationale_status": "incorrect",
                "expected_key_answer": "Cutaneous horn",
                "expected_next_step": "Wide excision",
                "rationale": "Misread pathology.",
            },
        ],
    )
    _write_tsv(
        pro_comparison_path,
        [
            {
                "case_id": "transformed_PMC10399123",
                "pro_score": "fail",
                "pro_dx_status": "incorrect",
                "pro_next_step_status": "partial",
                "pro_final_diagnosis": "MOGAD",
                "expected_key_answer": "Pediatric-onset multiple sclerosis",
                "pro_rationale": "Anchored on MOGAD.",
            },
            {
                "case_id": "native_PMC3122590",
                "pro_score": "fail",
                "pro_dx_status": "incorrect",
                "pro_next_step_status": "partial",
                "pro_final_diagnosis": "Pseudoepitheliomatous keratotic balanitis",
                "expected_key_answer": "Cutaneous horn",
                "pro_rationale": "Misread pathology.",
            },
        ],
    )

    return DeepSeekFailurePaths(
        ready_manifest=manifest_path,
        still_failed_ids=failed_ids_path,
        pro_comparison=pro_comparison_path,
        pro_results=pro_results_path,
        pro_scores=pro_scores_path,
        flash_results=flash_results_path,
        flash_scores=flash_scores_path,
    )


def _write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
