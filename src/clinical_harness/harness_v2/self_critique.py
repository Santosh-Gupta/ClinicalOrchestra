"""Stage 2: verified self-critique (runs BEFORE external retrieval).

Hypothesis under test (the decisive experiment): for frontier models, a verified self-critique recovers most
of the *safe* improvement, and external retrieval mainly helps weaker base models and rare entities. This stage
is how we measure that.

The primary model critiques its OWN bare ledger:
- Which candidates are weakly supported? (advisory only — see invariant below)
- What more-specific subtype of a listed candidate might the gold actually be? (-> specificity-repair targets)
- What rare/missed entity would it regret omitting? (-> add_candidate proposals for the recall lane)
- What case finding, if present, would change rank-1? (-> potential rank-1 challenger, routed through verifier)

INVARIANT: self-critique is ADVISORY. It only PROPOSES moves; it cannot apply them. Every proposal is routed
through the verifier (verifier.py), which enforces verbatim-discriminator + diagnosticity + absence!=refutation.
A self-critique proposal with no verbatim case discriminator is dropped. This keeps the stage from
rationalizing or inventing uncertainty.
"""
from __future__ import annotations

import json
from typing import Any

from clinical_harness.guided_eval import parse_json_object

from .types import Discriminator, Move, ProtectedLedger

_SELF_CRITIQUE_PROMPT = (
    "You are the primary diagnostic model auditing your OWN protected bare differential. "
    "The protected list is the floor; you may only propose small edits. Do not apply moves. "
    "Every proposed move must cite a verbatim quote copied exactly from the case prompt. "
    "Absence is not refutation: do not propose demotion because a finding is merely unmentioned. "
    "A discriminator must be near-specific, not just compatible. Return strict JSON only.\n\n"
    "Allowed move kinds: refine_specificity, add_candidate, demote, promote, rank1_swap.\n"
    "Use refine_specificity only to replace a listed broad diagnosis with a more specific subtype at the same rank. "
    "Use add_candidate for a missed diagnosis that should fill only an open/freed low slot. "
    "Use demote only when the case states a contradiction to the target candidate. "
    "Use promote/rank1_swap only for high-confidence risky moves with two-sided support/refutation.\n\n"
    "Case:\n{case_prompt}\n\n"
    "Protected ledger:\n{ledger}\n\n"
    "Schema:\n"
    '{"moves":[{"kind":"refine_specificity|add_candidate|demote|promote|rank1_swap",'
    '"target_rank":1,"new_diagnosis":"specific diagnosis or null",'
    '"quote":"verbatim case span","points_to":"diagnosis supported or refuted",'
    '"relation":"supports|refutes","diagnostic":true,'
    '"evidence_tier":1,"note":"brief audit note"}]}'
)


def propose_moves(ledger: ProtectedLedger, primary_model, config) -> list[Move]:
    """Run the self-critique prompt over the protected ledger and return PROPOSED moves (unverified).

    Each proposed move must name a verbatim span of `ledger.case_prompt` as its licensing discriminator; the
    verifier will re-check it. Proposals without a verbatim case span should not be emitted. Returns moves of
    kind refine_specificity / add_candidate / demote / promote / rank1_swap, each marked with its tier.
    """
    ledger_payload = [
            {
                "rank": c.rank,
                "diagnosis": c.diagnosis,
                "aliases": list(c.aliases),
                "broader_form": c.broader_form,
                "candidate_subtypes": list(c.candidate_subtypes),
                "rationale": c.rationale,
            }
            for c in ledger.candidates
        ]
    prompt = _SELF_CRITIQUE_PROMPT.replace("{case_prompt}", ledger.case_prompt).replace(
        "{ledger}", json.dumps(ledger_payload, indent=2)
    )
    try:
        result = primary_model.chat(prompt=prompt, temperature=0.0, max_tokens=12000)
        payload = parse_json_object(result.content)
    except Exception:
        return []
    return [_move_from_payload(item, ledger, source="self_critique") for item in _dict_list(payload.get("moves"))]


def _move_from_payload(item: dict[str, Any], ledger: ProtectedLedger, *, source: str) -> Move:
    kind = str(item.get("kind") or "").strip()
    if kind not in {"refine_specificity", "add_candidate", "demote", "promote", "rank1_swap"}:
        return Move(kind="noop", tier="free", note=f"{source}: invalid kind {kind!r}")
    quote = _optional_str(item.get("quote"))
    relation = str(item.get("relation") or "supports").strip().lower()
    if relation not in {"supports", "refutes"}:
        relation = "supports"
    points_to = _optional_str(item.get("points_to")) or _optional_str(item.get("new_diagnosis")) or _target_dx(item, ledger)
    if not quote or quote not in ledger.case_prompt or not points_to:
        return Move(kind="noop", tier="free", note=f"{source}: missing exact discriminator quote or target")
    evidence_tier = _evidence_tier(item.get("evidence_tier"))
    licensing = Discriminator(
        quote=quote,
        present=True,
        points_to=points_to,
        relation=relation,  # type: ignore[arg-type]
        diagnostic=bool(item.get("diagnostic")),
    )
    return Move(
        kind=kind,  # type: ignore[arg-type]
        tier="risky" if kind in {"promote", "rank1_swap"} else "free",
        target_rank=_int_or_none(item.get("target_rank")),
        new_diagnosis=_optional_str(item.get("new_diagnosis")),
        licensing=licensing,
        evidence_tier=evidence_tier,
        model_ratified=False,
        note=f"{source}: {_optional_str(item.get('note')) or ''}".strip(),
    )


def _target_dx(item: dict[str, Any], ledger: ProtectedLedger) -> str | None:
    rank = _int_or_none(item.get("target_rank"))
    for candidate in ledger.candidates:
        if candidate.rank == rank:
            return candidate.diagnosis
    return None


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _int_or_none(value: Any) -> int | None:
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return None
    return ivalue if 1 <= ivalue <= 5 else None


def _evidence_tier(value: Any) -> int | None:
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return 1
    return ivalue if 1 <= ivalue <= 4 else 1
