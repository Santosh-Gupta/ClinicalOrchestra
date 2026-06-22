"""Replay adapter: reconstruct a case timeline from on-disk artifacts.

This is the MVP data path. It reads the per-case artifacts produced by the
retrieval-guided eval (``*.queries.json``, ``*.evidence.json``,
``*.synthesis.json``, ``*.retrieval_response.json``, ``*.report.md``) plus the
aggregate ``retrieval_guided_results.jsonl`` row, and emits an ordered list of
:class:`~clinical_viewer.events.Event` objects shaped like an agent trace.

Known limitation: the evidence artifact does not record which query/round
retrieved each paper, so all evidence is attached to the first retrieval round.
When the harness gains a live emitter (see :mod:`live`), per-round attribution
will come for free and this heuristic can be dropped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..events import CaseArtifact, CaseTimeline, Event, EventType


ARTIFACTS: tuple[tuple[str, str, str], ...] = (
    ("events", "Native event ledger", ".events.jsonl"),
    ("queries", "Queries JSON", ".queries.json"),
    ("evidence", "Evidence JSON", ".evidence.json"),
    ("synthesis", "Synthesis JSON", ".synthesis.json"),
    ("retrieval_prompt", "Final prompt text", ".retrieval_prompt.txt"),
    ("retrieval_response", "Model response JSON", ".retrieval_response.json"),
    ("report", "Report Markdown", ".report.md"),
)

LEDGER_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("ledger_events", "Ledger events", "events.jsonl"),
    ("ledger_queries", "Ledger queries", "queries.jsonl"),
    ("ledger_evidence", "Ledger evidence", "evidence.jsonl"),
    ("ledger_answer", "Ledger answer", "answer.json"),
    ("ledger_manifest", "Ledger manifest", "manifest.json"),
)


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


class _Builder:
    """Accumulates events with monotonic ids/sequence numbers."""

    def __init__(self, run_id: str, case_id: str) -> None:
        self.run_id = run_id
        self.case_id = case_id
        self._events: list[Event] = []

    def add(
        self,
        type: EventType,
        actor: str,
        title: str,
        *,
        round: int | None = None,
        summary: str | None = None,
        status: str = "ok",
        payload: dict[str, Any] | None = None,
    ) -> None:
        seq = len(self._events)
        self._events.append(
            Event(
                id=f"e{seq:04d}",
                seq=seq,
                run_id=self.run_id,
                case_id=self.case_id,
                round=round,
                type=type,
                actor=actor,  # type: ignore[arg-type]
                title=title,
                summary=summary,
                status=status,  # type: ignore[arg-type]
                payload=payload or {},
            )
        )

    @property
    def events(self) -> list[Event]:
        return self._events


def build_case_timeline(run_dir: Path, run_id: str, case_id: str) -> CaseTimeline:
    """Reconstruct the full event timeline for one case."""

    native_events = _read_native_events(run_dir / f"{case_id}.events.jsonl")
    if native_events:
        result = _load_result_row(run_dir, case_id)
        answer_payload = next(
            (event.payload for event in native_events if event.type == EventType.ANSWER),
            {},
        )
        judge_payload = next(
            (event.payload for event in native_events if event.type == EventType.JUDGE),
            {},
        )
        return CaseTimeline(
            run_id=run_id,
            case_id=case_id,
            title=case_id,
            trace_source="native",
            trace_notice="Native event ledger: includes the detailed prompt, model-call, retrieval, and tool-use events emitted during the run.",
            expected_diagnosis=result.get("expected_diagnosis") or judge_payload.get("expected_diagnosis"),
            model_diagnosis=(
                result.get("model_final_diagnosis")
                or judge_payload.get("model_final_diagnosis")
                or answer_payload.get("final_diagnosis")
            ),
            score=result.get("score") or judge_payload.get("score"),
            score_method=result.get("score_method") or judge_payload.get("score_method"),
            artifacts=_case_artifacts(run_dir, case_id),
            events=native_events,
        )

    ledger_timeline = _build_ledger_timeline(run_dir, run_id, case_id)
    if ledger_timeline is not None:
        return ledger_timeline

    queries = _read_json(run_dir / f"{case_id}.queries.json") or []
    evidence = _read_json(run_dir / f"{case_id}.evidence.json") or []
    synthesis = _read_json(run_dir / f"{case_id}.synthesis.json") or []
    response = _read_json(run_dir / f"{case_id}.retrieval_response.json") or {}
    report = _read_text(run_dir / f"{case_id}.report.md")
    result = _load_result_row(run_dir, case_id)
    prompt_payload = _prompt_payload(report_path=run_dir / f"{case_id}.retrieval_prompt.txt")

    content = response.get("content", {}) if isinstance(response, dict) else {}
    b = _Builder(run_id, case_id)

    b.add(
        EventType.CASE_STARTED,
        "runner",
        f"Case {case_id}",
        summary=result.get("preset") and f"preset: {result['preset']}" or None,
        payload={"preset": result.get("preset"), "expected_diagnosis": result.get("expected_diagnosis")},
    )

    problem = content.get("problem_representation")
    if problem:
        b.add(
            EventType.PROBLEM_REPRESENTATION,
            "planner",
            "Problem representation",
            summary=_truncate(problem, 140),
            payload={"text": problem},
        )

    # Group queries by round; union with synthesis rounds to order the timeline.
    rounds = sorted(
        {int(q.get("round_index", 1)) for q in queries}
        | {int(s.get("synthesis_round", 1)) for s in synthesis}
        or {1}
    )
    first_round = rounds[0] if rounds else 1

    for rnd in rounds:
        b.add(EventType.ROUND_STARTED, "system", f"Round {rnd}", round=rnd)

        round_queries = [q for q in queries if int(q.get("round_index", 1)) == rnd]
        for q in round_queries:
            b.add(
                EventType.QUERY_GENERATED,
                "planner",
                q.get("query", "(query)"),
                round=rnd,
                summary=f"{q.get('source', 'pubmed')} · {q.get('generated_by', '')}".strip(" ·"),
                payload={
                    "query": q.get("query"),
                    "source": q.get("source"),
                    "intent": q.get("intent"),
                    "generated_by": q.get("generated_by"),
                    "query_id": q.get("query_id"),
                },
            )
            linked_evidence = [e for e in evidence if e.get("query_id") == q.get("query_id")]
            if linked_evidence:
                b.add(
                    EventType.TOOL_CALL,
                    "retriever",
                    f"PubMed search · {_short_event_text(q.get('query') or q.get('query_id') or 'query')}",
                    round=rnd,
                    summary=f"pubmed_search · {len(linked_evidence)} returned",
                    payload={
                        "tool": "pubmed_search",
                        "source_api": "pubmed",
                        "query_id": q.get("query_id"),
                        "query": q.get("query"),
                        "attempted_query": q.get("query"),
                        "attempt": "replay",
                        "parameters": {"sort": "relevance"},
                        "returned_count": len(linked_evidence),
                        "total_matches": None,
                        "query_translation": None,
                        "pmids": [e.get("pmid") for e in linked_evidence if e.get("pmid")],
                        "output_evidence_ids": [e.get("evidence_id") for e in linked_evidence if e.get("evidence_id")],
                        "articles": [_tool_article_payload(e) for e in linked_evidence],
                    },
                )

        # Evidence has no round attribution on disk; attach to the first round.
        if rnd == first_round and evidence:
            kept = [e for e in evidence if not e.get("excluded")]
            full_text_evidence = [e for e in evidence if e.get("source_scope") == "full_text" or e.get("full_text_snippet")]
            b.add(
                EventType.SEARCH_EXECUTED,
                "retriever",
                f"Retrieved {len(evidence)} record(s)",
                round=rnd,
                summary=f"{len(kept)} kept after exclusion",
                payload={"total": len(evidence), "kept": len(kept)},
            )
            if full_text_evidence:
                b.add(
                    EventType.TOOL_CALL,
                    "retriever",
                    "PMC full-text fetch",
                    round=rnd,
                    summary=f"pmc_fetch · {len(full_text_evidence)} returned",
                    payload={
                        "tool": "pmc_fetch",
                        "source_api": "pmc",
                        "attempt": "replay",
                        "parameters": {
                            "pmcids": [e.get("pmcid") for e in full_text_evidence if e.get("pmcid")],
                            "retmode": "xml",
                        },
                        "requested_count": len([e for e in full_text_evidence if e.get("pmcid")]),
                        "returned_count": len(full_text_evidence),
                        "pmcids": [e.get("pmcid") for e in full_text_evidence if e.get("pmcid")],
                        "output_evidence_ids": [
                            e.get("evidence_id") for e in full_text_evidence if e.get("evidence_id")
                        ],
                        "articles": [_tool_article_payload(e) for e in full_text_evidence],
                    },
                )
            for ev in evidence:
                b.add(
                    EventType.EVIDENCE_RETRIEVED,
                    "retriever",
                    ev.get("title") or ev.get("evidence_id") or "(untitled)",
                    round=rnd,
                    summary=_evidence_summary(ev),
                    status="warn" if ev.get("excluded") else "ok",
                    payload={
                        "evidence_id": ev.get("evidence_id"),
                        "query_id": ev.get("query_id"),
                        "rank": ev.get("rank"),
                        "pmid": ev.get("pmid"),
                        "pmcid": ev.get("pmcid"),
                        "doi": ev.get("doi"),
                        "title": ev.get("title"),
                        "journal": ev.get("journal"),
                        "publication_year": ev.get("publication_year"),
                        "abstract_snippet": ev.get("abstract_snippet"),
                        "source_api": ev.get("source_api"),
                        "source_scope": ev.get("source_scope"),
                        "full_text_snippet": ev.get("full_text_snippet"),
                        "publication_types": ev.get("publication_types"),
                        "relevance": ev.get("relevance"),
                        "excluded": ev.get("excluded"),
                        "exclusion_reason": ev.get("exclusion_reason"),
                        "url": _pubmed_url(ev.get("pmid")),
                    },
                )

        for syn in [s for s in synthesis if int(s.get("synthesis_round", 1)) == rnd]:
            discs = syn.get("useful_discriminators", []) or []
            more = syn.get("more_retrieval_needed")
            b.add(
                EventType.SYNTHESIS,
                "synthesizer",
                f"Synthesis · {len(discs)} discriminator(s)",
                round=rnd,
                summary=(
                    "resolved" if syn.get("differential_resolved") else "more retrieval needed"
                    if more else "synthesized evidence"
                ),
                status="warn" if more else "ok",
                payload={
                    "useful_discriminators": discs,
                    "notes": syn.get("notes"),
                    "more_retrieval_needed": more,
                    "differential_resolved": syn.get("differential_resolved"),
                    "remaining_uncertainty": syn.get("remaining_uncertainty"),
                    "top_mimic_pair": syn.get("top_mimic_pair"),
                    "need_full_text_evidence_ids": syn.get("need_full_text_evidence_ids"),
                    "additional_queries": syn.get("additional_queries"),
                    "preset": syn.get("preset"),
                },
            )

        b.add(EventType.ROUND_COMPLETED, "system", f"Round {rnd} complete", round=rnd)

    if prompt_payload:
        b.add(
            EventType.PROMPT_BUILT,
            "diagnostician",
            "Final prompt assembled",
            summary=_prompt_summary(prompt_payload),
            payload=prompt_payload,
        )

    if response:
        model = response.get("model") if isinstance(response, dict) else None
        latency = response.get("latency_ms") if isinstance(response, dict) else None
        usage = _model_usage(response)
        b.add(
            EventType.MODEL_RESPONSE,
            "diagnostician",
            f"Model response · {model or 'unknown model'}",
            summary=_model_response_summary(model, latency, usage, response),
            status="error" if response.get("error") else "ok",
            payload={
                "model": model,
                "latency_ms": latency,
                "usage": usage,
                "error": response.get("error"),
                "raw_content": response.get("raw_content"),
                "raw": response.get("raw"),
                "content": response.get("content"),
                "self_consistency": response.get("self_consistency"),
            },
        )

    if content:
        final_dx = content.get("final_diagnosis") or "(no diagnosis)"
        b.add(
            EventType.ANSWER,
            "diagnostician",
            final_dx,
            summary=content.get("recommended_next_step") and _truncate(content["recommended_next_step"], 120),
            status="ok",
            payload={
                "final_diagnosis": final_dx,
                "etiology": content.get("etiology"),
                "confidence": content.get("confidence"),
                "recommended_next_step": content.get("recommended_next_step"),
                "ranked_differential": content.get("ranked_differential"),
                "discriminator_summary": content.get("discriminator_summary"),
                "key_papers": content.get("key_papers"),
                "report_markdown": report,
            },
        )

    if result:
        score = result.get("score")
        status = "pass" if score == "pass" else "fail" if score == "fail" else "info"
        b.add(
            EventType.JUDGE,
            "judge",
            f"Verdict: {score or 'unscored'}",
            summary=result.get("judge_match_type"),
            status=status,
            payload={
                "score": score,
                "score_method": result.get("score_method"),
                "judge_match_type": result.get("judge_match_type"),
                "judge_rationale": result.get("judge_rationale"),
                "expected_diagnosis": result.get("expected_diagnosis"),
                "model_final_diagnosis": result.get("model_final_diagnosis"),
                "lexical_score": result.get("lexical_score"),
                "agreement": result.get("agreement"),
                "samples": result.get("samples"),
            },
        )

    error = result.get("error")
    b.add(
        EventType.CASE_COMPLETED,
        "runner",
        "Case complete" if not error else "Case errored",
        status="error" if error else ("pass" if result.get("score") == "pass" else "ok"),
        payload={"error": error},
    )

    return CaseTimeline(
        run_id=run_id,
        case_id=case_id,
        title=case_id,
        trace_source="replay",
        trace_notice="Reconstructed from older run artifacts. It shows available queries, evidence, prompt, response, answer, and judge data, but not every live model/tool event.",
        expected_diagnosis=result.get("expected_diagnosis"),
        model_diagnosis=result.get("model_final_diagnosis") or content.get("final_diagnosis"),
        score=result.get("score"),
        score_method=result.get("score_method"),
        artifacts=_case_artifacts(run_dir, case_id),
        events=b.events,
    )


def _case_artifacts(run_dir: Path, case_id: str) -> list[CaseArtifact]:
    artifacts: list[CaseArtifact] = []
    for name, label, suffix in ARTIFACTS:
        path = run_dir / f"{case_id}{suffix}"
        if path.exists():
            artifacts.append(CaseArtifact(name=name, label=label, filename=path.name))
    if _is_ledger_case(run_dir, case_id):
        for name, label, filename in LEDGER_ARTIFACTS:
            path = run_dir / filename
            if path.exists():
                artifacts.append(CaseArtifact(name=name, label=label, filename=path.name))
    return artifacts


def _build_ledger_timeline(run_dir: Path, run_id: str, case_id: str) -> CaseTimeline | None:
    """Replay the deterministic ``RunLedger`` format written by ``case_runner``."""

    if not _is_ledger_case(run_dir, case_id):
        return None
    ledger_events = _read_jsonl(run_dir / "events.jsonl")
    if not ledger_events:
        return None

    manifest = _read_json(run_dir / "manifest.json") or {}
    answer = _read_json(run_dir / "answer.json") or {}
    b = _Builder(run_id, case_id)

    started = False
    completed = False
    for row in ledger_events:
        if not isinstance(row, dict):
            continue
        action = row.get("action")
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        actor = _ledger_actor(row.get("actor"))
        ts = row.get("timestamp")
        error = row.get("error")

        if action == "run_created":
            b.add(
                EventType.CASE_STARTED,
                "runner",
                f"Case {case_id}",
                summary=_ledger_run_summary(details, manifest),
                payload={
                    "action": action,
                    "actor": row.get("actor"),
                    "mode": details.get("mode") or manifest.get("mode"),
                    "allowed_sources": details.get("allowed_sources") or manifest.get("allowed_sources"),
                    "case_path": details.get("case_path") or manifest.get("case_path"),
                    "cli_args": details.get("cli_args") or manifest.get("cli_args"),
                    "manifest": manifest,
                },
            )
            b.events[-1].ts = ts
            started = True
        elif action == "case_loaded":
            if not started:
                b.add(EventType.CASE_STARTED, "runner", f"Case {case_id}", payload={"manifest": manifest})
                b.events[-1].ts = ts
                started = True
            b.add(
                EventType.NOTE,
                "runner",
                "Case loaded",
                summary=details.get("title"),
                payload=_ledger_payload(row, details),
            )
            b.events[-1].ts = ts
        elif action == "problem_represented":
            b.add(
                EventType.PROBLEM_REPRESENTATION,
                "planner",
                "Problem representation",
                summary=_problem_summary(details),
                payload=_ledger_payload(row, details),
            )
            b.events[-1].ts = ts
        elif action == "query_generated":
            b.add(
                EventType.QUERY_GENERATED,
                "planner",
                details.get("query") or "(query)",
                summary=details.get("intent") or details.get("generated_by"),
                payload=_ledger_payload(row, details),
            )
            b.events[-1].ts = ts
        elif action == "query_executed":
            returned = details.get("returned_articles")
            b.add(
                EventType.TOOL_CALL,
                "retriever",
                f"PubMed search · {_short_event_text(details.get('query') or row.get('input_ids', ['query'])[0])}",
                summary=f"pubmed_search · {returned if returned is not None else 0} returned",
                payload={
                    **_ledger_payload(row, details),
                    "tool": "pubmed_search",
                    "source_api": "pubmed",
                    "query": details.get("query"),
                    "attempted_query": details.get("query"),
                    "parameters": {"sort": "relevance"},
                    "returned_count": returned,
                    "total_matches": details.get("result_count"),
                    "output_query_ids": row.get("output_ids") or [],
                },
            )
            b.events[-1].ts = ts
        elif action in {"evidence_recorded", "evidence_excluded"}:
            excluded = action == "evidence_excluded" or bool(details.get("excluded"))
            title = details.get("title") or details.get("pmid") or _first(row.get("output_ids")) or "Evidence"
            b.add(
                EventType.EVIDENCE_RETRIEVED,
                "retriever",
                title,
                summary=_evidence_summary(details),
                status="warn" if excluded else "ok",
                payload={
                    **_ledger_payload(row, details),
                    "evidence_id": details.get("evidence_id") or _first(row.get("output_ids")),
                    "pmid": details.get("pmid"),
                    "pmcid": details.get("pmcid"),
                    "doi": details.get("doi"),
                    "title": details.get("title"),
                    "journal": details.get("journal"),
                    "publication_year": details.get("publication_year"),
                    "abstract_snippet": details.get("abstract_snippet"),
                    "original_source_match": details.get("original_source_match"),
                    "excluded": excluded,
                    "exclusion_reason": details.get("exclusion_reason"),
                    "url": _pubmed_url(details.get("pmid")),
                },
            )
            b.events[-1].ts = ts
        elif action == "answer_written":
            b.add(
                EventType.ANSWER,
                "diagnostician",
                _answer_title(answer),
                summary=_answer_summary(answer, details),
                payload={
                    **_ledger_payload(row, details),
                    "answer": answer,
                    "answer_path": details.get("answer_path") or manifest.get("answer_path"),
                    "confidence": details.get("confidence") or answer.get("confidence"),
                    "final_diagnosis": _answer_title(answer),
                    "citations": answer.get("citations"),
                    "differential": answer.get("differential"),
                    "recommended_next_step": answer.get("recommended_next_step"),
                },
            )
            b.events[-1].ts = ts
        elif action == "run_failed":
            b.add(
                EventType.ERROR,
                "runner",
                "Run failed",
                summary=error,
                status="error",
                payload=_ledger_payload(row, details),
            )
            b.events[-1].ts = ts
        else:
            b.add(
                EventType.NOTE,
                actor,
                str(action or "Ledger event"),
                summary=error,
                status="error" if error else "info",
                payload=_ledger_payload(row, details),
            )
            b.events[-1].ts = ts

    if b.events and b.events[-1].type == EventType.CASE_COMPLETED:
        completed = True
    if not completed:
        status = manifest.get("status")
        error = manifest.get("error")
        b.add(
            EventType.CASE_COMPLETED,
            "runner",
            "Case complete" if status != "error" else "Case errored",
            status="error" if status == "error" else "ok",
            payload={"status": status, "error": error, "manifest": manifest},
        )
        b.events[-1].ts = manifest.get("completed_at")

    return CaseTimeline(
        run_id=run_id,
        case_id=case_id,
        title=case_id,
        trace_source="replay",
        trace_notice=(
            "Reconstructed from the deterministic case-run ledger. It includes "
            "case loading, problem representation, generated queries, PubMed tool "
            "calls, recorded or excluded evidence, and the structured answer."
        ),
        expected_diagnosis=None,
        model_diagnosis=_answer_title(answer) if answer else None,
        score=None,
        score_method=None,
        artifacts=_case_artifacts(run_dir, case_id),
        events=b.events,
    )


def _is_ledger_case(run_dir: Path, case_id: str) -> bool:
    if not (run_dir / "events.jsonl").exists():
        return False
    manifest = _read_json(run_dir / "manifest.json") or {}
    ledger_case_id = manifest.get("case_id") or run_dir.name
    return str(ledger_case_id) == case_id


def _read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    rows: list[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _ledger_actor(actor: Any) -> str:
    actor_text = str(actor or "")
    if actor_text in {"case_loader", "runner"}:
        return "runner"
    if actor_text in {"template_runner"}:
        return "planner"
    if actor_text in {"pubmed", "retrieval_guard"}:
        return "retriever"
    return "system"


def _ledger_payload(row: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    return {
        **details,
        "ledger_event_id": row.get("event_id"),
        "ledger_actor": row.get("actor"),
        "ledger_action": row.get("action"),
        "input_ids": row.get("input_ids") or [],
        "output_ids": row.get("output_ids") or [],
        "error": row.get("error"),
    }


def _ledger_run_summary(details: dict[str, Any], manifest: dict[str, Any]) -> str | None:
    mode = details.get("mode") or manifest.get("mode")
    status = manifest.get("status")
    parts = [str(part) for part in (mode, status) if part]
    return " · ".join(parts) or None


def _problem_summary(details: dict[str, Any]) -> str | None:
    text = details.get("one_liner") or details.get("summary") or details.get("problem_representation")
    if isinstance(text, str):
        return _truncate(text, 140)
    key_features = details.get("key_features")
    if isinstance(key_features, list) and key_features:
        return _truncate("; ".join(str(item) for item in key_features[:3]), 140)
    return None


def _answer_title(answer: dict[str, Any]) -> str:
    candidates = answer.get("final_diagnosis") or answer.get("diagnosis") or answer.get("answer")
    if isinstance(candidates, str) and candidates:
        return candidates
    diagnoses = answer.get("diagnoses")
    if isinstance(diagnoses, list) and diagnoses:
        first = diagnoses[0]
        if isinstance(first, dict):
            name = first.get("name") or first.get("diagnosis")
            if isinstance(name, str) and name:
                return name
        if isinstance(first, str):
            return first
    differential = answer.get("differential")
    if isinstance(differential, list) and differential:
        first = differential[0]
        if isinstance(first, dict):
            name = first.get("diagnosis") or first.get("name")
            if isinstance(name, str) and name:
                return name
    return "(structured answer)"


def _answer_summary(answer: dict[str, Any], details: dict[str, Any]) -> str | None:
    confidence = details.get("confidence") or answer.get("confidence")
    if confidence:
        return f"confidence: {confidence}"
    return None


def _first(value: Any) -> Any:
    if isinstance(value, list | tuple) and value:
        return value[0]
    return None


def _load_result_row(run_dir: Path, case_id: str) -> dict[str, Any]:
    path = run_dir / "retrieval_guided_results.jsonl"
    if not path.exists():
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("case_id") == case_id:
            return row
    return {}


def _read_native_events(path: Path) -> list[Event]:
    if not path.exists():
        return []
    events: list[Event] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(Event.model_validate_json(line))
        except ValueError:
            continue
    events.sort(key=lambda event: event.seq)
    return events


def _prompt_payload(*, report_path: Path) -> dict[str, Any]:
    prompt = _read_text(report_path)
    if not prompt:
        return {}
    packet = _extract_case_packet(prompt)
    payload: dict[str, Any] = {
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "case_packet": packet,
    }
    if isinstance(packet, dict):
        payload.update(
            {
                "case_id": packet.get("case_id"),
                "harness_preset": packet.get("harness_preset"),
                "retrieval_rounds_allowed": packet.get("retrieval_rounds_allowed"),
                "retrieval_rounds_completed": packet.get("retrieval_rounds_completed"),
                "retrieved_evidence_count": len(packet.get("retrieved_evidence") or []),
                "screened_relevant_evidence_count": len(packet.get("screened_relevant_evidence") or []),
                "synthesis_count": len(packet.get("evidence_synthesis") or []),
                "specific_entities_count": len(packet.get("specific_entities_to_consider") or []),
                "finalization_gates_count": len(packet.get("finalization_gates") or []),
                "blocked_shortcuts": packet.get("blocked_shortcuts"),
                "finalization_gates": packet.get("finalization_gates"),
                "specific_entities_to_consider": packet.get("specific_entities_to_consider"),
                "screened_relevant_evidence": packet.get("screened_relevant_evidence"),
                "retrieved_evidence": packet.get("retrieved_evidence"),
                "evidence_synthesis": packet.get("evidence_synthesis"),
            }
        )
    return payload


def _extract_case_packet(prompt: str) -> dict[str, Any] | None:
    marker = "Case packet:"
    index = prompt.find(marker)
    if index < 0:
        return None
    raw = prompt[index + len(marker):].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _prompt_summary(payload: dict[str, Any]) -> str:
    parts = [f"{payload.get('prompt_chars', 0)} chars"]
    if payload.get("retrieved_evidence_count") is not None:
        parts.append(f"{payload['retrieved_evidence_count']} evidence injected")
    if payload.get("screened_relevant_evidence_count"):
        parts.append(f"{payload['screened_relevant_evidence_count']} screened notes")
    if payload.get("finalization_gates_count"):
        parts.append(f"{payload['finalization_gates_count']} gates")
    return " · ".join(parts)


def _model_usage(response: dict[str, Any]) -> dict[str, Any] | None:
    raw = response.get("raw")
    if isinstance(raw, dict) and isinstance(raw.get("usage"), dict):
        return raw["usage"]
    return None


def _model_response_summary(
    model: str | None,
    latency_ms: int | float | None,
    usage: dict[str, Any] | None,
    response: dict[str, Any],
) -> str:
    parts = []
    if latency_ms is not None:
        parts.append(f"{latency_ms} ms")
    if usage:
        total = usage.get("total_tokens")
        if total is not None:
            parts.append(f"{total} tokens")
    if response.get("error"):
        parts.append(str(response["error"])[:120])
    return " · ".join(parts) or (model or "model response")


def _tool_article_payload(ev: dict[str, Any]) -> dict[str, Any]:
    return {
        "pmid": ev.get("pmid"),
        "pmcid": ev.get("pmcid"),
        "doi": ev.get("doi"),
        "title": ev.get("title"),
        "journal": ev.get("journal"),
        "publication_year": ev.get("publication_year"),
        "url": ev.get("url") or _pubmed_url(ev.get("pmid")),
    }


def _evidence_summary(ev: dict[str, Any]) -> str | None:
    parts = []
    if ev.get("journal"):
        parts.append(ev["journal"])
    if ev.get("pmid"):
        parts.append(f"PMID {ev['pmid']}")
    if ev.get("excluded"):
        parts.append(f"excluded: {ev.get('exclusion_reason', 'source match')}")
    return " · ".join(parts) or None


def _pubmed_url(pmid: str | None) -> str | None:
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None


def _short_event_text(value: Any, max_chars: int = 110) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= max_chars else text[: max_chars - 3].rstrip() + "..."


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
