import json
import tempfile
import unittest
from pathlib import Path

from clinical_harness.guided_eval import (
    answer_key_from_manifest_row,
    build_guided_final_prompt,
    case_from_manifest_row,
    lexical_score,
    run_guided_manifest_eval,
)


class GuidedEvalTests(unittest.TestCase):
    def test_case_from_manifest_redacts_source_metadata_from_prompt(self) -> None:
        row = _manifest_row()
        case = case_from_manifest_row(row)
        prompt = build_guided_final_prompt(case, preset="mold_identification")

        self.assertEqual(case.case_id, "next_native_PMC12710301")
        self.assertIn("mold_identification", prompt)
        self.assertIn("blocked_if_known", prompt)
        self.assertIn("A patient has invasive mold sinusitis.", prompt)
        self.assertNotIn("Photo Quiz Source Title", prompt)
        self.assertNotIn("PMC12710301", prompt)
        self.assertNotIn("10.0000/example", prompt)

    def test_answer_key_and_lexical_score_use_aliases(self) -> None:
        answer_key = answer_key_from_manifest_row(_manifest_row())

        self.assertEqual(answer_key["diagnosis"], "Invasive Microascus sinusitis")
        self.assertEqual(
            lexical_score("Microascus sinusitis with CNS spread", answer_key),
            "pass",
        )
        self.assertEqual(lexical_score("Cladophialophora infection", answer_key), "fail")

    def test_lexical_score_derives_common_biomedical_aliases(self) -> None:
        answer_key = {
            "diagnosis": (
                "Steroid-responsive lymphomatous infiltration (likely primary CNS lymphoma) "
                "involving the internal auditory canal and facial nerve"
            ),
            "aliases": (),
        }

        self.assertEqual(
            lexical_score("Primary CNS lymphoma (PCNSL) of the internal auditory canal", answer_key),
            "pass",
        )

    def test_lexical_score_allows_token_subset_aliases_with_modifiers(self) -> None:
        answer_key = {
            "diagnosis": "Chronic suppurative osteomyelitis of the maxilla (maxillary osteomyelitis)",
            "aliases": ("Chronic osteomyelitis of the anterior maxilla",),
        }

        self.assertEqual(
            lexical_score("Chronic suppurative osteomyelitis of the anterior maxilla", answer_key),
            "pass",
        )

    def test_lexical_score_does_not_pass_partial_melanoma_mention(self) -> None:
        answer_key = {
            "diagnosis": "Metastatic malignant melanoma (masseteric metastasis)",
            "aliases": ("Late-onset melanoma metastasis", "Masseteric recurrence of melanoma"),
        }

        self.assertEqual(
            lexical_score(
                "Differential includes metastatic melanoma and NF1-associated MPNST; tissue diagnosis required",
                answer_key,
            ),
            "fail",
        )

    def test_run_guided_manifest_eval_dry_run_writes_prompts_and_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "manifest.jsonl"
            manifest.write_text(json.dumps(_manifest_row()) + "\n", encoding="utf-8")
            out_dir = root / "guided"

            rows = run_guided_manifest_eval(
                manifest_path=manifest,
                out_dir=out_dir,
                dry_run=True,
            )

            prompt_path = out_dir / "next_native_PMC12710301.prompt.txt"
            results_path = out_dir / "guided_results.tsv"

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].preset, "mold_identification")
            self.assertEqual(rows[0].lexical_score, "not_run")
            self.assertTrue(prompt_path.exists())
            self.assertTrue(results_path.exists())
            self.assertIn("mold_identification_queries", prompt_path.read_text(encoding="utf-8"))


def _manifest_row() -> dict[str, str]:
    return {
        "case_id": "next_native_PMC12710301",
        "title": "Photo Quiz Source Title",
        "challenge_prompt": "A patient has invasive mold sinusitis.",
        "answer_rest": json.dumps(
            {
                "diagnosis": "Invasive Microascus sinusitis",
                "aliases": ["Microascus sinusitis"],
                "next_management_step": "Treat with antifungals.",
            }
        ),
        "pmcid": "PMC12710301",
        "doi": "10.0000/example",
        "license_key": "cc_by",
        "license_tier": "public",
    }


if __name__ == "__main__":
    unittest.main()
