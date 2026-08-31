"""Stage 1: build the PROTECTED bare ledger.

Invariant: the bare differential must be elicited under the EXACT same prompt and judged by the SAME judge as
the evaluation, so the ledger's pass@n equals the model's bare pass@n (within-run). If P0 (no moves) does not
reproduce bare pass@1..5 exactly, the harness is corrupting the floor — that is the first thing the dev
protocol checks.

Reuse: elicit the bare differential the same way scripts/bare_top5_eval.py does (or load the saved bare5
response if available), then enrich each candidate with aliases / broader form / subtypes / refuting findings
via one primary-model call.
"""
from __future__ import annotations

import json
from typing import Any

from clinical_harness.guided_eval import parse_json_object
from clinical_harness.retrieval_guided_eval import _ranked_diagnoses

from .types import LedgerCandidate, ProtectedLedger

_BARE_TOP5_PROMPT = (
    'Give your TOP 5 most likely diagnoses for this case, ranked most likely first, as strict JSON '
    '{"ranked_differential":[{"rank":1,"diagnosis":"..."},...5 items]}. Use ONLY your own medical '
    "knowledge (no outside lookup). Be specific. Case:\n"
)

_ENRICH_PROMPT = (
    "You are enriching a protected diagnostic ledger. Do not change the rank order or diagnosis strings. "
    "For each candidate, provide aliases, a broader form if applicable, plausible more-specific subtypes, "
    "and explicit case findings that would refute the candidate if they are STATED in the case. "
    "Return strict JSON only with candidate_metadata keyed by the exact diagnosis string.\n\n"
    "Case:\n{case_prompt}\n\n"
    "Protected ranked diagnoses:\n{ranked}\n\n"
    "Schema:\n"
    '{"candidate_metadata":{"exact diagnosis":{"aliases":[],"broader_form":null,'
    '"candidate_subtypes":[],"rationale":"","refuting_findings":[]}}}'
)


def build_ledger(case_id: str, case_prompt: str, primary_model, *, bare5_response: dict | None = None) -> ProtectedLedger:
    """Elicit (or load) the model's bare top-5 and wrap it in a ProtectedLedger with per-candidate metadata.

    If `bare5_response` is provided (a saved bare5 response payload), use its ranked_differential verbatim as
    the floor — do NOT re-elicit a different differential (re-elicitation silently loses recall; see v1
    lessons). Otherwise elicit once with the canonical bare top-5 prompt at temperature 0.

    The enrichment call asks the primary model, for each candidate: aliases, the broader form (if any), plausible
    more-specific subtypes (specificity-repair targets), and the case findings that would refute it
    (`refuting_findings`). Enrichment is metadata only; it must not change the ranked diagnoses.

    Returns a ProtectedLedger whose candidates are in bare rank order and all `locked=True`.
    """
    payload = _bare_payload(case_prompt, primary_model, bare5_response=bare5_response)
    ranked = _ranked_diagnoses(payload, limit=5)
    if not ranked:
        raise ValueError(f"{case_id}: bare top-5 elicitation produced no ranked diagnoses")
    if len(ranked) < 5:
        raise ValueError(f"{case_id}: bare top-5 elicitation produced only {len(ranked)} diagnoses")

    metadata = _enrich(case_prompt, ranked, primary_model)
    candidates: list[LedgerCandidate] = []
    for rank, diagnosis in enumerate(ranked[:5], start=1):
        item = metadata.get(diagnosis, {})
        candidates.append(
            LedgerCandidate(
                rank=rank,
                diagnosis=diagnosis,
                aliases=tuple(_str_list(item.get("aliases"))),
                broader_form=_optional_str(item.get("broader_form")),
                candidate_subtypes=tuple(_str_list(item.get("candidate_subtypes"))),
                rationale=_optional_str(item.get("rationale")) or "",
                refuting_findings=tuple(_str_list(item.get("refuting_findings"))),
                locked=True,
            )
        )
    led = ProtectedLedger(case_id=case_id, candidates=candidates, case_prompt=case_prompt)
    assert_floor_preserved(led, ranked[:5])
    return led


def assert_floor_preserved(ledger: ProtectedLedger, bare_top5: list[str]) -> None:
    """Sanity guard: the ledger's ranked diagnoses must equal the bare top-5 exactly (P0 invariant)."""
    actual = ledger.ranked_diagnoses()
    if actual != bare_top5:
        raise AssertionError(
            f"{ledger.case_id}: protected ledger corrupted the bare floor: "
            f"ledger={actual!r} bare={bare_top5!r}"
        )


def _bare_payload(case_prompt: str, primary_model, *, bare5_response: dict | None) -> dict[str, Any]:
    if bare5_response:
        content = bare5_response.get("content") if isinstance(bare5_response.get("content"), dict) else bare5_response
        if isinstance(content, dict):
            return content
        raise ValueError("bare5_response must be a payload dict or contain a dict-valued 'content'")
    result = primary_model.chat(prompt=_BARE_TOP5_PROMPT + case_prompt, temperature=0.0, max_tokens=16000)
    return parse_json_object(result.content)


def _enrich(case_prompt: str, ranked: list[str], primary_model) -> dict[str, dict[str, Any]]:
    prompt = _ENRICH_PROMPT.replace("{case_prompt}", case_prompt).replace("{ranked}", json.dumps(ranked, indent=2))
    try:
        result = primary_model.chat(prompt=prompt, temperature=0.0, max_tokens=8000)
        payload = parse_json_object(result.content)
    except Exception:
        return {}
    meta = payload.get("candidate_metadata")
    return meta if isinstance(meta, dict) else {}


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
