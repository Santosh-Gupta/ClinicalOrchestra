import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clinical_harness.guided_eval import case_from_manifest_row
from clinical_harness.model_client import ChatCompletionResult
from clinical_harness.retrieval_guided_eval import (
    EvidenceSynthesis,
    HarnessConfig,
    RetrievalEvidence,
    RetrievalQuery,
    _anchor_contrast_query,
    _article_relevance,
    _closed_book_top5,
    _compact_final_answer_prompt,
    _enforce_closed_book_floor,
    _union_top5_from_samples,
    _extract_prompt_case_packet,
    _generate_final_answer,
    _ranked_relevant_evidence,
    build_retrieval_guided_final_prompt,
    build_retrieval_queries,
    build_frontier_query_plan_prompt,
    collect_pubmed_evidence,
    enrich_evidence_with_full_text,
    case_anchor_terms,
    frontier_query_plan_from_payload,
    retrieval_queries_from_frontier_plan,
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

    def test_frontier_query_plan_filters_shortcuts_and_builds_queries(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        plan = frontier_query_plan_from_payload(
            case,
            preset="mold_identification",
            max_queries=3,
            config=HarnessConfig(eval_mode=True),
            payload={
                "problem_representation": "Invasive fungal sinusitis.",
                "possible_diagnoses": [
                    {
                        "diagnosis": "Invasive Microascus sinusitis",
                        "supporting_case_facts": ["mold sinusitis"],
                        "refuting_or_missing_case_facts": ["sequencing not shown"],
                        "key_discriminator": "morphology or sequencing",
                        "current_weight": "medium",
                    }
                ],
                "initial_differential": [{"diagnosis": "Microascus sinusitis"}],
                "uncertainty_map": [{"question": "Which mold is supported?"}],
                "query_ideas": [
                    {"purpose": "unsafe", "query": "Photo Quiz Source Title PMC12710301"},
                    {"purpose": "organism discriminator", "query": "invasive mold sinusitis morphology conidia sequencing"},
                ],
                "reader_extraction_brief": "Extract organism-level mycology discriminators.",
                "skepticism_notes": ["Do not accept a mold genus without morphology or sequencing."],
            },
        )

        queries = retrieval_queries_from_frontier_plan(plan, max_queries=3)

        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].generated_by, "answerer_query_plan")
        self.assertIn("mold", queries[0].query.lower())
        self.assertNotIn("Photo Quiz Source Title", queries[0].query)
        self.assertEqual(plan.reader_extraction_brief, "Extract organism-level mycology discriminators.")
        self.assertEqual(plan.possible_diagnoses[0]["diagnosis"], "Invasive Microascus sinusitis")

    def test_frontier_query_plan_prompt_asks_for_diagnostic_state_before_queries_not_top5(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        prompt = build_frontier_query_plan_prompt(
            case,
            preset="mold_identification",
            max_queries=4,
            max_rounds=3,
        )

        self.assertIn("First, produce a CLOSED-BOOK diagnostic state", prompt)
        self.assertIn("do not force a top-5", prompt)
        self.assertIn('"possible_diagnoses"', prompt)
        self.assertLess(prompt.index("CLOSED-BOOK diagnostic state"), prompt.index("generate retrieval queries"))

    def test_frontier_query_plan_is_injected_with_skeptical_contract_and_provenance(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        plan = frontier_query_plan_from_payload(
            case,
            preset="mold_identification",
            max_queries=1,
            config=HarnessConfig(eval_mode=True),
            payload={
                "query_ideas": [{"purpose": "organism discriminator", "query": "invasive mold sinusitis sequencing"}],
                "reader_extraction_brief": "Extract organism-level mycology discriminators.",
            },
        )
        queries = retrieval_queries_from_frontier_plan(plan, max_queries=1)
        evidence = (
            RetrievalEvidence(
                evidence_id="pubmed:123",
                query_id="r1q1",
                rank=1,
                pmid="123",
                pmcid=None,
                doi=None,
                title="Mold sinusitis sequencing",
                journal=None,
                publication_year=None,
                publication_types=(),
                url=None,
                abstract_snippet="Sequencing can identify invasive molds.",
                relevance=3,
            ),
        )

        prompt = build_retrieval_guided_final_prompt(
            case,
            preset="mold_identification",
            evidence=evidence,
            queries=queries,
            query_plan=plan,
            config=HarnessConfig(skeptical_evidence_mode=True),
        )
        packet = _extract_prompt_case_packet(prompt) or {}

        self.assertIn("SKEPTICAL EVIDENCE CONTRACT", prompt)
        self.assertEqual(packet["frontier_query_plan"]["reader_extraction_brief"], "Extract organism-level mycology discriminators.")
        self.assertEqual(packet["retrieval_queries"][0]["generated_by"], "answerer_query_plan")
        self.assertEqual(packet["retrieved_evidence"][0]["query_provenance"], "answerer_query_plan")

    def test_bare_answer_preservation_injects_closed_book_prior(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        plan = frontier_query_plan_from_payload(
            case,
            preset="mold_identification",
            max_queries=1,
            config=HarnessConfig(eval_mode=True),
            payload={
                "problem_representation": "Invasive mold sinusitis.",
                "possible_diagnoses": [
                    {
                        "diagnosis": "Invasive Microascus sinusitis",
                        "supporting_case_facts": ["invasive mold sinusitis"],
                        "refuting_or_missing_case_facts": ["genus not confirmed"],
                        "key_discriminator": "sequencing and morphology",
                        "current_weight": "medium",
                    }
                ],
                "query_ideas": [{"purpose": "organism discriminator", "query": "invasive mold sequencing"}],
            },
        )

        prompt = build_retrieval_guided_final_prompt(
            case,
            preset="mold_identification",
            evidence=(),
            query_plan=plan,
            config=HarnessConfig(use_bare_answer_preservation=True),
        )
        packet = _extract_prompt_case_packet(prompt) or {}

        self.assertIn("CLOSED-BOOK PRIOR PRESERVATION", prompt)
        self.assertIn("closed_book_prior_audit", prompt)
        self.assertEqual(
            packet["closed_book_diagnostic_prior"]["high_or_medium_diagnoses"],
            ["Invasive Microascus sinusitis"],
        )

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


    def test_frontier_mode_runner_uses_answerer_query_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "manifest.jsonl"
            manifest.write_text(json.dumps(_manifest_row()) + "\n", encoding="utf-8")
            out_dir = root / "retrieval"
            client = _FrontierPlannerClient()

            rows = run_retrieval_guided_manifest_eval(
                manifest_path=manifest,
                out_dir=out_dir,
                retrieve=False,
                model_client=client,  # type: ignore[arg-type]
                max_queries=2,
                max_rounds=2,
                config=HarnessConfig(
                    use_answerer_query_planner=True,
                    skeptical_evidence_mode=True,
                    min_rounds=1,
                ),
            )

            queries = json.loads((out_dir / "next_native_PMC12710301.queries.json").read_text())
            plan = json.loads((out_dir / "next_native_PMC12710301.query_plan.json").read_text())
            prompt = (out_dir / "next_native_PMC12710301.retrieval_prompt.txt").read_text()

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].model_final_diagnosis, "Invasive Microascus sinusitis")
            self.assertEqual(queries[0]["generated_by"], "answerer_query_plan")
            self.assertEqual(plan["reader_extraction_brief"], "Extract mold sequencing and morphology discriminators.")
            self.assertIn("frontier_query_plan", prompt)
            self.assertIn("SKEPTICAL EVIDENCE CONTRACT", prompt)
            self.assertEqual(client.prompts[0].count("FRONTIER diagnostic planner"), 1)

    def test_skip_existing_preserves_floor_mutated_response_and_closed_book_rank(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "manifest.jsonl"
            manifest.write_text(json.dumps(_manifest_row()) + "\n", encoding="utf-8")
            out_dir = root / "retrieval"
            client = _FloorPersistenceClient()

            first = run_retrieval_guided_manifest_eval(
                manifest_path=manifest,
                out_dir=out_dir,
                retrieve=False,
                model_client=client,
                reader_client=client,
                judge=False,
                config=HarnessConfig(use_answerer_query_planner=True, use_bare_answer_preservation=True),
            )
            stored = json.loads((out_dir / "next_native_PMC12710301.retrieval_response.json").read_text())
            stored_ranked = stored["content"]["ranked_differential"]

            self.assertEqual(first[0].gold_rank, 4)
            self.assertEqual(first[0].closed_book_gold_rank, 1)
            self.assertEqual(stored["closed_book_gold_rank"], 1)
            self.assertTrue(any(item.get("floor_reinserted") for item in stored_ranked))

            second = run_retrieval_guided_manifest_eval(
                manifest_path=manifest,
                out_dir=out_dir,
                retrieve=False,
                model_client=_NoCallClient(),
                reader_client=_NoCallClient(),
                judge=False,
                skip_existing=True,
                config=HarnessConfig(use_answerer_query_planner=True, use_bare_answer_preservation=True),
            )

            self.assertEqual(second[0].gold_rank, first[0].gold_rank)
            self.assertEqual(second[0].closed_book_gold_rank, first[0].closed_book_gold_rank)

    def test_frontier_followup_does_not_fall_back_to_generic_preset_queries(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        queries = build_retrieval_queries(
            case,
            preset="general",
            round_index=2,
            max_queries=2,
            previous_queries=("diagnostic criteria differential diagnosis review",),
            evidence=(),
            synthesis=EvidenceSynthesis(case_id=case.case_id, preset="general", synthesis_round=1),
            config=HarnessConfig(use_answerer_query_planner=True),
        )

        self.assertEqual(queries, ())

    def test_frontier_followup_labels_reader_queries_not_preset_templates(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        queries = build_retrieval_queries(
            case,
            preset="general",
            round_index=2,
            max_queries=2,
            previous_queries=(),
            evidence=(),
            synthesis=EvidenceSynthesis(
                case_id=case.case_id,
                preset="general",
                synthesis_round=1,
                additional_queries=("invasive mold sequencing morphology discriminator",),
            ),
            config=HarnessConfig(use_answerer_query_planner=True),
        )

        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].generated_by, "reader_additional_query")


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


class ClosedBookFloorTests(unittest.TestCase):
    """The frontier do-no-harm floor: retrieval may add/promote but must not silently drop a
    closed-book candidate from the final top-5 (the dominant top-5 regression mechanism)."""

    def _payload(self, ranked: list[str], audit: list[dict] | None = None) -> dict:
        return {
            "ranked_differential": [{"rank": i + 1, "diagnosis": d} for i, d in enumerate(ranked)],
            "final_diagnosis": ranked[0] if ranked else None,
            "closed_book_prior_audit": audit or [],
        }

    def test_silently_dropped_closed_book_candidate_is_reinserted(self) -> None:
        # Model had the gold ("myasthenia gravis") closed-book but silently dropped it for retrieval mimics.
        closed_book = ["myasthenia gravis", "guillain-barre syndrome", "botulism"]
        payload = self._payload(["lambert-eaton syndrome", "tick paralysis", "ALS", "porphyria", "CIDP"])
        _enforce_closed_book_floor(payload, closed_book)
        finals = [d["diagnosis"].lower() for d in payload["ranked_differential"]]
        self.assertIn("myasthenia gravis", finals)  # re-inserted: would have been a top-5 loss
        self.assertLessEqual(len(payload["ranked_differential"]), 5)
        self.assertTrue(any(d.get("floor_reinserted") for d in payload["ranked_differential"]))

    def test_explicitly_excluded_candidate_is_not_reinserted(self) -> None:
        closed_book = ["myasthenia gravis", "botulism"]
        payload = self._payload(
            ["lambert-eaton syndrome", "tick paralysis", "ALS", "porphyria", "CIDP"],
            audit=[{"diagnosis": "myasthenia gravis", "final_status": "excluded",
                    "case_matched_reason": "anti-AChR negative and decrement absent"}],
        )
        _enforce_closed_book_floor(payload, closed_book)
        finals = [d["diagnosis"].lower() for d in payload["ranked_differential"]]
        self.assertNotIn("myasthenia gravis", finals)  # model refuted it with a discriminator
        self.assertIn("botulism", finals)  # the non-excluded prior is still protected

    def test_retrieval_rescue_is_kept_when_budget_allows(self) -> None:
        # Closed-book gave 2 candidates; a retrieval rescue at rank 1 should survive alongside both priors.
        closed_book = ["catatonia", "depression"]
        payload = self._payload(["anti-NMDA receptor encephalitis", "catatonia", "depression"])
        _enforce_closed_book_floor(payload, closed_book)
        finals = [d["diagnosis"].lower() for d in payload["ranked_differential"]]
        self.assertEqual(finals[0], "anti-nmda receptor encephalitis")  # rescue preserved at rank 1
        self.assertIn("catatonia", finals)
        self.assertIn("depression", finals)

    def test_union_sampling_surfaces_a_sometimes_candidate(self) -> None:
        # The gold ("MERS") appears at rank 4 in only one of three samples; union should keep it in top-5.
        def pl(names):
            return {"ranked_differential": [{"rank": i + 1, "diagnosis": d} for i, d in enumerate(names)]}
        samples = [
            pl(["A", "B", "C", "MERS", "D"]),
            pl(["A", "B", "C", "D", "E"]),
            pl(["A", "B", "C", "D", "F"]),
        ]
        union = _union_top5_from_samples(samples)
        self.assertIn("MERS", union)  # best-rank 4 beats the rank-5 fillers E/F
        self.assertEqual(union[0], "A")  # consistent rank-1 stays first
        self.assertLessEqual(len(union), 5)

    def test_closed_book_top5_ranks_by_weight(self) -> None:
        plan = frontier_query_plan_from_payload(
            case_from_manifest_row(_manifest_row()),
            preset="general",
            payload={"possible_diagnoses": [
                {"diagnosis": "low one", "current_weight": "low"},
                {"diagnosis": "high one", "current_weight": "high"},
                {"diagnosis": "medium one", "current_weight": "medium"},
            ]},
            max_queries=4,
        )
        self.assertEqual(_closed_book_top5(plan)[:3], ["high one", "medium one", "low one"])


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


class FinalAnswerResilienceTests(unittest.TestCase):
    def test_compact_final_prompt_keeps_extractable_case_packet(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        plan = frontier_query_plan_from_payload(
            case,
            preset="general",
            max_queries=1,
            payload={
                "possible_diagnoses": [
                    {"diagnosis": "Invasive Microascus sinusitis", "current_weight": "medium"}
                ],
                "query_ideas": [{"query": "invasive mold sinusitis"}],
            },
        )
        full_prompt = build_retrieval_guided_final_prompt(
            case,
            preset="general",
            evidence=(),
            query_plan=plan,
            config=HarnessConfig(use_bare_answer_preservation=True),
        )
        packet = _extract_prompt_case_packet(full_prompt)
        self.assertIsNotNone(packet)

        compact_prompt = _compact_final_answer_prompt(
            packet or {},
            intro="Return ONLY one minified strict JSON object.",
        )
        compact_packet = _extract_prompt_case_packet(compact_prompt)

        self.assertIsNotNone(compact_packet)
        self.assertIn("Required schema exactly", compact_prompt)
        self.assertIn("ranked_differential", compact_prompt)
        self.assertIn("challenge_prompt", compact_packet or {})
        self.assertIn("closed_book_diagnostic_prior", compact_packet or {})
        self.assertIn("closed_book_prior_audit", compact_prompt)
        self.assertLess(len(compact_prompt), len(full_prompt))

    def test_truncated_final_answer_gets_compact_retry(self) -> None:
        case = case_from_manifest_row(_manifest_row())
        client = _FinalAnswerRetryClient()
        prompt = build_retrieval_guided_final_prompt(case, preset="general", evidence=())

        payload, response_payload, error, agreement = _generate_final_answer(
            client,
            prompt=prompt,
            case=case,
            preset="general",
            samples=1,
            sample_temperature=0.7,
            consensus_judge=None,
        )

        self.assertIsNone(error)
        self.assertIsNone(agreement)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["final_diagnosis"], "Invasive Microascus sinusitis")
        self.assertTrue(response_payload["recovered_from_invalid_json"])
        self.assertEqual(len(client.prompts), 2)
        self.assertIn("minified strict JSON", client.prompts[1])
        self.assertIn("Case packet", client.prompts[1])


class _FinalAnswerRetryClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def chat(self, *, prompt: str, temperature: float = 0.0, max_tokens: int = 4096) -> ChatCompletionResult:
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            return ChatCompletionResult(
                model="stub",
                content='{"problem_representation":"x","ranked_differential":[{"rank":1,',
                raw={"choices": [{"finish_reason": "length"}]},
                latency_ms=1,
            )
        return ChatCompletionResult(
            model="stub",
            content=json.dumps({
                "problem_representation": "Immunocompromised patient with mold sinusitis.",
                "retrieved_evidence_used": [],
                "discriminator_summary": [],
                "ranked_differential": [
                    {"rank": 1, "diagnosis": "Invasive Microascus sinusitis"},
                    {"rank": 2, "diagnosis": "Invasive Aspergillus sinusitis"},
                    {"rank": 3, "diagnosis": "Mucormycosis"},
                    {"rank": 4, "diagnosis": "Fusarium sinusitis"},
                    {"rank": 5, "diagnosis": "Scedosporium sinusitis"},
                ],
                "final_diagnosis": "Invasive Microascus sinusitis",
                "etiology": None,
                "recommended_next_step": "Confirm fungal identification and treat.",
                "key_papers": [],
                "confidence": "medium",
                "uncertainty_or_missing_information": [],
            }),
            raw={"choices": [{"finish_reason": "stop"}]},
            latency_ms=1,
        )


class _FloorPersistenceClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def chat(self, *, prompt: str, temperature: float = 0.0, max_tokens: int = 4096) -> ChatCompletionResult:
        self.prompts.append(prompt)
        if "FRONTIER diagnostic planner" in prompt:
            return ChatCompletionResult(
                model="stub",
                content=json.dumps({
                    "problem_representation": "Invasive fungal sinusitis.",
                    "possible_diagnoses": [
                        {"diagnosis": "Invasive Microascus sinusitis", "current_weight": "high"},
                        {"diagnosis": "Invasive Aspergillus sinusitis", "current_weight": "medium"},
                    ],
                    "query_ideas": [],
                    "reader_extraction_brief": "No retrieval needed.",
                }),
                raw={"choices": [{"finish_reason": "stop"}]},
                latency_ms=1,
            )
        return ChatCompletionResult(
            model="stub",
            content=json.dumps({
                "problem_representation": "Invasive fungal sinusitis.",
                "closed_book_prior_audit": [],
                "retrieved_evidence_used": [],
                "discriminator_summary": [],
                "ranked_differential": [
                    {"rank": 1, "diagnosis": "Mucormycosis"},
                    {"rank": 2, "diagnosis": "Fusarium sinusitis"},
                    {"rank": 3, "diagnosis": "Scedosporium sinusitis"},
                    {"rank": 4, "diagnosis": "Alternaria sinusitis"},
                    {"rank": 5, "diagnosis": "Candida sinusitis"},
                ],
                "final_diagnosis": "Mucormycosis",
                "etiology": None,
                "recommended_next_step": "Confirm organism.",
                "key_papers": [],
                "confidence": "medium",
                "uncertainty_or_missing_information": [],
            }),
            raw={"choices": [{"finish_reason": "stop"}]},
            latency_ms=1,
        )


class _NoCallClient:
    def chat(self, *, prompt: str, temperature: float = 0.0, max_tokens: int = 4096) -> ChatCompletionResult:
        raise AssertionError("skip_existing should not call the model")


class _FrontierPlannerClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def chat(self, *, prompt: str, temperature: float = 0.0, max_tokens: int = 4096) -> ChatCompletionResult:
        self.prompts.append(prompt)
        if "FRONTIER diagnostic planner" in prompt:
            return ChatCompletionResult(
                model="stub",
                content=json.dumps({
                    "problem_representation": "Invasive fungal sinusitis.",
                    "possible_diagnoses": [
                        {
                            "diagnosis": "Invasive Microascus sinusitis",
                            "supporting_case_facts": ["mold sinusitis"],
                            "refuting_or_missing_case_facts": ["organism not yet confirmed"],
                            "key_discriminator": "sequencing and morphology",
                            "current_weight": "medium",
                        },
                        {
                            "diagnosis": "Invasive Aspergillus sinusitis",
                            "supporting_case_facts": ["invasive mold sinusitis"],
                            "refuting_or_missing_case_facts": ["no Aspergillus-specific clue"],
                            "key_discriminator": "culture or histology",
                            "current_weight": "low",
                        },
                    ],
                    "initial_differential": [{"diagnosis": "Invasive Microascus sinusitis"}],
                    "uncertainty_map": [{"question": "Which mold is supported?"}],
                    "query_ideas": [
                        {
                            "purpose": "mold discriminator",
                            "source": "pubmed",
                            "query": "invasive mold sinusitis sequencing morphology",
                            "expected_evidence": "organism-level diagnostic clues",
                        }
                    ],
                    "reader_extraction_brief": "Extract mold sequencing and morphology discriminators.",
                    "skepticism_notes": ["Do not infer genus without case-matched lab evidence."],
                }),
                raw={"choices": [{"finish_reason": "stop"}]},
                latency_ms=1,
            )
        return ChatCompletionResult(
            model="stub",
            content=json.dumps({
                "problem_representation": "Invasive fungal sinusitis.",
                "retrieved_evidence_used": [],
                "discriminator_summary": [],
                "ranked_differential": [
                    {"rank": 1, "diagnosis": "Invasive Microascus sinusitis"},
                    {"rank": 2, "diagnosis": "Invasive Aspergillus sinusitis"},
                    {"rank": 3, "diagnosis": "Mucormycosis"},
                    {"rank": 4, "diagnosis": "Fusarium sinusitis"},
                    {"rank": 5, "diagnosis": "Scedosporium sinusitis"},
                ],
                "final_diagnosis": "Invasive Microascus sinusitis",
                "etiology": None,
                "recommended_next_step": "Confirm fungal identification and treat.",
                "key_papers": [],
                "confidence": "medium",
                "uncertainty_or_missing_information": [],
            }),
            raw={"choices": [{"finish_reason": "stop"}]},
            latency_ms=1,
        )


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
