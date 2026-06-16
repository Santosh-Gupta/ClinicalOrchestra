import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clinical_harness.guided_eval import case_from_manifest_row
from clinical_harness.retrieval_guided_eval import (
    EvidenceSynthesis,
    HarnessConfig,
    RetrievalEvidence,
    RetrievalQuery,
    _anchor_contrast_query,
    _article_relevance,
    _ranked_relevant_evidence,
    build_retrieval_guided_final_prompt,
    build_retrieval_queries,
    collect_pubmed_evidence,
    enrich_evidence_with_full_text,
    case_anchor_terms,
    run_retrieval_guided_manifest_eval,
    should_run_another_round,
    source_exclusion_decision,
)


def _evidence(evidence_id: str, *, relevance: int, rank: int = 1, excluded: bool = False) -> RetrievalEvidence:
    return RetrievalEvidence(
        evidence_id=evidence_id,
        query_id="q1",
        rank=rank,
        pmid=evidence_id,
        pmcid=None,
        doi=None,
        title=evidence_id,
        journal=None,
        publication_year=None,
        publication_types=(),
        url=None,
        abstract_snippet=None,
        excluded=excluded,
        relevance=relevance,
    )


@dataclass(frozen=True)
class _StubPmcArticle:
    pmcid: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.payload


