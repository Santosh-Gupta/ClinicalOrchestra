# ClinicalHarness v2 — experiment protocol

> **Outcome (2026-06-30, paused):** ran on dev subsets. P1 strictly-free floor = neutral (zero harm, zero
> gain). Both self-critique and retrieval prefix-editing (P2) HURT on hard cases — the audit showed the model
> misapplying real, defeasible discriminators (e.g. demoting a correct Gitelman dx on "Mg 2.8"). No gold-blind
> prefix edit reliably beat the base model. See [`writeup.md`](writeup.md) §3. Metric gotcha we hit: don't
> re-judge identical lists — judge stochasticity fakes deltas; reuse the rank when the harness made no change.

How to validate v2 on the dev set without contaminating the benchmark. The metric is locked in
`scripts/harness_v2_eval.py` (`dominance_report`); this doc says which experiments to run, in what order, and
the bar each must clear.

## Data
- **Tune on `benchmark/development_solvable.jsonl`** — 313 cases (the 358 development cases minus 45 flagged
  `not_solvable`/`not_self_contained`). Stratify reports by `review_status`.
- **NEVER tune on `benchmark/neuro_psych_68_challenges.jsonl`** (the held-out benchmark). Touch it once, only
  after a policy is frozen, to report final numbers.
- Temperature 0.0 everywhere. Same majority-of-3 judge as v1, judged WITHIN-RUN (judge bare and final in the
  same pass so the comparison is judge-consistent — this is why v1's "vs Table 2" numbers drifted).

## The success bar (operational "only helps")
For every cutoff n in 1..5: `pass@n(arm) >= pass@n(bare)` on the dev set (`dominance_report.only_helps == True`).
Also report `harm_at[n]` (bare hit, arm miss) and `help_at[n]`. **Read every harm incident** — each is a
verification-soundness bug, not a threshold to nudge.

## Order of experiments

1. **P0 floor check (must pass before anything else).** Run arm=`bare` (policy P0). Assert the v2 ledger
   reproduces the model's bare pass@1..5 exactly. If not, the harness is corrupting the floor — fix before
   proceeding. (`ledger.assert_floor_preserved`.)

2. **The decisive four-arm experiment (P1).** On the 313 cases, run all four arms at policy P1:
   `bare` / `self_critique` / `retrieval` / `full`. Report per-cutoff ladders + harm/help for each, and track
   **where the gold first appears** (self-critique vs retrieval). This answers the central question: *is
   external retrieval necessary, or does verified self-critique + specificity repair capture most of the safe
   gain?* Expected: self-critique + specificity carries frontier models; retrieval earns its cost on rare
   entities / weaker base models. Pick the cheapest arm that is non-inferior at every n and best at top-1/top-3.

3. **Ablate the free moves.** Within the best P1 arm, toggle specificity-repair, add_candidate, and
   contradiction-demote independently. Confirm each is individually non-inferior at every n (specificity repair
   in particular: require **zero pass->fail flips** — never refine a candidate that already passes).

4. **Escalate only if certified.** Enable P2 (promotes), then P3 (rank-1 swap) one at a time. Before enabling
   each: collect all *proposed* risky moves, audit ~50 by hand/judge, estimate **move precision**, and enable
   the level only if (a) precision is very high (rank-1 swaps: aim >90-95%) and (b) dev pass@1..5 stays
   non-inferior with strictly-positive top-rank gain. If a level cannot clear the bar, stop at the previous one.

5. **Freeze + benchmark.** Freeze the winning (model, policy level, gate thresholds). Run it once on the 68-case
   benchmark, within-run judged, and report per-cutoff vs bare. This is the only benchmark touch.

## Models
Run the four-arm experiment with at least one strong answerer (e.g. a frontier model) and one weaker
(DeepSeek V4 Flash/Pro) as primary, since the knowledge-gap hypothesis predicts different retrieval value by
tier. Reader = DeepSeek V4 Flash (extractor only). Judge = DeepSeek V4 Flash, 3 votes.

## What to log per case (for the harm audit)
bare_top5, final_top5, every proposed move with its verbatim discriminator + evidence tier + ratified flag,
licensed vs rejected verdicts (with reasons), and grounding-source PMCIDs/DOIs. The harm audit reads these for
every (bare hit, arm miss) case.

## Definition of done for v2 (first milestone)
A policy that is per-cutoff non-inferior on the 313 dev cases with a strictly positive gain at top-1 OR top-3
(beyond v1's top-5-only gain), with the harm audit showing residual harm traced to identified verification
bugs — then the single frozen benchmark run.
