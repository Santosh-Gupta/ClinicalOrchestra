import json
import unittest
from dataclasses import dataclass

from clinical_harness.diagnostic_ensemble import (
    DIAGNOSTIC_ANGLES,
    aggregate_proposed_queries,
    build_angle_prompt,
    consolidate,
    run_angle,
    run_angles,
    run_ensemble,
)


@dataclass
class _Result:
    content: str


class _StubClient:
    """Returns a queued payload per chat call; dict -> JSON, Exception -> raise."""

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = 0

    def chat(self, *, prompt, temperature=0.0, max_tokens=2048):
        self.calls += 1
        item = self._payloads.pop(0)
        if isinstance(item, Exception):
            raise item
        return _Result(content=json.dumps(item))


class EnsembleTests(unittest.TestCase):
    def test_angle_prompt_is_scoped(self) -> None:
        p = build_angle_prompt("exposure_iatrogenic", case_summary="CS")
        self.assertIn("drug timeline", p)
        self.assertIn("CS", p)
        self.assertIn("Stay strictly in your angle", p)

    def test_run_angle_parses_candidates_and_queries(self) -> None:
        client = _StubClient([{
            "candidates": [{"diagnosis": "valproate-risperidone interaction", "rationale": "timeline", "discriminator_wanted": "ammonia"}],
            "must_exclude": [],
            "proposed_queries": ["valproate risperidone interaction"],
        }])
        c = run_angle(client, "exposure_iatrogenic", case_summary="x")
        self.assertEqual(c.candidates[0]["diagnosis"], "valproate-risperidone interaction")
        self.assertEqual(c.proposed_queries, ("valproate risperidone interaction",))

    def test_angle_error_is_isolated(self) -> None:
        client = _StubClient([RuntimeError("boom")])
        c = run_angle(client, "tempo", case_summary="x")
        self.assertIsNotNone(c.error)
        self.assertEqual(c.candidates, ())

    def test_run_angles_runs_all_and_preserves_order(self) -> None:
        # one payload per angle (sequential to keep order deterministic in the stub)
        payloads = [{"candidates": [{"diagnosis": a}], "proposed_queries": [f"q {a}"]} for a in DIAGNOSTIC_ANGLES]
        client = _StubClient(payloads)
        contribs = run_angles(client, case_summary="x", concurrency=1)
        self.assertEqual(tuple(c.angle for c in contribs), tuple(DIAGNOSTIC_ANGLES))

    def test_consolidation_returns_final(self) -> None:
        from clinical_harness.diagnostic_ensemble import AngleContribution
        contribs = (AngleContribution(angle="cant_miss", must_exclude=["HSV encephalitis"]),)
        client = _StubClient([{
            "final_diagnosis": "HSV encephalitis until excluded",
            "consolidation_rationale": "can't-miss veto",
            "discriminator_to_retrieve_next": ["CSF HSV PCR"],
            "unresolved": False,
        }])
        res = consolidate(client, case_summary="x", contributions=contribs)
        self.assertEqual(res.final_diagnosis, "HSV encephalitis until excluded")
        self.assertEqual(res.discriminator_to_retrieve_next, ("CSF HSV PCR",))

    def test_run_ensemble_end_to_end(self) -> None:
        payloads = [{"candidates": [{"diagnosis": a}], "proposed_queries": []} for a in DIAGNOSTIC_ANGLES]
        payloads.append({"final_diagnosis": "X", "consolidation_rationale": "r", "unresolved": False})
        client = _StubClient(payloads)
        res = run_ensemble(client, case_summary="x", concurrency=1)
        self.assertEqual(res.final_diagnosis, "X")
        self.assertEqual(len(res.contributions), len(DIAGNOSTIC_ANGLES))

    def test_aggregate_proposed_queries_dedupes(self) -> None:
        from clinical_harness.diagnostic_ensemble import AngleContribution
        contribs = (
            AngleContribution(angle="a", proposed_queries=("HSV encephalitis", "valproate level")),
            AngleContribution(angle="b", proposed_queries=("hsv  encephalitis", "ammonia")),
        )
        self.assertEqual(aggregate_proposed_queries(contribs), ("HSV encephalitis", "valproate level", "ammonia"))


if __name__ == "__main__":
    unittest.main()
