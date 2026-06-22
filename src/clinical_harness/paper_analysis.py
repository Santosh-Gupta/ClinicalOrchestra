"""Context-isolated per-paper analysis for scaled retrieval.

Each retrieved paper is screened in its OWN model call (a cheap Flash agent), which reads the
abstract/full text and returns only the compact, diagnosis-relevant extract — or nothing if the
paper is irrelevant. The heavy raw text never re-enters the main diagnostic thread; only the small
distilled note does. This is what lets the harness screen hundreds or thousands of papers without
blowing the main context window, and it parallelizes (one paper per worker, bounded thread pool +
the shared NCBI/model rate limiting in ncbi.py / model_client.py).

Each analysis is given the evolving diagnostic state (the current differential / open questions) so
the extraction is targeted at the discriminator the main thread actually needs, and it can propose
follow-up queries that feed the standing query-strategist loop.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable

from .guided_eval import parse_json_object
from .model_client import OpenAICompatibleChatClient
from .schemas import JsonSerializableMixin


ModelCallRecorder = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class PaperAnalysis(JsonSerializableMixin):
    evidence_id: str
    pmid: str | None
    title: str | None
    relevant: bool
    relevant_excerpt: str | None = None
    discriminators: tuple[str, ...] = field(default_factory=tuple)
    supports: tuple[str, ...] = field(default_factory=tuple)
    refutes: tuple[str, ...] = field(default_factory=tuple)
    new_entity: str | None = None
    proposed_queries: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None


def build_paper_analysis_prompt(
    *, case_summary: str, differential_context: str, paper: dict[str, Any], clinical_reasoning: str = ""
) -> str:
    paper_view = {
        "title": paper.get("title"),
        "abstract": paper.get("abstract") or paper.get("abstract_snippet"),
        "full_text_snippet": paper.get("full_text_snippet"),
    }
    # The richer the clinical reasoning we hand the screener, the more nuanced its relevance judgment:
    # a paper is "relevant" only against THIS case's specific differential and the discriminators in
    # play, not the topic in general. Foreground that reasoning.
    reasoning_block = (
        f"Clinical reasoning so far (use this to judge nuanced relevance — a paper matters only if it "
        f"bears on THESE hypotheses or the discriminators in play):\n{clinical_reasoning}\n\n"
        if clinical_reasoning else ""
    )
    return (
        "You are a paper-screening subagent inside a clinical information-retrieval harness. You are "
        "given ONE paper plus the current diagnostic reasoning on a case. Decide whether this paper "
        "helps move THIS differential — confirm/refute a hypothesis, supply a discriminator that "
        "separates two candidates, surface a missed entity that fits the features, or name a "
        "confirmatory test. Extract ONLY what is relevant; if nothing bears on this case, return "
        "relevant=false with empty fields. Be strict — most papers are not relevant. Do not diagnose "
        "the case yourself; do not use the paper's identifiers as answer shortcuts; no hidden reasoning.\n\n"
        "Return strict JSON:\n"
        "{\n"
        '  "relevant": true|false,\n'
        '  "relevant_excerpt": "<=80 words of the directly useful content, or null>",\n'
        '  "discriminators": ["finding that distinguishes one candidate from another, tied to this case"],\n'
        '  "supports": ["hypothesis in this differential the paper supports"],\n'
        '  "refutes": ["hypothesis the paper argues against"],\n'
        '  "new_entity": "a diagnosis NOT yet in the differential that this paper suggests fits, or null",\n'
        '  "proposed_queries": ["a NEW focused PubMed query (<=6 terms) this paper suggests trying next"]\n'
        "}\n\n"
        + reasoning_block +
        f"Case summary:\n{case_summary}\n\n"
        f"Differential / discriminators in play:\n{differential_context}\n\n"
        f"Paper:\n{json.dumps(paper_view, ensure_ascii=False)}\n"
    )


def analyze_paper(
    client: OpenAICompatibleChatClient,
    *,
    paper: dict[str, Any],
    case_summary: str,
    differential_context: str,
    clinical_reasoning: str = "",
    model: str | None = None,
    max_tokens: int = 4096,  # reasoning models spend tokens before the answer (ADR-017)
    model_call_recorder: ModelCallRecorder | None = None,
) -> PaperAnalysis:
    evidence_id = str(paper.get("evidence_id") or paper.get("pmid") or "")
    pmid = paper.get("pmid")
    title = paper.get("title")
    prompt = build_paper_analysis_prompt(
        case_summary=case_summary, differential_context=differential_context, paper=paper,
        clinical_reasoning=clinical_reasoning,
    )
    max_attempts = max(1, int(os.getenv("PAPER_SCREENING_MAX_ATTEMPTS", "3")))
    retry_errors: list[str] = []
    result = None
    payload: dict[str, Any] | None = None
    successful_attempt = 1
    for attempt in range(1, max_attempts + 1):
        try:
            result = client.chat(prompt=prompt, temperature=0.0, max_tokens=max_tokens)
            payload = parse_json_object(result.content)
            successful_attempt = attempt
            break
        except Exception as exc:  # noqa: BLE001 - one bad attempt should not sink the paper.
            retry_errors.append(str(exc))
            retrying = attempt < max_attempts
            _record_model_call(
                model_call_recorder,
                stage="paper_screening",
                actor="retriever",
                title=(
                    f"Paper screening retrying · {evidence_id}"
                    if retrying
                    else f"Paper screening failed · {evidence_id}"
                ),
                prompt=prompt,
                evidence_id=evidence_id,
                pmid=pmid,
                paper_title=title,
                error=str(exc),
                max_tokens=max_tokens,
                temperature=0.0,
                attempt=attempt,
                max_attempts=max_attempts,
                retry_will_continue=retrying,
                retry_errors=tuple(retry_errors),
                status="warn" if retrying else "error",
            )
            if retrying:
                time.sleep(min(2.0, 0.5 * attempt))
                continue
            return PaperAnalysis(evidence_id=evidence_id, pmid=pmid, title=title, relevant=False, error=str(exc))

    assert payload is not None
    assert result is not None

    def _strs(key: str) -> tuple[str, ...]:
        v = payload.get(key)
        return tuple(s for s in v if isinstance(s, str)) if isinstance(v, list) else ()

    excerpt = payload.get("relevant_excerpt")
    new_entity = payload.get("new_entity")
    _record_model_call(
        model_call_recorder,
        stage="paper_screening",
        actor="retriever",
        title=f"Paper screening · {evidence_id}",
        prompt=prompt,
        evidence_id=evidence_id,
        pmid=pmid,
        paper_title=title,
        result=result,
        parsed=payload,
        max_tokens=max_tokens,
        temperature=0.0,
        attempt=successful_attempt,
        max_attempts=max_attempts,
        recovered_from_error=bool(retry_errors),
        retry_errors=tuple(retry_errors),
    )
    return PaperAnalysis(
        evidence_id=evidence_id,
        pmid=pmid,
        title=title,
        relevant=bool(payload.get("relevant")),
        relevant_excerpt=excerpt if isinstance(excerpt, str) and excerpt.strip() else None,
        discriminators=_strs("discriminators"),
        supports=_strs("supports"),
        refutes=_strs("refutes"),
        new_entity=new_entity if isinstance(new_entity, str) and new_entity.strip() else None,
        proposed_queries=_strs("proposed_queries"),
    )


def analyze_papers(
    client: OpenAICompatibleChatClient,
    *,
    papers: list[dict[str, Any]],
    case_summary: str,
    differential_context: str,
    clinical_reasoning: str = "",
    model: str | None = None,
    concurrency: int = 8,
    keep_irrelevant: bool = False,
    model_call_recorder: ModelCallRecorder | None = None,
) -> tuple[PaperAnalysis, ...]:
    """Screen many papers in parallel, returning only the relevant analyses by default.

    Concurrency is bounded; the model client handles 429 backoff and (for rate-limited providers) a
    shared RPM/TPM limiter, so this stays within the account ceiling even at high paper counts.
    """
    if not papers:
        return ()

    def _one(paper: dict[str, Any]) -> PaperAnalysis:
        return analyze_paper(
            client, paper=paper, case_summary=case_summary,
            differential_context=differential_context, clinical_reasoning=clinical_reasoning, model=model,
            model_call_recorder=model_call_recorder,
        )

    results: list[PaperAnalysis | None] = [None] * len(papers)
    if concurrency > 1 and len(papers) > 1:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            future_to_idx = {pool.submit(_one, p): i for i, p in enumerate(papers)}
            for fut in as_completed(future_to_idx):
                results[future_to_idx[fut]] = fut.result()
    else:
        results = [_one(p) for p in papers]
    analyses = [r for r in results if r is not None]
    if keep_irrelevant:
        return tuple(analyses)
    return tuple(a for a in analyses if a.relevant)


def _record_model_call(
    recorder: ModelCallRecorder | None,
    *,
    stage: str,
    actor: str,
    title: str,
    prompt: str,
    evidence_id: str | None = None,
    pmid: str | None = None,
    paper_title: str | None = None,
    result: Any | None = None,
    parsed: dict[str, Any] | None = None,
    error: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    attempt: int | None = None,
    max_attempts: int | None = None,
    retry_will_continue: bool = False,
    recovered_from_error: bool = False,
    retry_errors: tuple[str, ...] = (),
    status: str | None = None,
) -> None:
    if recorder is None:
        return
    raw = getattr(result, "raw", None) if result is not None else None
    usage = raw.get("usage") if isinstance(raw, dict) and isinstance(raw.get("usage"), dict) else None
    recorder(
        {
            "stage": stage,
            "actor": actor,
            "title": title,
            "prompt": prompt,
            "prompt_chars": len(prompt),
            "model": getattr(result, "model", None) if result is not None else None,
            "latency_ms": getattr(result, "latency_ms", None) if result is not None else None,
            "usage": usage,
            "response_text": getattr(result, "content", None) if result is not None else None,
            "parsed_json": parsed,
            "raw": raw,
            "error": error,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "retry_will_continue": retry_will_continue,
            "recovered_from_error": recovered_from_error,
            "retry_errors": list(retry_errors),
            "status": status,
            "evidence_id": evidence_id,
            "pmid": pmid,
            "paper_title": paper_title,
        }
    )
