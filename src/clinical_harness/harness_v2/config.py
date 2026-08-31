"""Configuration for harness v2. The policy level is the master safety knob; gates/thresholds are tuned on the
313-case dev set to per-cutoff non-inferiority (see docs/HARNESS_V2_EXPERIMENTS.md)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Policy ladder (docs/HARNESS_V2_DESIGN.md sec. "Move policy ladder"). Escalate only when dev certifies the
# next level is per-cutoff non-inferior. P0 is the no-corruption baseline.
PolicyLevel = Literal[
    "P0",  # output bare unchanged (must reproduce bare pass@1..5 exactly)
    "P1",  # + free moves: specificity repair, duplicate merge, bottom-slot add, contradiction-only demote
    "P2",  # + gated promotes within ranks 2..5 (risky, budgeted)
    "P3",  # + gated rank-1 swap (risky, strongest license + Tier-1 evidence)
]


@dataclass
class HarnessV2Config:
    policy_level: PolicyLevel = "P1"

    # --- arm selection (for the four-arm experiment) ---
    use_self_critique: bool = True       # verified self-critique stage (advisory; feeds free moves)
    use_retrieval: bool = True           # external PubMed/PMC retrieval
    retrieval_necessity_gate: bool = True  # skip retrieval when the model is confident/complete

    # --- safety gates (the verifier enforces these; see verifier.py) ---
    require_verbatim_discriminator: bool = True   # a move needs a verbatim case-prompt span
    require_diagnosticity: bool = True            # the discriminator must be (near-)specific, not "compatible"
    forbid_absence_refutation: bool = True        # never demote on "not mentioned"; only on stated contradiction
    require_model_ratification: bool = True       # primary LLM must confirm each move against the full case

    # --- risky-move budget (Tier 2) ---
    min_rank1_swap_evidence_tier: int = 1         # rank-1 swaps require Tier-1 evidence (criteria/guidelines)
    min_demotion_evidence_tier: int = 2           # case reports (Tier 3/4) may ADD but never demote
    self_consistency_samples: int = 1             # repeat verification; act only on recurring moves (temp 0)

    # --- recall lane ---
    max_added_candidates: int = 1                 # how many missed candidates may enter low slots
    allow_specificity_repair: bool = True         # broad->specific at SAME rank when broad form fails

    # --- models (reuse v1 infra) ---
    primary_model: str = ""               # the answerer / verifier (frontier model under test)
    reader_model: str = "v4-flash"        # extractor only, never decides (see self_critique/retrieval)
    judge_model: str = "v4-flash"         # same majority-of-3 judge as v1, within-run
    judge_votes: int = 3
    temperature: float = 0.0              # ALWAYS 0.0 (project rule)
