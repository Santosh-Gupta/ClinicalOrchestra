"""Core data contracts for harness v2. These types are the stable interface between stages; the executor
implements the stages against them. Keep them small and explicit.

Vocabulary:
- "bare differential": the base model's own ranked top-5, elicited under the SAME prompt/judge as evaluation.
- "ledger": the protected representation of the bare differential plus per-candidate metadata. Immutable
  unless a move is licensed.
- "move": a single, auditable edit to the ledger. Every move carries the verbatim case discriminator that
  licenses it and is classified free (cannot demote the gold) or risky (can).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

MoveKind = Literal[
    "noop",              # no change
    "refine_specificity",# replace a candidate with a more specific subtype AT THE SAME RANK (free)
    "merge_duplicate",   # collapse an alias/duplicate, freeing a slot (free)
    "add_candidate",     # insert a genuinely-missed candidate into the lowest open slot (free)
    "demote",            # move a candidate DOWN, only on explicit case contradiction (free-ish; see verifier)
    "promote",           # move a candidate UP within ranks 2..5 (risky)
    "rank1_swap",        # replace the rank-1 candidate (risky; requires the strongest license)
]

MoveTier = Literal["free", "risky"]   # free => formally cannot demote the gold; risky => can, spend budget
EvidenceTier = Literal[1, 2, 3, 4]    # 1=criteria/guidelines, 2=case series w/ discriminating table,
                                      # 3=single case report, 4=weak semantic/snippet


@dataclass
class LedgerCandidate:
    """One protected candidate from the bare differential, plus what would refute/refine it."""
    rank: int                      # original bare rank (1-5)
    diagnosis: str
    aliases: tuple[str, ...] = ()
    broader_form: str | None = None        # e.g. "autoimmune encephalitis" for "anti-LGI1 encephalitis"
    candidate_subtypes: tuple[str, ...] = ()  # specificity-repair targets
    rationale: str = ""
    refuting_findings: tuple[str, ...] = ()   # case findings that, if present, would rule this out
    locked: bool = True            # protected; only a licensed move may touch it


@dataclass
class ProtectedLedger:
    """The bare differential, protected. The move engine operates on this; it is never free-form rewritten."""
    case_id: str
    candidates: list[LedgerCandidate]    # in bare rank order
    case_prompt: str                     # the challenge text (source of verbatim discriminators)

    def ranked_diagnoses(self) -> list[str]:
        return [c.diagnosis for c in sorted(self.candidates, key=lambda c: c.rank)]


@dataclass
class Discriminator:
    """A finding that licenses a move. MUST be a verbatim span from the case prompt (not invented, not from a
    retrieved paper's generic criteria). `present=True` => the case states it; absence is NOT a discriminator."""
    quote: str                     # verbatim substring of the case prompt
    present: bool                  # True only if the case affirmatively states it (see "absence != refutation")
    points_to: str                 # the diagnosis it supports or refutes
    relation: Literal["supports", "refutes"]
    diagnostic: bool               # True only if (near-)specific to `points_to`, not merely "compatible"


@dataclass
class Move:
    kind: MoveKind
    tier: MoveTier
    target_rank: int | None = None        # candidate the move acts on
    new_diagnosis: str | None = None      # for refine_specificity / add_candidate / rank1_swap
    licensing: Discriminator | None = None
    evidence_tier: EvidenceTier | None = None
    model_ratified: bool = False          # the primary LLM confirmed the move against the full case
    note: str = ""


@dataclass
class MoveVerdict:
    move: Move
    licensed: bool                 # passed the verifier gate
    reason: str                    # why licensed / rejected (for audit)


@dataclass
class ArmResult:
    """Output of one pipeline arm on one case."""
    case_id: str
    arm: Literal["bare", "self_critique", "retrieval", "full"]
    bare_top5: list[str]
    final_top5: list[str]
    applied_moves: list[Move] = field(default_factory=list)
    rejected_moves: list[MoveVerdict] = field(default_factory=list)
    grounding_sources: list[dict] = field(default_factory=list)   # PMCID/DOI of retained papers
    retrieval_invoked: bool = False
