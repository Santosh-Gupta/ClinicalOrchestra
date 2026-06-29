import json
import unittest
from dataclasses import dataclass

from clinical_harness.paper_analysis import analyze_paper, analyze_papers, build_paper_analysis_prompt


@dataclass
class _Result:
    content: str


class _StubClient:
    """Returns a queued JSON content per chat call; raises if told to."""

    def __init__(self, payloads):
        self._payloads = list(payloads)

    def chat(self, *, prompt, temperature=0.0, max_tokens=2048):
        item = self._payloads.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, str):
            return _Result(content=item)
        return _Result(content=json.dumps(item))


class PaperAnalysisTests(unittest.TestCase):
    def test_relevant_paper_extracts_compact_note(self) -> None:
        client = _StubClient([{
            "relevant": True,
            "relevant_excerpt": "HSV-1 encephalitis can present without fever or classic MRI in elderly.",
            "discriminators": ["CSF HSV PCR positive"],
            "supports": ["HSV encephalitis"],
            "refutes": ["autoimmune encephalitis"],
            "candidate_diagnoses": ["HSV encephalitis"],
            "proposed_queries": ["HSV encephalitis atypical elderly"],
        }])
        a = analyze_paper(client, paper={"evidence_id": "pubmed:1", "pmid": "1", "title": "HSV review"},
                          case_summary="elderly encephalopathy", differential_context="AE vs HSV")
        self.assertTrue(a.relevant)
        self.assertIn("HSV-1", a.relevant_excerpt)
        self.assertEqual(a.supports, ("HSV encephalitis",))
        self.assertEqual(a.candidate_diagnoses, ("HSV encephalitis",))
        self.assertEqual(a.proposed_queries, ("HSV encephalitis atypical elderly",))

    def test_model_call_recorder_gets_prompt_and_parsed_payload(self) -> None:
        calls = []
        client = _StubClient([{
            "relevant": True,
            "relevant_excerpt": "useful",
            "discriminators": ["marker"],
        }])
        analyze_paper(
            client,
            paper={"evidence_id": "pubmed:1", "pmid": "1", "title": "HSV review"},
            case_summary="elderly encephalopathy",
            differential_context="AE vs HSV",
            model_call_recorder=calls.append,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["stage"], "paper_screening")
        self.assertEqual(calls[0]["evidence_id"], "pubmed:1")
        self.assertIn("elderly encephalopathy", calls[0]["prompt"])
        self.assertEqual(calls[0]["parsed_json"]["discriminators"], ["marker"])

    def test_irrelevant_paper_is_filtered_out(self) -> None:
        client = _StubClient([
            {"relevant": True, "relevant_excerpt": "useful", "discriminators": ["x"]},
            {"relevant": False, "relevant_excerpt": None},
        ])
        papers = [{"evidence_id": "a", "pmid": "1", "title": "useful"},
                  {"evidence_id": "b", "pmid": "2", "title": "noise"}]
        kept = analyze_papers(client, papers=papers, case_summary="c", differential_context="d", concurrency=1)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].evidence_id, "a")

    def test_error_in_one_paper_is_isolated(self) -> None:
        client = _StubClient([RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom")])
        a = analyze_paper(client, paper={"evidence_id": "x", "pmid": "9", "title": "t"},
                          case_summary="c", differential_context="d")
        self.assertFalse(a.relevant)
        self.assertIn("boom", a.error)

    def test_paper_screening_retries_bad_model_json(self) -> None:
        calls = []
        client = _StubClient([
            "",
            {"relevant": True, "relevant_excerpt": "fixed on retry", "discriminators": ["marker"]},
        ])
        a = analyze_paper(
            client,
            paper={"evidence_id": "x", "pmid": "9", "title": "t"},
            case_summary="c",
            differential_context="d",
            model_call_recorder=calls.append,
        )

        self.assertTrue(a.relevant)
        self.assertEqual(a.relevant_excerpt, "fixed on retry")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["status"], "warn")
        self.assertTrue(calls[0]["retry_will_continue"])
        self.assertTrue(calls[1]["recovered_from_error"])
        self.assertEqual(calls[1]["attempt"], 2)

    def test_prompt_includes_state_and_strictness(self) -> None:
        p = build_paper_analysis_prompt(case_summary="CS", differential_context="DIFF",
                                        paper={"title": "T", "abstract": "A"})
        self.assertIn("CS", p)
        self.assertIn("DIFF", p)
        self.assertIn("most papers are not relevant", p)
        self.assertIn('"candidate_diagnoses"', p)


if __name__ == "__main__":
    unittest.main()