class RetrievalGuidedEvalTests(unittest.TestCase):
    def test_retrieval_queries_are_preset_specific_and_do_not_leak_source(self) -> None:
        case = case_from_manifest_row(_manifest_row())

        queries = build_retrieval_queries(case, preset="mold_identification", max_queries=2)

        self.assertEqual(len(queries), 2)
        joined = "\n".join(query.query for query in queries)
        # Preset-specific mold-identification vocabulary, without leaking the source title.
        self.assertTrue(any(term in joined.lower() for term in ("mold", "fungal", "conidia", "infection")))
        self.assertNotIn("Photo Quiz Source Title", joined)
        self.assertNotIn("PMC12710301", joined)
        self.assertNotIn("10.0000/example", joined)

    def test_source_exclusion_matches_original_source_metadata(self) -> None:
        case = case_from_manifest_row(_manifest_row())

        excluded, reason = source_exclusion_decision(
            case,
            {
                "title": "Unrelated title",
                "pmcid": "PMC12710301",
                "doi": None,
            },
        )

        self.assertTrue(excluded)
        self.assertEqual(reason, "source_pmcid_match")

    def test_retrieval_prompt_uses_evidence_but_redacts_case_identifier(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        prompt = build_retrieval_guided_final_prompt(case, preset="mold_identification", evidence=())

        self.assertIn("retrieved_evidence", prompt)
        self.assertIn("finalization_gates", prompt)
        self.assertIn("A patient has invasive mold sinusitis.", prompt)
        self.assertNotIn("PMC12710301", prompt)
        self.assertNotIn("Photo Quiz Source Title", prompt)
        self.assertNotIn("10.0000/example", prompt)

    def test_keratotic_retrieval_prompt_forces_morphology_base_histology_split(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        prompt = build_retrieval_guided_final_prompt(case, preset="keratotic_skin_lesion", evidence=())

        self.assertIn("Separate the clinical morphologic diagnosis", prompt)
        self.assertIn("cutaneous horn", prompt)
        self.assertIn("base histology", prompt)

    def test_retrieval_guided_eval_dry_run_writes_artifacts_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "manifest.jsonl"
            manifest.write_text(json.dumps(_manifest_row()) + "\n", encoding="utf-8")
            out_dir = root / "retrieval"
            emitted = []

            rows = run_retrieval_guided_manifest_eval(
                manifest_path=manifest,
                out_dir=out_dir,
                dry_run=True,
                retrieve=False,
                emitter=emitted.append,
            )

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].query_count, 2)
            self.assertEqual(rows[0].evidence_count, 0)
            self.assertEqual(rows[0].lexical_score, "not_run")
            self.assertTrue((out_dir / "next_native_PMC12710301.queries.json").exists())
            self.assertTrue((out_dir / "next_native_PMC12710301.evidence.json").exists())
            self.assertTrue((out_dir / "next_native_PMC12710301.retrieval_prompt.txt").exists())
            events_path = out_dir / "next_native_PMC12710301.events.jsonl"
            self.assertTrue(events_path.exists())
            events = [json.loads(line) for line in events_path.read_text().splitlines()]
            self.assertEqual([event["seq"] for event in events], list(range(len(events))))
            self.assertEqual(events[0]["type"], "case_started")
            self.assertEqual(events[-1]["type"], "case_completed")
            self.assertIn("prompt_built", [event["type"] for event in events])
            self.assertEqual([event["type"] for event in emitted], [event["type"] for event in events])
            (out_dir / "next_native_PMC12710301.retrieval_response.json").write_text(
                json.dumps({"content": {"final_diagnosis": "Invasive Microascus sinusitis"}}) + "\n",
                encoding="utf-8",
            )
            run_retrieval_guided_manifest_eval(
                manifest_path=manifest,
                out_dir=out_dir,
                dry_run=True,
                retrieve=False,
                skip_existing=True,
            )
            self.assertEqual([json.loads(line) for line in events_path.read_text().splitlines()], events)
            self.assertTrue((out_dir / "retrieval_guided_results.tsv").exists())

    def test_retrieval_guided_eval_dry_run_supports_multi_round_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "manifest.jsonl"
            manifest.write_text(json.dumps(_manifest_row()) + "\n", encoding="utf-8")
            out_dir = root / "retrieval"

            rows = run_retrieval_guided_manifest_eval(
                manifest_path=manifest,
                out_dir=out_dir,
                dry_run=True,
                retrieve=False,
                max_rounds=2,
            )

            queries = json.loads((out_dir / "next_native_PMC12710301.queries.json").read_text())
            syntheses = json.loads((out_dir / "next_native_PMC12710301.synthesis.json").read_text())
            prompt = (out_dir / "next_native_PMC12710301.retrieval_prompt.txt").read_text()

            self.assertEqual(len(rows), 1)
            self.assertGreaterEqual(len(queries), 2)
            self.assertGreaterEqual(len(syntheses), 1)
            self.assertIn("evidence_synthesis", prompt)
            self.assertIn("retrieval_rounds_allowed", prompt)


    def test_relevance_filter_drops_offtopic_when_enough_relevant(self) -> None:
        evidence = (
            _evidence("relevant-1", relevance=3, rank=2),
            _evidence("offtopic", relevance=0, rank=1),
            _evidence("relevant-2", relevance=5, rank=4),
            _evidence("relevant-3", relevance=1, rank=3),
        )
        ranked = _ranked_relevant_evidence(evidence)
        ids = [item.evidence_id for item in ranked]
        self.assertEqual(ids, ["relevant-2", "relevant-1", "relevant-3"])  # sorted by relevance, offtopic dropped

    def test_relevance_filter_keeps_offtopic_when_signal_is_weak(self) -> None:
        evidence = (
            _evidence("relevant-1", relevance=2),
            _evidence("offtopic", relevance=0),
        )
        ranked = _ranked_relevant_evidence(evidence)
        self.assertIn("offtopic", [item.evidence_id for item in ranked])  # last resort, not empty

    def test_relevance_filter_excludes_source_matches(self) -> None:
        evidence = (_evidence("blocked", relevance=9, excluded=True),)
        self.assertEqual(_ranked_relevant_evidence(evidence), [])

    def test_article_relevance_counts_anchor_overlap(self) -> None:
        anchor = case_anchor_terms(case_from_manifest_row(_manifest_row()), "mold_identification")
        on_topic = {"title": "Invasive mold sinusitis sequencing", "abstract": ""}
        off_topic = {"title": "Viscosupplementation for knee osteoarthritis", "abstract": ""}
        self.assertGreater(_article_relevance(on_topic, anchor), 0)
        self.assertEqual(_article_relevance(off_topic, anchor), 0)

    def test_ablation_gates_off_removes_finalization_gates_from_prompt(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        on = build_retrieval_guided_final_prompt(case, preset="mold_identification", evidence=())
        off = build_retrieval_guided_final_prompt(
            case, preset="mold_identification", evidence=(), config=HarnessConfig(use_gates=False)
        )
        self.assertIn("Do not stop at broad mold categories", on)  # gate text present by default
        self.assertNotIn("Do not stop at broad mold categories", off)  # removed when ablated
        self.assertIn('"finalization_gates": []', off)

    def test_ablation_contrast_query_off(self) -> None:
        # Use a case that actually raises the demyelination mimic, so the (now feature-conditional,
        # ADR-035) contrast query fires when enabled and is absent when ablated off.
        row = _manifest_row()
        row["challenge_prompt"] = "Longitudinally extensive myelitis with AQP4-IgG NMOSD versus MOGAD considerations."
        case = case_from_manifest_row(row)
        with_contrast = build_retrieval_queries(case, preset="demyelination", max_queries=6)
        without = build_retrieval_queries(
            case, preset="demyelination", max_queries=6, config=HarnessConfig(use_contrast_queries=False)
        )
        self.assertTrue(any("versus" in q.query for q in with_contrast))
        self.assertFalse(any("versus" in q.query for q in without))

    def test_contrast_query_is_inert_when_case_does_not_raise_the_mimic(self) -> None:
        # ADR-035: a mold case under the demyelination preset must NOT pull a demyelination contrast.
        case = case_from_manifest_row(_manifest_row())
        queries = build_retrieval_queries(case, preset="demyelination", max_queries=6)
        self.assertFalse(any("versus" in q.query for q in queries))

    def test_ablation_relevance_filter_off_keeps_offtopic_in_order(self) -> None:
        evidence = (
            _evidence("relevant-1", relevance=3, rank=2),
            _evidence("offtopic", relevance=0, rank=1),
            _evidence("relevant-2", relevance=5, rank=3),
        )
        ranked = _ranked_relevant_evidence(evidence, HarnessConfig(use_relevance_filter=False))
        # off-topic retained, original (insertion) order preserved, no relevance ranking
        self.assertEqual([e.evidence_id for e in ranked], ["relevant-1", "offtopic", "relevant-2"])

    def test_anchor_contrast_query_skips_placeholder_pairs(self) -> None:
        # mold_identification pair uses placeholder language -> no contrast query
        self.assertIsNone(_anchor_contrast_query("mold_identification"))
        # demyelination names concrete entities -> contrast query produced
        contrast = _anchor_contrast_query("demyelination")
        self.assertIsNotNone(contrast)
        self.assertIn("versus", contrast)
        self.assertIn("multiple sclerosis", contrast.lower())

    def test_pubmed_collection_records_tool_call_payload(self) -> None:
        from unittest.mock import patch

        case = case_from_manifest_row(_manifest_row())
        query = RetrievalQuery(
            query_id="r1q1",
            query="microascus sinusitis",
            source="pubmed",
            intent="find discriminator",
            round_index=1,
        )
        calls: list[dict] = []
        search_payload = {
            "query": "microascus sinusitis",
            "query_translation": '"microascus"[All Fields] AND "sinusitis"[All Fields]',
            "count": 7,
            "pmids": ["123"],
            "articles": [
                {
                    "pmid": "123",
                    "pmcid": "PMC999",
                    "doi": "10.1/example",
                    "title": "Microascus sinusitis",
                    "journal": "Medical Mycology",
                    "publication_year": "2024",
                    "publication_types": ["Case Reports"],
                    "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
                    "abstract": "Microascus can cause invasive sinusitis.",
                }
            ],
        }

        with patch("clinical_harness.retrieval_guided_eval.pubmed_search", return_value=search_payload):
            evidence = collect_pubmed_evidence(
                object(),  # type: ignore[arg-type]
                case,
                queries=(query,),
                articles_per_query=3,
                preset="mold_identification",
                config=HarnessConfig(use_relevance_filter=False),
                tool_call_recorder=calls.append,
            )

        self.assertEqual([item.evidence_id for item in evidence], ["pubmed:123"])
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["tool"], "pubmed_search")
        self.assertEqual(call["query_id"], "r1q1")
        self.assertEqual(call["returned_count"], 1)
        self.assertEqual(call["total_matches"], 7)
        self.assertEqual(call["pmids"], ["123"])
        self.assertEqual(call["output_evidence_ids"], ["pubmed:123"])
        self.assertEqual(call["parameters"], {"limit": 3, "sort": "relevance"})

    def test_full_text_enrichment_records_pmc_tool_call_payload(self) -> None:
        from unittest.mock import patch

        case = case_from_manifest_row(_manifest_row())
        evidence = (
            RetrievalEvidence(
                evidence_id="pubmed:123",
                query_id="r1q1",
                rank=1,
                pmid="123",
                pmcid="PMC999",
                doi="10.1/example",
                title="Microascus sinusitis",
                journal="Medical Mycology",
                publication_year="2024",
                publication_types=("Case Reports",),
                url="https://pubmed.ncbi.nlm.nih.gov/123/",
                abstract_snippet="abstract",
            ),
        )
        article = _StubPmcArticle(
            pmcid="PMC999",
            payload={
                "pmcid": "PMC999",
                "pmid": "123",
                "doi": "10.1/example",
                "title": "Microascus sinusitis",
                "journal": "Medical Mycology",
                "publication_year": "2024",
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC999/",
                "sections": [{"title": "Case presentation", "text": "Full text diagnostic details."}],
            },
        )
        calls: list[dict] = []

        with patch("clinical_harness.retrieval_guided_eval.fetch_pmc_articles", return_value=[article]):
            enriched = enrich_evidence_with_full_text(
                object(),  # type: ignore[arg-type]
                case,
                evidence=evidence,
                tool_call_recorder=calls.append,
            )

        self.assertEqual(enriched[0].source_scope, "full_text")
        self.assertIn("Full text diagnostic details", enriched[0].full_text_snippet or "")
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["tool"], "pmc_fetch")
        self.assertEqual(call["source_api"], "pmc")
        self.assertEqual(call["requested_count"], 1)
        self.assertEqual(call["returned_count"], 1)
        self.assertEqual(call["pmcids"], ["PMC999"])
        self.assertEqual(call["output_evidence_ids"], ["pubmed:123"])
        self.assertEqual(call["articles"][0]["section_count"], 1)


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


