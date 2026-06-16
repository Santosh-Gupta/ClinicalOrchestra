import unittest

from clinical_harness.judge import JudgeVerdict, build_judge_prompt, score_diagnosis


class _StubClient:
    """Records the prompt and returns a canned JSON content string."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.prompts: list[str] = []
        self.model = "stub-model"

    def chat(self, *, prompt: str, temperature: float = 0.0, max_tokens: int = 512):
        self.prompts.append(prompt)

        class _Result:
            content = self.content
            model = self.model

        return _Result()


class JudgeTests(unittest.TestCase):
    def test_empty_candidate_is_not_run(self) -> None:
        verdict = score_diagnosis(candidate="", expected="Multiple sclerosis")
        self.assertEqual(verdict.score, "not_run")
        self.assertEqual(verdict.method, "empty")

    def test_lexical_pass_short_circuits_without_judge(self) -> None:
        verdict = score_diagnosis(
            candidate="Pediatric-onset multiple sclerosis (MS)",
            expected="Pediatric-onset multiple sclerosis (MS)",
        )
        self.assertEqual(verdict.score, "pass")
        self.assertEqual(verdict.method, "lexical")

    def test_lexical_fail_without_judge_returns_fail(self) -> None:
        verdict = score_diagnosis(
            candidate="MOG antibody-associated disease",
            expected="Pediatric-onset multiple sclerosis",
        )
        self.assertEqual(verdict.score, "fail")
        self.assertEqual(verdict.method, "lexical")

    def test_lexical_pass_does_not_call_judge(self) -> None:
        client = _StubClient('{"equivalent": false}')
        verdict = score_diagnosis(
            candidate="Multiple sclerosis",
            expected="Multiple sclerosis",
            judge_client=client,
        )
        self.assertEqual(verdict.score, "pass")
        self.assertEqual(client.prompts, [])  # judge never invoked

    def test_judge_passes_qualifier_difference(self) -> None:
        client = _StubClient('{"equivalent": true, "match_type": "qualifier_difference", "rationale": "same"}')
        verdict = score_diagnosis(
            candidate="Metastatic melanoma",
            expected="Metastatic malignant melanoma (masseteric metastasis)",
            judge_client=client,
        )
        self.assertEqual(verdict.score, "pass")
        self.assertEqual(verdict.method, "judge")
        self.assertEqual(verdict.match_type, "qualifier_difference")
        self.assertEqual(len(client.prompts), 1)

    def test_judge_model_call_recorder_gets_prompt_and_parsed_payload(self) -> None:
        calls = []
        client = _StubClient('{"equivalent": true, "match_type": "synonym", "rationale": "same"}')
        score_diagnosis(
            candidate="ileal carcinoid",
            expected="well-differentiated small bowel neuroendocrine tumor",
            judge_client=client,
            model_call_recorder=calls.append,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["stage"], "judge_equivalence")
        self.assertIn("ileal carcinoid", calls[0]["prompt"])
        self.assertEqual(calls[0]["parsed_json"]["match_type"], "synonym")

    def test_judge_fails_wrong_species(self) -> None:
        client = _StubClient('{"equivalent": false, "match_type": "wrong_species", "rationale": "diff species"}')
        verdict = score_diagnosis(
            candidate="Saprochaete capitata",
            expected="Saprochaete clavata",
            judge_client=client,
        )
        self.assertEqual(verdict.score, "fail")
        self.assertEqual(verdict.match_type, "wrong_species")

    def test_judge_malformed_response_falls_back_to_lexical(self) -> None:
        import clinical_harness.judge as judge_mod

        self.addCleanup(setattr, judge_mod, "_JUDGE_RETRY_BACKOFF_SECONDS", judge_mod._JUDGE_RETRY_BACKOFF_SECONDS)
        judge_mod._JUDGE_RETRY_BACKOFF_SECONDS = 0  # don't sleep through retries in tests
        client = _StubClient("not json at all")
        verdict = score_diagnosis(
            candidate="Saprochaete capitata",
            expected="Saprochaete clavata",
            judge_client=client,
        )
        self.assertEqual(verdict.method, "judge_fallback_lexical")
        self.assertEqual(verdict.score, "fail")
        self.assertIsNotNone(verdict.judge_error)

    def test_build_judge_prompt_includes_aliases_and_candidate(self) -> None:
        prompt = build_judge_prompt(
            expected="AML with t(8;21)",
            aliases=("core binding factor AML",),
            candidate="AML with inv(16)",
        )
        self.assertIn("AML with t(8;21)", prompt)
        self.assertIn("core binding factor AML", prompt)
        self.assertIn("AML with inv(16)", prompt)
        self.assertIsInstance(JudgeVerdict(score="pass", method="judge").to_dict(), dict)


if __name__ == "__main__":
    unittest.main()
