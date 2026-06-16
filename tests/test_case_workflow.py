import json
import tempfile
import unittest
from pathlib import Path

from clinical_harness.case_runner import evidence_from_pubmed_article, run_case
from clinical_harness.cases import load_clinical_case
from clinical_harness.ledger import RunLedger
from clinical_harness.schemas import (
    CandidateDiagnosis,
    ClinicalCase,
    EvidenceRecord,
    SearchQuery,
    StructuredAnswer,
)


class SchemaTests(unittest.TestCase):
    def test_schema_serializes_to_json(self) -> None:
        answer = StructuredAnswer(
            final_diagnosis="undetermined",
            differential=(
                CandidateDiagnosis(
                    diagnosis="example diagnosis",
                    aliases=("alias",),
                    supporting_evidence=("pubmed:1",),
                ),
            ),
        )

        payload = answer.to_dict()
        encoded = json.dumps(payload, sort_keys=True)

        self.assertIn("example diagnosis", encoded)
        self.assertEqual(payload["differential"][0]["aliases"], ["alias"])


class CaseLoadingTests(unittest.TestCase):
    def test_load_clinical_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.json"
            path.write_text(
                json.dumps(
                    {
                        "case_id": "case-1",
                        "title": "Synthetic case",
                        "prompt": "A synthetic neurologic prompt.",
                        "answer_key": {"final_diagnosis": "example"},
                        "metadata": {
                            "source_family": "synthetic",
                            "source_exclusion": {"pmid": "1"},
                        },
                    }
                ),
                encoding="utf-8",
            )

            case = load_clinical_case(path)

        self.assertEqual(case.case_id, "case-1")
        self.assertEqual(case.source_exclusion()["pmid"], "1")

    def test_load_clinical_case_rejects_missing_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.json"
            path.write_text(json.dumps({"case_id": "case-1", "title": "Synthetic case"}), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_clinical_case(path)


class LedgerTests(unittest.TestCase):
    def test_ledger_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = RunLedger.create(
                out_dir=tmpdir,
                run_id="unit-run",
                case_id="case-1",
                case_path=Path(tmpdir) / "case.json",
                mode="pubmed_only",
                allowed_sources=("pubmed",),
            )
            query = SearchQuery(
                query_id="q1",
                query="seizure diagnosis neurology",
                source="pubmed",
                generated_by="template",
                intent="find similar cases",
            )
            evidence = EvidenceRecord(
                evidence_id="pubmed:1",
                source_api="pubmed",
                query_id="q1",
                query=query.query,
                rank=1,
                retrieved_at="2026-05-27T00:00:00Z",
                pmid="1",
            )
            answer = StructuredAnswer(final_diagnosis="undetermined")

            ledger.write_query(query)
            ledger.write_evidence(evidence)
            answer_path = ledger.write_answer(answer)
            ledger.update_manifest(status="completed", answer_path=str(answer_path))

            run_dir = Path(tmpdir) / "unit-run"
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            queries = (run_dir / "queries.jsonl").read_text(encoding="utf-8").strip().splitlines()
            evidence_lines = (run_dir / "evidence.jsonl").read_text(encoding="utf-8").strip().splitlines()

        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(len(queries), 1)
        self.assertEqual(len(evidence_lines), 1)


class CaseRunnerTests(unittest.TestCase):
    def test_run_case_without_retrieval_writes_artifacts(self) -> None:
        case_path = Path(__file__).resolve().parents[1] / "examples" / "cases" / "synthetic_neuro_case.json"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_case(
                case_path,
                mode="pubmed_only",
                out_dir=tmpdir,
                run_id="unit-case-run",
                retrieve=False,
            )
            run_dir = Path(tmpdir) / "unit-case-run"
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            queries = (run_dir / "queries.jsonl").read_text(encoding="utf-8").strip().splitlines()
            evidence = (run_dir / "evidence.jsonl").read_text(encoding="utf-8").strip()
            answer = json.loads((run_dir / "answer.json").read_text(encoding="utf-8"))

        self.assertEqual(result.run_id, "unit-case-run")
        self.assertEqual(manifest["status"], "completed")
        self.assertGreaterEqual(len(queries), 1)
        self.assertEqual(evidence, "")
        self.assertEqual(answer["final_diagnosis"], "undetermined")

    def test_source_excluded_mode_marks_matching_pubmed_article(self) -> None:
        case = ClinicalCase(
            case_id="case-1",
            title="Synthetic case",
            prompt="Prompt",
            metadata={"source_exclusion": {"pmid": "12345", "pmcid": "PMC999", "doi": "10.0000/example"}},
        )
        query = SearchQuery(
            query_id="q1",
            query="example",
            source="pubmed",
            generated_by="template",
            intent="test",
        )
        article = {
            "pmid": "12345",
            "pmcid": "PMC999",
            "doi": "10.0000/example",
            "title": "Original source",
            "publication_types": ["Case Reports"],
        }

        record = evidence_from_pubmed_article(
            article,
            query=query,
            rank=1,
            case=case,
            mode="pubmed_only_source_excluded",
        )

        self.assertTrue(record.original_source_match)
        self.assertTrue(record.excluded)
        self.assertEqual(record.exclusion_reason, "pmid")
        self.assertEqual(record.pmcid, "PMC999")


if __name__ == "__main__":
    unittest.main()
