"""Stage 4: the evidence verifier — the gate that makes moves trustworthy. This is where the dominance
property lives or dies, so it is the highest-value code in v2.

A move is LICENSED only if ALL hold (subject to config toggles):
1. Verbatim discriminator: `move.licensing.quote` is an exact substring of the case prompt
   (config.require_verbatim_discriminator). Invented or paper-only criteria are rejected.
2. Diagnosticity: the discriminator is (near-)specific to the target diagnosis, not merely "compatible"
   (config.require_diagnosticity). Generic reviews raise possibilities; they do not reorder.
3. Absence != refutation: a `demote`/`rank1_swap` may rely only on a STATED contradiction
   (`present=True, relation="refutes"`). "Not mentioned in the prompt" can never refute
   (config.forbid_absence_refutation). This is the single most important safety rule — most spurious demotions
   in v1-style systems come from treating missing data as negative evidence.
4. Evidence tier: rank1_swap requires tier <= config.min_rank1_swap_evidence_tier (default 1: criteria/
   guidelines); demote requires tier <= config.min_demotion_evidence_tier (default 2). Lone case reports
   (tier 3/4) may license `add_candidate` but never a demotion or rank-1 swap.
5. Model ratification: the primary model, shown the proposed move + its quoted discriminator + the full case,
   confirms the move (config.require_model_ratification). The verifier can veto; it can never force a move the
   model rejects.
6. Self-consistency: if config.self_consistency_samples > 1, the move must recur across independent
   verification passes (prompt-perturbed at temp 0) to be licensed.

Free moves (refine_specificity, merge_duplicate, add_candidate) still require (1)-(2)/(5); they are "free"
because they cannot demote an existing candidate below its bare rank, NOT because they skip verification.
"""
from __future__ import annotations

import json
from typing import Any

from clinical_harness.guided_eval import parse_json_object

from .types import Move, MoveVerdict, ProtectedLedger

_RATIFY_PROMPT = (
    "You are the primary diagnostic model verifying a proposed edit to your protected bare differential. "
    "The default is veto. Ratify only if the quoted case discriminator is verbatim present, diagnostic rather "
    "than merely compatible, and the move is justified against the full case. Absence of a finding is not "
    "refutation. Return strict JSON only.\n\n"
    "Case:\n{case_prompt}\n\n"
    "Protected top-5:\n{top5}\n\n"
    "Proposed move:\n{move}\n\n"
    'Schema: {"ratified":true,"diagnostic":true,"reason":"brief"}'
)


def verify(move: Move, ledger: ProtectedLedger, primary_model, config) -> MoveVerdict:
    """Apply the gate above to a single proposed move. Return a MoveVerdict with `licensed` and a `reason`
    string detailed enough to audit (every rejected/licensed move is logged for the dev harm analysis)."""
    if move.kind == "noop":
        return MoveVerdict(move=move, licensed=False, reason=f"noop/invalid proposal: {move.note}")
    disc = move.licensing
    if disc is None:
        return MoveVerdict(move=move, licensed=False, reason="missing licensing discriminator")
    if config.require_verbatim_discriminator and disc.quote not in ledger.case_prompt:
        return MoveVerdict(move=move, licensed=False, reason="licensing quote is not an exact case substring")
    if not disc.present:
        return MoveVerdict(move=move, licensed=False, reason="licensing discriminator is not affirmatively present")
    if config.require_diagnosticity and not disc.diagnostic:
        return MoveVerdict(move=move, licensed=False, reason="licensing discriminator marked non-diagnostic")
    if config.forbid_absence_refutation and move.kind in {"demote", "rank1_swap"}:
        if disc.relation != "refutes":
            return MoveVerdict(move=move, licensed=False, reason=f"{move.kind} requires a stated refuting discriminator")
        if not disc.present:
            return MoveVerdict(move=move, licensed=False, reason="absence cannot refute a protected candidate")
    if move.kind == "rank1_swap":
        if move.evidence_tier is None or move.evidence_tier > config.min_rank1_swap_evidence_tier:
            return MoveVerdict(move=move, licensed=False, reason="rank1_swap lacks Tier-1 evidence")
        # The current Move contract carries one discriminator, so require explicit two-sided audit text.
        # Without it, P3 swaps are refused rather than silently weakening the spec.
        if "two_sided=true" not in move.note.lower():
            return MoveVerdict(move=move, licensed=False, reason="rank1_swap lacks explicit two-sided support/refutation audit")
    if move.kind == "demote":
        if move.evidence_tier is None or move.evidence_tier > config.min_demotion_evidence_tier:
            return MoveVerdict(move=move, licensed=False, reason="demote requires Tier-2-or-stronger evidence")
    if move.kind == "promote":
        if "two_sided=true" not in move.note.lower():
            return MoveVerdict(move=move, licensed=False, reason="promote lacks explicit two-sided support/refutation audit")
    if config.require_model_ratification and not _ratified(move, ledger, primary_model, config):
        return MoveVerdict(move=move, licensed=False, reason="primary model did not ratify the move")
    move.model_ratified = True
    return MoveVerdict(move=move, licensed=True, reason="licensed by six-check verifier")


def verify_all(moves: list[Move], ledger: ProtectedLedger, primary_model, config) -> list[MoveVerdict]:
    """Verify a batch; convenience wrapper over verify()."""
    return [verify(move, ledger, primary_model, config) for move in moves]


def _ratified(move: Move, ledger: ProtectedLedger, primary_model, config) -> bool:
    if primary_model is None:
        return False
    samples = max(1, int(getattr(config, "self_consistency_samples", 1)))
    for i in range(samples):
        prompt = (
            _RATIFY_PROMPT.replace("{case_prompt}", ledger.case_prompt)
            .replace("{top5}", json.dumps(ledger.ranked_diagnoses(), indent=2))
            .replace("{move}", json.dumps(_move_payload(move) | {"verification_pass": i + 1}, indent=2))
        )
        try:
            result = primary_model.chat(prompt=prompt, temperature=0.0, max_tokens=3000)
            payload = parse_json_object(result.content)
        except Exception:
            return False
        if not payload.get("ratified"):
            return False
        if config.require_diagnosticity and payload.get("diagnostic") is False:
            return False
    return True


def _move_payload(move: Move) -> dict[str, Any]:
    disc = move.licensing
    return {
        "kind": move.kind,
        "tier": move.tier,
        "target_rank": move.target_rank,
        "new_diagnosis": move.new_diagnosis,
        "evidence_tier": move.evidence_tier,
        "note": move.note,
        "licensing": None
        if disc is None
        else {
            "quote": disc.quote,
            "present": disc.present,
            "points_to": disc.points_to,
            "relation": disc.relation,
            "diagnostic": disc.diagnostic,
        },
    }
