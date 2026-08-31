# ClinicalHarness v2 — design spec

> **Status (2026-06-30): implemented, tested on the dev set, PAUSED with a negative result.** The strictly-free
> floor (P1: dedup + bottom-add) is provably neutral, but *prefix-editing* moves (refine/demote/promote/swap) —
> whether licensed by self-critique or retrieval — did **not** safely beat the base model on hard cases: the
> verifier reduces to the model's own clinical interpretation, which is exactly what's unreliable there
> (a "refuting" finding in medicine is defeasible, not a proof). See [`writeup.md`](writeup.md) §3 for the
> conclusion. This doc is the design as intended; treat it as a starting point for a *sound-oracle* approach
> (formal criteria checks, an independent stronger verifier), not a finished, working method.

*Below is the original design spec (written before the negative dev-set result).*

Authoritative design for harness v2. Read alongside `docs/HARNESS_V2_BRAINSTORM.md` (the reasoning) and
`docs/HARNESS_V2_EXPERIMENTS.md` (the protocol). This doc says *what to build*; the scaffolding in
`src/clinical_harness/harness_v2/` says *where*.

## Goal

Produce a ranked top-5 differential that **dominates the base model's bare differential at every cutoff**:
for every n in 1..5, `pass@n(v2) >= pass@n(bare)`, while genuinely improving some cutoffs (ideally top-1).

## The key idea (why v2 differs from v1)

v1 was a *generator* that produced its own differential, then fused it with the model's. Free re-ranking
crowds the model's own correct candidates down the list (measured: Gemini Flash top-2 fell 44->33 under
substitution). **v2 is a conservative EDITOR/verifier of the model's bare differential — default action
NO-OP.** It makes only a few auditable, evidence-licensed moves and otherwise returns the bare list untouched.

## The do-no-harm vs improvement tension, and how we resolve it

Strict per-case dominance at every cutoff forces prefix preservation, which forbids changing rank-1 — so a
*pure* do-no-harm rule caps improvement near v1. We therefore treat do-no-harm as a **floor with a calibrated
harm budget**, split into two tiers:

- **Tier 1 — free moves (formally cannot demote the gold; always allowed):** specificity repair (broad->specific
  at the SAME rank), duplicate/alias merge, bottom-slot add of a missed candidate, and demotion only on a
  STATED case contradiction. These improve top-1 (via specificity) and top-5 (via add) with no gold-displacement
  risk. Specificity repair is the proof that do-no-harm and top-1 improvement are not mutually exclusive.
- **Tier 2 — risky moves (no formal guarantee; spend a bounded, certified budget):** promotes within ranks 2..5
  and rank-1 swaps. These can demote the gold. We do not require zero harm; we require the move's precision to
  be high enough that **aggregate pass@n still rises on the dev set**, with every harm incident audited.

So "only helps" operationally = `delta[n] >= 0` for all n on the 313-case dev set, with Tier 1 guaranteeing the
floor and Tier 2 spending budget only where dev certifies it pays.

## Architecture (bare-first / retrieval-second / verifier-gated)

```
case -> [ledger] build protected bare differential (+ metadata)
     -> [self_critique] model critiques its own ledger -> PROPOSED moves   (advisory only)
     -> [retrieval] (gated) frontier-led queries -> reader extracts -> case-anchored discriminators -> PROPOSED moves
     -> [verifier] six-check gate licenses/rejects each proposed move
     -> [moves] apply licensed moves permitted by policy level -> final top-5
```

Module map (`src/clinical_harness/harness_v2/`):
- `types.py` — data contracts (LedgerCandidate, ProtectedLedger, Discriminator, Move, MoveVerdict, ArmResult).
- `config.py` — HarnessV2Config (policy level + gates + budgets). Temperature ALWAYS 0.0.
- `ledger.py` — Stage 1: build the protected bare ledger; `assert_floor_preserved` (P0 invariant).
- `self_critique.py` — Stage 2: verified self-critique -> proposed moves (advisory).
- `retrieval.py` — Stage 3: necessity gate, frontier-led queries, reader-as-extractor, evidence->discriminators.
- `verifier.py` — Stage 4: the six-check licensing gate (the highest-value code).
- `moves.py` — Stage 5: constrained policy engine (P0-P3) -> final top-5.
- `pipeline.py` — orchestrates the four arms.

Reuse from v1 (do NOT modify v1): `ncbi.NcbiClient` (retrieval), `model_client` (LLM calls), the cheap reader,
and `retrieval_guided_eval._gold_rank` / `_ranked_diagnoses` (scoring). Do NOT reuse v1's final reranker — v2
never lets retrieval reorder.

## Move taxonomy & policy ladder (enforced in `moves.py`)

- P0: apply nothing. `final == bare`. Used to prove the floor isn't corrupted.
- P1: + Tier-1 free moves (specificity repair, merge_duplicate, add_candidate <= config.max_added_candidates,
  contradiction-only demote). Cannot lower pass@n for any n.
- P2: + promote within ranks 2..5 (risky, two-sided license).
- P3: + rank1_swap (risky, strongest license, Tier-1 evidence, two-sided). The only move that changes top-1.

The engine MUST refuse any move whose kind exceeds the active policy level.

## The verifier gate (six checks; the dominance property lives here)

A move is licensed only if: (1) its discriminator is a **verbatim** span of the case prompt; (2) the
discriminator is **diagnostic** (near-specific), not merely compatible; (3) **absence != refutation** — demotes
require a STATED contradiction, never "not mentioned"; (4) **evidence tier** sufficient (rank-1 swap: Tier 1;
demote: <= Tier 2; case reports may only add); (5) the primary model **ratifies** the move against the full
case (verifier can veto, never force); (6) **self-consistency** if configured (move recurs across passes).

## Safety invariants (carried from the v1 regression analysis)

- Never demote a candidate for LACK of supporting evidence (only positive contradiction). [#1 cause of v1 harm]
- Reader is an EXTRACTOR, never a decider/reranker. A weaker/differently-biased reader must not override a
  stronger answerer.
- Keep a candidate ledger; never silently drop a bare candidate (distillation compression bug).
- Task-type awareness: only diagnosis moves count; don't let a management/outcome answer displace a diagnosis.
- Necessity gate: don't retrieve when the model is confident & complete (avoids noise-induced regressions).

## Dominance argument (informal)

Under sound verification, the truth is never refuted by a real case fact, so the gold is never demoted; it can
only be promoted/refined. Hence `rank_v2(gold) <= rank_bare(gold)` per case under Tier-1-only (P1), giving
formal per-cutoff dominance. P2/P3 relax this for top-rank gains; their net effect is governed empirically by
the dev-set non-inferiority gate. The entire guarantee reduces to verification soundness — the thing to build
and measure.

## Frozen vs new
- FROZEN (do not edit): v1 = `scripts/fuse_harness.py` + the do-no-harm fusion path / `HarnessConfig` in
  `retrieval_guided_eval.py`. It is the published method.
- NEW: everything under `src/clinical_harness/harness_v2/` and `scripts/harness_v2_eval.py`.
