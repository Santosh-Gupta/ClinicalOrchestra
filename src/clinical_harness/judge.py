"""Diagnostic-equivalence judging for benchmark scoring.

The original ``lexical_score`` proxy in :mod:`clinical_harness.guided_eval` only does
substring and token-subset matching. That produces *false negatives*: a model answer
that is clinically the same diagnosis as the answer key but phrased with different
qualifiers (grade, stage, anatomic location, extent) gets marked ``fail``. Concrete
examples observed in the Pro-failed manifest run:

- key ``Metastatic malignant melanoma (masseteric metastasis)`` vs model
  ``Metastatic melanoma (likely from prior cutaneous melanoma)`` -> same diagnosis.
- key ``Small bowel neuroendocrine tumor (well-differentiated, Grade 1, ...)`` vs model
  ``Small bowel neuroendocrine tumor (ileal NET)`` -> same diagnosis.
- key ``IDH-wildtype glioblastoma of the optic nerve (malignant optic glioma ...)`` vs
  model ``Malignant optic glioma (IDH-wildtype glioblastoma)`` -> same diagnosis.

This module adds an LLM judge that decides clinical equivalence at the level of
specificity the benchmark requires, while still *failing* wrong species, wrong genetic
subtype, wrong lineage, wrong entity, or answers too generic to capture the key
discriminator. The lexical scorer is kept as a cheap pre-pass: a lexical ``pass`` is
always accepted without spending a model call; only lexical ``fail`` / ``not_run`` are
escalated to the judge.

No new runtime dependencies: the judge reuses the standard-library OpenAI-compatible
chat client.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from .guided_eval import lexical_score, parse_json_object
from .model_client import OpenAICompatibleChatClient
from .schemas import JsonSerializableMixin


ModelCallRecorder = Callable[[dict[str, Any]], None]


_JUDGE_MAX_ATTEMPTS = 3
_JUDGE_RETRY_BACKOFF_SECONDS = 1.5


@dataclass(frozen=True)
class JudgeVerdict(JsonSerializableMixin):
    """Result of a single diagnostic-equivalence decision."""

    score: str  # "pass" | "fail" | "not_run"
    method: str  # "lexical" | "judge" | "judge_fallback_lexical" | "empty"
    match_type: str | None = None
    rationale: str | None = None
    judge_model: str | None = None
    judge_error: str | None = None


JUDGE_SYSTEM_RULES = (
    "You are a strict diagnostic-equivalence judge for a clinical benchmark. You compare a "
    "candidate final diagnosis against an answer key. You output only JSON. You never reveal hidden "
    "reasoning; output only the requested fields.\n\n"
    "Decide whether the candidate names the SAME disease entity as the answer key, at the level of "
    "specificity the key requires.\n\n"
    "Count as EQUIVALENT (equivalent=true):\n"
    "- The candidate matches the key but omits non-discriminating qualifiers such as tumor grade, "
    "stage, size, anatomic sub-site, laterality, extent of spread, or the named source of a "
    "metastasis (e.g. key 'metastatic malignant melanoma (masseteric metastasis)' vs candidate "
    "'metastatic melanoma').\n"
    "- The candidate uses a recognized synonym, eponym, or abbreviation of the same entity "
    "(e.g. 'malignant optic glioma of adulthood' == 'IDH-wildtype glioblastoma of the optic nerve'; "
    "'ileal carcinoid' == 'well-differentiated small bowel neuroendocrine tumor').\n\n"
    "Count as NOT equivalent (equivalent=false):\n"
    "- Different microbial/fungal SPECIES even within the same genus "
    "(e.g. 'Saprochaete capitata' != 'Saprochaete clavata'; 'Malassezia furfur' != 'Malassezia pachydermatis').\n"
    "- Different genetic/cytogenetic SUBTYPE of the same disease "
    "(e.g. 'AML with inv(16)' != 'AML with t(8;21)').\n"
    "- Different lineage or cell of origin (e.g. 'DLBCL/B-cell lymphoma' != 'myeloid sarcoma').\n"
    "- A different disease entity, even if a plausible mimic "
    "(e.g. 'MOGAD' != 'multiple sclerosis'; 'cardiac amyloidosis' != 'cardiac angiosarcoma').\n"
    "- The candidate is too generic to capture the key's discriminator "
    "(e.g. 'primary breast sarcoma, provisional' != 'mammary stromal (CD10+) sarcoma'; "
    "'fungal infection' != a named species). A candidate that only reaches the syndrome/category level "
    "when the key names a specific entity is NOT equivalent.\n\n"
    "When unsure between 'recognized synonym' and 'different entity', default to equivalent=false.\n\n"
    "Commitment rule: the candidate must COMMIT to the answer-key entity. If the candidate hedges "
    "between the answer-key entity and a DIFFERENT entity (e.g. 'anti-NMDA encephalitis vs NPSLE, "
    "pending testing', or leads with the different entity and only lists the key as an alternative), "
    "it is NOT equivalent — set equivalent=false with match_type 'uncommitted'. Pending confirmatory "
    "testing for the SAME committed entity (e.g. 'AML with t(8;21), awaiting cytogenetics') is fine."
)


def build_judge_prompt(*, expected: str, aliases: tuple[str, ...], candidate: str) -> str:
    payload = {
        "answer_key_diagnosis": expected,
        "answer_key_accepted_aliases": list(aliases),
        "candidate_final_diagnosis": candidate,
    }
    return (
        JUDGE_SYSTEM_RULES
        + "\n\nReturn strict JSON only:\n"
        "{\n"
        '  "equivalent": true,\n'
        '  "match_type": "exact | qualifier_difference | synonym | wrong_species | '
        'wrong_subtype | wrong_lineage | wrong_entity | too_generic",\n'
        '  "rationale": "one or two sentences"\n'
        "}\n\n"
        f"Comparison:\n{json.dumps(payload, indent=2, sort_keys=True)}\n"
    )


def judge_diagnosis_equivalence(
    client: OpenAICompatibleChatClient,
    *,
    expected: str,
    candidate: str,
    aliases: tuple[str, ...] = (),
    max_tokens: int = 512,
    fallback_client: OpenAICompatibleChatClient | None = None,
    model_call_recorder: ModelCallRecorder | None = None,
) -> JudgeVerdict:
    """Ask the configured model whether ``candidate`` is the same diagnosis as ``expected``.

    A slower/stronger primary judge (e.g. deepseek-v4-pro) can intermittently time out. When the
    primary fails after retries, a secondary LLM judge (``fallback_client``, e.g. flash) is tried
    before the last-resort lexical score — a secondary judge is far more reliable than the lexical
    proxy, which is known to produce false negatives.
    """

    prompt = build_judge_prompt(expected=expected, aliases=aliases, candidate=candidate)
    last_exc: Exception | None = None
    result = None
    payload = None
    # Retry transient API/parse hiccups before falling back.
    for attempt in range(_JUDGE_MAX_ATTEMPTS):
        try:
            result = client.chat(prompt=prompt, temperature=0.0, max_tokens=max_tokens)
            payload = parse_json_object(result.content)
            _record_model_call(
                model_call_recorder,
                prompt=prompt,
                result=result,
                parsed=payload,
                max_tokens=max_tokens,
                temperature=0.0,
                expected=expected,
                candidate=candidate,
            )
            break
        except Exception as exc:  # pragma: no cover - network/parse failure path
            last_exc = exc
            if attempt < _JUDGE_MAX_ATTEMPTS - 1:
                time.sleep(_JUDGE_RETRY_BACKOFF_SECONDS * (attempt + 1))
    if payload is None or result is None:
        _record_model_call(
            model_call_recorder,
            prompt=prompt,
            error=str(last_exc),
            max_tokens=max_tokens,
            temperature=0.0,
            expected=expected,
            candidate=candidate,
        )
        if fallback_client is not None:
            secondary = judge_diagnosis_equivalence(
                fallback_client, expected=expected, candidate=candidate, aliases=aliases,
                max_tokens=max_tokens, model_call_recorder=model_call_recorder,
            )
            if secondary.method == "judge":
                return JudgeVerdict(
                    score=secondary.score,
                    method="judge_secondary",
                    match_type=secondary.match_type,
                    rationale=secondary.rationale,
                    judge_model=secondary.judge_model,
                    judge_error=f"primary judge failed: {last_exc}",
                )
        fallback = lexical_score(candidate, {"diagnosis": expected, "aliases": aliases})
        return JudgeVerdict(
            score=fallback,
            method="judge_fallback_lexical",
            rationale="judge call failed after retries; fell back to lexical score",
            judge_error=str(last_exc),
        )
    equivalent = bool(payload.get("equivalent"))
    match_type = payload.get("match_type")
    rationale = payload.get("rationale")
    return JudgeVerdict(
        score="pass" if equivalent else "fail",
        method="judge",
        match_type=match_type if isinstance(match_type, str) else None,
        rationale=rationale if isinstance(rationale, str) else None,
        judge_model=result.model,
    )


def score_diagnosis(
    *,
    candidate: str | None,
    expected: str,
    aliases: tuple[str, ...] = (),
    judge_client: OpenAICompatibleChatClient | None = None,
    fallback_client: OpenAICompatibleChatClient | None = None,
    model_call_recorder: ModelCallRecorder | None = None,
) -> JudgeVerdict:
    """Score one diagnosis.

    Strategy: empty -> not_run; lexical pass -> accept cheaply; otherwise, if a judge
    client is available, escalate to the LLM judge (with an optional secondary-judge fallback);
    otherwise return the lexical fail.
    """

    text = (candidate or "").strip()
    if not text:
        return JudgeVerdict(score="not_run", method="empty")
    lexical = lexical_score(text, {"diagnosis": expected, "aliases": aliases})
    if lexical == "pass" and not _has_competing_hedge(text):
        return JudgeVerdict(score="pass", method="lexical", match_type="lexical")
    # A lexical pass on a hedged answer (e.g. "X vs Y, pending testing") can be a false
    # positive: the key may appear only as one competing option. Escalate to the judge, which
    # enforces commitment. Without a judge client, fall back to the lexical verdict.
    if judge_client is None:
        return JudgeVerdict(score=lexical, method="lexical")
    return judge_diagnosis_equivalence(
        judge_client, expected=expected, candidate=text, aliases=aliases,
        fallback_client=fallback_client, model_call_recorder=model_call_recorder,
    )


# Markers that signal the answer weighs multiple DISTINCT entities against each other, as
# opposed to "pending/awaiting" qualifiers on a single committed entity.
_COMPETING_HEDGE_MARKERS = (
    " vs ", " vs.", "versus", "rule out", " r/o ", "differential between", " either ",
)


def _has_competing_hedge(text: str) -> bool:
    lowered = f" {text.lower()} "
    return any(marker in lowered for marker in _COMPETING_HEDGE_MARKERS)


def _record_model_call(
    recorder: ModelCallRecorder | None,
    *,
    prompt: str,
    result: Any | None = None,
    parsed: dict[str, Any] | None = None,
    error: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    expected: str,
    candidate: str,
) -> None:
    if recorder is None:
        return
    raw = getattr(result, "raw", None) if result is not None else None
    usage = raw.get("usage") if isinstance(raw, dict) and isinstance(raw.get("usage"), dict) else None
    recorder(
        {
            "stage": "judge_equivalence",
            "actor": "judge",
            "title": "Judge equivalence call",
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
            "expected_diagnosis": expected,
            "candidate_diagnosis": candidate,
        }
    )


def _coerce_aliases(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())