class ConcurrencyTests(unittest.TestCase):
    def _multi_case_manifest(self, root: Path, n: int) -> Path:
        manifest = root / "manifest.jsonl"
        lines = []
        for i in range(n):
            row = _manifest_row()
            row["case_id"] = f"case_{i:02d}"
            row["pmcid"] = f"PMC{1000+i}"
            lines.append(json.dumps(row))
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return manifest

    def test_concurrent_run_preserves_manifest_order_and_matches_sequential(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = self._multi_case_manifest(root, 8)

            seq = run_retrieval_guided_manifest_eval(
                manifest_path=manifest, out_dir=root / "seq", dry_run=True, retrieve=False, concurrency=1,
            )
            par = run_retrieval_guided_manifest_eval(
                manifest_path=manifest, out_dir=root / "par", dry_run=True, retrieve=False, concurrency=4,
            )

            self.assertEqual([r.case_id for r in seq], [f"case_{i:02d}" for i in range(8)])
            # Concurrent results must be in the same manifest order, not completion order.
            self.assertEqual([r.case_id for r in par], [r.case_id for r in seq])

    def test_one_bad_case_does_not_abort_the_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "manifest.jsonl"
            good = _manifest_row()
            good["case_id"] = "good_case"
            bad = _manifest_row()
            bad["case_id"] = "bad_case"
            del bad["answer_rest"]  # makes answer_key extraction raise inside the worker
            manifest.write_text(json.dumps(good) + "\n" + json.dumps(bad) + "\n", encoding="utf-8")

            rows = run_retrieval_guided_manifest_eval(
                manifest_path=manifest, out_dir=root / "out", dry_run=True, retrieve=False, concurrency=2,
            )

            by_id = {r.case_id: r for r in rows}
            self.assertEqual(len(rows), 2)
            self.assertIsNone(by_id["bad_case"].error and None)  # bad case present, not crashed
            self.assertEqual(by_id["bad_case"].preset, "error")
            self.assertIsNotNone(by_id["bad_case"].error)
            self.assertEqual(by_id["good_case"].preset != "error", True)

    def test_concurrency_must_be_positive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = self._multi_case_manifest(Path(tmpdir), 2)
            with self.assertRaises(ValueError):
                run_retrieval_guided_manifest_eval(
                    manifest_path=manifest, out_dir=Path(tmpdir) / "o", dry_run=True, retrieve=False, concurrency=0,
                )


class EvalModeTests(unittest.TestCase):
    def test_source_excluded_in_eval_mode_kept_in_doctor_mode(self) -> None:
        from clinical_harness.retrieval_guided_eval import source_exclusion_decision
        case = case_from_manifest_row(_manifest_row())  # source pmcid PMC12710301
        article = {"pmcid": "PMC12710301", "title": "whatever"}
        excluded_eval, reason = source_exclusion_decision(case, article, eval_mode=True)
        self.assertTrue(excluded_eval)
        self.assertEqual(reason, "source_pmcid_match")
        excluded_doctor, _ = source_exclusion_decision(case, article, eval_mode=False)
        self.assertFalse(excluded_doctor)

    def test_prompt_anticheat_clause_toggles_with_eval_mode(self) -> None:
        from clinical_harness.retrieval_guided_eval import build_retrieval_guided_final_prompt
        case = case_from_manifest_row(_manifest_row())
        p_eval = build_retrieval_guided_final_prompt(case, preset="general", evidence=(), config=HarnessConfig(eval_mode=True))
        p_doc = build_retrieval_guided_final_prompt(case, preset="general", evidence=(), config=HarnessConfig(eval_mode=False))
        self.assertIn("EVAL MODE (anti-cheat)", p_eval)
        self.assertNotIn("EVAL MODE (anti-cheat)", p_doc)
        self.assertIn("DOCTOR-ASSIST MODE", p_doc)
        # key_papers (cited report) must be requested in both modes
        self.assertIn("key_papers", p_eval)
        self.assertIn("key_papers", p_doc)

    def test_case_report_lists_cited_papers(self) -> None:
        import tempfile
        from clinical_harness.retrieval_guided_eval import _write_case_report
        case = case_from_manifest_row(_manifest_row())
        payload = {
            "final_diagnosis": "Invasive Microascus sinusitis",
            "recommended_next_step": "Antifungals",
            "key_papers": [{"title": "Microascus sinusitis review", "pmid": "12345678", "doi": "10.x/y",
                            "contribution": "named the organism-level discriminator"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.md"
            _write_case_report(path, case, payload)
            text = path.read_text()
        self.assertIn("Microascus sinusitis review", text)
        self.assertIn("pubmed.ncbi.nlm.nih.gov/12345678", text)
        self.assertIn("How it contributed", text)


class QueryFocusTests(unittest.TestCase):
    def test_long_query_is_capped_to_meaningful_terms(self) -> None:
        from clinical_harness.retrieval_guided_eval import _focus_query
        long_q = "subacute encephalopathy psychosis cognitive decline elderly normal MRI herpes simplex PCR autoimmune"
        focused = _focus_query(long_q)
        # Long ANDed PubMed queries return zero hits; ensure we trim to <= 8 meaningful terms.
        self.assertLessEqual(len(focused.split()), 8)
        self.assertIn("encephalopathy", focused)

    def test_short_query_is_unchanged(self) -> None:
        from clinical_harness.retrieval_guided_eval import _sanitize_query
        self.assertEqual(_sanitize_query("valproate risperidone interaction"), "valproate risperidone interaction")

    def test_minimal_query_is_two_terms(self) -> None:
        from clinical_harness.retrieval_guided_eval import _minimal_query
        self.assertEqual(len(_minimal_query("chronic progressive cerebellar ataxia adult onset").split()), 2)


class ClientResilienceTests(unittest.TestCase):
    def test_retry_delay_honors_retry_after_header(self) -> None:
        from clinical_harness.model_client import OpenAICompatibleChatClient
        client = OpenAICompatibleChatClient(api_key="k", base_url="http://x", model="m", backoff_cap_seconds=30.0)
        self.assertEqual(client._retry_delay(0, "5"), 5.0)
        self.assertEqual(client._retry_delay(0, "999"), 30.0)  # capped
        # Bad header falls back to jittered exponential backoff within the ceiling.
        self.assertLessEqual(client._retry_delay(2, "not-a-number"), 4.0)

    def test_ncbi_rate_limit_is_thread_safe(self) -> None:
        import threading
        from clinical_harness.ncbi import NcbiClient, NcbiConfig
        client = NcbiClient(NcbiConfig(min_interval_seconds=0.0))
        errors: list[Exception] = []

        def hammer() -> None:
            try:
                for _ in range(50):
                    client._respect_rate_limit()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=hammer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class AdaptiveRoundsTests(unittest.TestCase):
    ENOUGH = tuple(_evidence(f"e{i}", relevance=3, rank=i) for i in range(1, 6))  # 5 included

    def _synthesis(self, **kw) -> EvidenceSynthesis:
        base = dict(case_id="c", preset="general", synthesis_round=1)
        base.update(kw)
        return EvidenceSynthesis(**base)

    def test_stops_when_agent_resolves_differential(self) -> None:
        syn = self._synthesis(differential_resolved=True, more_retrieval_needed=False)
        self.assertFalse(should_run_another_round(
            preset="general", round_index=1, max_rounds=4, evidence=self.ENOUGH, synthesis=syn,
        ))

    def test_continues_when_agent_requests_new_query(self) -> None:
        syn = self._synthesis(more_retrieval_needed=True, additional_queries=("LCNEC vs adenocarcinoma IHC",))
        self.assertTrue(should_run_another_round(
            preset="general", round_index=1, max_rounds=4, evidence=self.ENOUGH, synthesis=syn,
            previous_queries=("initial query",),
        ))

    def test_convergence_guard_stops_when_query_already_run(self) -> None:
        # Agent wants more, but every proposed query was already executed -> no progress, stop.
        syn = self._synthesis(more_retrieval_needed=True, additional_queries=("Initial  Query",))
        self.assertFalse(should_run_another_round(
            preset="general", round_index=1, max_rounds=4, evidence=self.ENOUGH, synthesis=syn,
            previous_queries=("initial query",),
        ))

    def test_max_rounds_is_a_hard_cap(self) -> None:
        syn = self._synthesis(more_retrieval_needed=True, additional_queries=("brand new query",))
        self.assertFalse(should_run_another_round(
            preset="general", round_index=2, max_rounds=2, evidence=self.ENOUGH, synthesis=syn,
        ))

    def test_min_rounds_floor_forces_continuation(self) -> None:
        syn = self._synthesis(differential_resolved=True)
        self.assertTrue(should_run_another_round(
            preset="general", round_index=1, max_rounds=4, evidence=self.ENOUGH, synthesis=syn,
            config=HarnessConfig(min_rounds=2),
        ))

    def test_legacy_fixed_rounds_ignores_resolution_signal(self) -> None:
        # With adaptive off, a complex preset still gets its second look regardless of the signal.
        syn = self._synthesis(differential_resolved=True, more_retrieval_needed=False)
        self.assertTrue(should_run_another_round(
            preset="prion_sleep", round_index=1, max_rounds=2, evidence=self.ENOUGH, synthesis=syn,
            config=HarnessConfig(adaptive_rounds=False),
        ))


if __name__ == "__main__":
    unittest.main()
