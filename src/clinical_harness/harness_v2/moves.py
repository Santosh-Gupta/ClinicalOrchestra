"""Stage 5: the allowed-moves engine. Applies LICENSED moves to the protected ledger under the active policy
level, producing the final top-5. This is a constrained policy engine, never free generation.

Policy ladder (config.policy_level), each a strict superset of the previous:
- P0: apply nothing. final == bare. (Used to prove the floor isn't corrupted.)
- P1: apply FREE moves only:
    * refine_specificity: replace candidate at SAME rank with a licensed more-specific subtype. Guard: only
      when the broad form was failing the judge AND the subtype is licensed; never refine a candidate that
      already passes (avoids pass->fail flips). Same rank => cannot demote any other candidate.
    * merge_duplicate: collapse an alias/duplicate; the freed slot is available to add_candidate.
    * add_candidate: insert a licensed missed candidate into the LOWEST open/freed slot only (<= config
      .max_added_candidates). Cannot push a higher-ranked bare candidate out of top-n.
    * demote: only on a Tier-<=min_demotion contradiction (verifier-licensed). NOTE even demotion is bounded:
      a demoted candidate moves DOWN, which can only lower its own rank — never another candidate's gold.
- P2: + promote within ranks 2..5 (risky; budgeted). A promote of X above Y can demote Y, so it is licensed
      only by a contradiction of Y AND support for X (two-sided), per the verifier.
- P3: + rank1_swap (risky; strongest license, Tier-1 evidence, two-sided). This is the only move that can
      change top-1, and the only one with irreducible harm risk. Enable solely after dev certifies net-positive
      pass@1 (see docs/HARNESS_V2_EXPERIMENTS.md).

DOMINANCE NOTE: under P1 the engine cannot lower pass@n for any n (free moves only). P2/P3 trade a measured
harm budget for top-rank gains; their net effect must be certified per-cutoff non-inferior on the dev set
before use. The engine must REFUSE any move above the active policy level.
"""
from __future__ import annotations

import re

from .types import ArmResult, Move, MoveVerdict, ProtectedLedger

# Exp 1 finding: refine_specificity (over-specification -> pass->fail) and demote (proposer==ratifier
# rubber-stamping) both HARM in the self-critique-only arm. They are NOT free. P1 is now STRICTLY free
# (dedup + bottom-add only); prefix-altering moves require external corroboration and live at P2+.
_ALLOWED_BY_POLICY = {
    "P0": {"noop"},
    "P1": {"merge_duplicate", "add_candidate"},
    "P2": {"merge_duplicate", "add_candidate", "refine_specificity", "demote", "promote"},
    "P3": {"merge_duplicate", "add_candidate", "refine_specificity", "demote", "promote", "rank1_swap"},
}


def apply_moves(ledger: ProtectedLedger, verdicts: list[MoveVerdict], config) -> ArmResult:
    """Apply licensed moves permitted by config.policy_level to the ledger and emit the final top-5.

    Must: (a) ignore unlicensed verdicts; (b) refuse moves whose kind exceeds the policy level; (c) preserve
    the dominance guarantees described above for P1; (d) record applied vs rejected moves on the ArmResult for
    audit. The final_top5 is exactly 5 entries.
    """
    bare = ledger.ranked_diagnoses()
    final = list(bare)
    applied: list[Move] = []
    rejected: list[MoveVerdict] = [v for v in verdicts if not v.licensed]
    policy = getattr(config, "policy_level", "P1")
    allowed = _ALLOWED_BY_POLICY.get(policy, _ALLOWED_BY_POLICY["P1"])
    if policy == "P0":
        return ArmResult(case_id=ledger.case_id, arm="bare", bare_top5=bare[:5], final_top5=bare[:5], rejected_moves=verdicts)

    for verdict in verdicts:
        if not verdict.licensed:
            continue
        move = verdict.move
        if move.kind not in allowed:
            rejected.append(MoveVerdict(move=move, licensed=False, reason=f"refused by policy {policy}"))
            continue
        changed = False
        if move.kind == "refine_specificity":
            changed = _apply_refine(final, move)
        elif move.kind == "merge_duplicate":
            changed = _apply_merge(final, move)
        elif move.kind == "add_candidate":
            changed = _apply_add(final, move, max_added=int(getattr(config, "max_added_candidates", 1)))
        elif move.kind == "demote":
            changed = _apply_demote(final, move)
        elif move.kind == "promote":
            changed = _apply_promote(final, move)
        elif move.kind == "rank1_swap":
            changed = _apply_rank1_swap(final, move)
        if changed:
            applied.append(move)
        else:
            rejected.append(MoveVerdict(move=move, licensed=False, reason="licensed but no valid policy action"))

    final = _dedupe_keep_order(final)
    for dx in bare:
        if len(final) >= 5:
            break
        if _norm(dx) not in {_norm(item) for item in final}:
            final.append(dx)
    return ArmResult(
        case_id=ledger.case_id,
        arm="bare",
        bare_top5=bare[:5],
        final_top5=final[:5],
        applied_moves=applied,
        rejected_moves=rejected,
    )


def _apply_refine(final: list[str], move: Move) -> bool:
    if not move.target_rank or not move.new_diagnosis:
        return False
    idx = move.target_rank - 1
    if idx < 0 or idx >= len(final):
        return False
    old = final[idx]
    if _norm(old) == _norm(move.new_diagnosis):
        return False
    # Same-rank refinement only; never move another candidate.
    final[idx] = move.new_diagnosis
    return True


def _apply_merge(final: list[str], move: Move) -> bool:
    before = list(final)
    seen: set[str] = set()
    merged: list[str] = []
    for dx in final:
        key = _norm(dx)
        if key and key not in seen:
            seen.add(key)
            merged.append(dx)
    final[:] = merged
    return final != before


def _apply_add(final: list[str], move: Move, *, max_added: int) -> bool:
    if max_added <= 0 or not move.new_diagnosis:
        return False
    if _norm(move.new_diagnosis) in {_norm(dx) for dx in final}:
        return False
    # P1 add_candidate is a free move only when it fills an open/freed slot. It does not overwrite rank 5.
    if len(final) >= 5:
        return False
    final.append(move.new_diagnosis)
    return True


def _apply_demote(final: list[str], move: Move) -> bool:
    if not move.target_rank:
        return False
    idx = move.target_rank - 1
    if idx < 0 or idx >= len(final):
        return False
    dx = final.pop(idx)
    final.append(dx)
    return True


def _apply_promote(final: list[str], move: Move) -> bool:
    if not move.new_diagnosis:
        return False
    target_key = _norm(move.new_diagnosis)
    idx = next((i for i, dx in enumerate(final) if _norm(dx) == target_key), None)
    if idx is None or idx == 0:
        return False
    new_idx = max(1, (move.target_rank or idx + 1) - 1)
    dx = final.pop(idx)
    final.insert(new_idx, dx)
    return True


def _apply_rank1_swap(final: list[str], move: Move) -> bool:
    if not move.new_diagnosis or not final:
        return False
    old = final[0]
    final[:] = [move.new_diagnosis] + [dx for dx in final if _norm(dx) != _norm(move.new_diagnosis)]
    if _norm(old) not in {_norm(dx) for dx in final}:
        final.append(old)
    return True


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = _norm(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
