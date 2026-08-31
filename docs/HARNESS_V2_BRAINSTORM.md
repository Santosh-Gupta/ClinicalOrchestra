# Harness v2 brainstorm: a retrieval harness that helps at *every* top-n, never hurts

Internal design brainstorm. No implementation yet. Goal: from the ground up, design a retrieval harness whose
ranked differential **dominates** the model's bare differential — for every cutoff n in 1..5, pass@n(harness)
>= pass@n(bare) — while still genuinely *improving* some cutoffs, including top-1.

## 1. Restate the goal precisely, and why it is hard

"Helps at every top-n, never hurts" = the harness's final ranking dominates the bare ranking: for the (unknown)
gold diagnosis, `rank_harness(gold) <= rank_bare(gold)` on every case. If that holds per case, then pass@n is
non-decreasing at every cutoff, automatically.

Why this is hard: improving top-1 means being willing to change which candidate is rank-1. But if the bare
rank-1 was already correct, *any* change hurts. A free re-ranker cannot know which case it is in, so reordering
is inherently double-edged — this is exactly the crowding we measured in v1 (substitution moved Gemini Flash's
top-2 from 44 to 33). A strict per-case guarantee is therefore **impossible for an unconstrained re-ranker**.
The guarantee has to come from *constraining the moves the harness is allowed to make* so that the only licensed
moves are ones that (under sound evidence) cannot demote the truth.

## 2. What v1 taught us (the constraints any v2 must respect)

1. **Substitution/free re-ranking hurts.** Literature-salient mimics get promoted on generic evidence and crowd
   the model's own correct candidates down. (RAG anchoring/distraction.)
2. **The floor must be the model's TRUE bare differential**, judged by the same judge (within-run). Re-eliciting
   a narrower differential silently loses recall.
3. **Absence of evidence != evidence of absence.** v1 substitution demoted candidates the model couldn't find
   literature for. Several of those were correct (rare/recent entities). A candidate must never lose rank merely
   because retrieval failed to support it.
4. **Retrieval helps most where the base model has a knowledge gap** (weaker models gained more). For a strong
   model that is usually right, the harness's job is mostly *don't break it*, occasionally *add a missed entity*.
5. **The 5-slot cap forces a trade**: adding a candidate displaces one. Improving recall (bottom) and precision
   (top) are different operations with different risk profiles.
6. **The reader is effective** (rejects ~73% of retrieved papers, keeps ~10 relevant/case) and cheap. Keep it.
7. **Judge stochasticity is real** — evaluate within-run, and treat <=1-rank ladder moves as noise when tuning.

## 3. The central reframe for v2

**v1 treated the harness as a generator that competes with the model** (produce a differential, then fuse).
Crowding is intrinsic to that framing. **v2 should treat the harness as a conservative *editor/verifier* of the
model's own differential, whose default action is NO-OP, and whose only licensed edits are grounded in a case
fact.** It never rewrites the list; it makes a few surgical, evidence-verified moves, and otherwise returns the
bare list untouched.

**The dominance argument.** Restrict the harness to two licensed moves, each requiring a *verbatim discriminator
present in the case prompt*:
- **Promote** candidate X above candidate Y only if a case-present discriminator is diagnostic *for X*.
- **Demote** candidate X only if a case-present discriminator *refutes X* (a finding the case shows that X
  cannot explain / requires-and-lacks).
- Everything else: **no-op** (keep bare order).

If verification is sound — the discriminator is really in the case and really diagnostic — then the **truth is
never refuted by a real case fact**, so the gold is never demoted; and the gold can only be promoted (when the
model under-weighted a present discriminator). Hence `rank_harness(gold) <= rank_bare(gold)` for every case, and
pass@n dominates at every cutoff. **The guarantee degrades exactly to the soundness of verification** — which
becomes the one thing to engineer and measure, instead of a diffuse "make retrieval better."

## 4. Two lanes (different cutoffs, different risk)

- **Precision lane (top of list).** Verified promotions/demotions *among existing candidates*. This is what can
  move the gold to rank-1/2/3. High bar: each move needs a case-quoted discriminator + the model's own
  confirmation that the discriminator overrides its prior. Targets the "the case literally contained the
  deciding sign and the model under-weighted it" wins (e.g. an antibody/stain pattern stated in the vignette).
- **Recall lane (bottom of list).** Insert genuinely-missed candidates the model never listed, grounded in a
  case-present feature, into the lowest slot(s). This is v1's slot-5 trick, generalized but still bounded so it
  can never push a *higher-ranked* bare candidate out of top-n. Targets bare-miss recovery (top-4/5 gains).

Keeping the lanes separate lets us bound each: the recall lane can only add at/after the last bare rank; the
precision lane can only reorder when a hard gate fires.

## 5. Mechanisms to make verification sound (the real work)

- **Verbatim-discriminator extraction.** The reader must quote the exact case sentence that licenses a move; if
  it cannot quote it, the move is rejected. Kills hallucinated/ generic-literature promotions.
- **Diagnosticity test.** The discriminator must be (near-)specific to the candidate, not merely "compatible."
  Generic reviews "raise possibilities," they do not reorder (v1's skeptical-evidence contract, made strict).
- **Model-as-verifier with veto.** The primary LLM sees each *proposed* move + its quoted discriminator and must
  ratify it against the full case; unratified moves are dropped. The model can veto but the harness cannot force.
- **Asymmetric demotion rule.** Demote only on positive refutation; never on "no support found." (Principle #3.)
- **Abstention / no-op default + confidence gate.** If the bare rank-1 is confidently supported and nothing is
  refuted, the harness does nothing — cheap and safe. Most strong-model cases should hit this path.
- **Self-consistency on the move, not the answer.** Sample the verification a few times (temp 0 ⇒ use prompt
  perturbations or independent reader calls); only act on moves that recur. Reduces one-off judge/reader noise.
- **Better retrieval coverage so the lane *can* fire.** Feature-driven and open-ended "what else explains finding
  F" queries (not just diagnosis-anchored), so the discriminator papers are actually retrieved. Coverage feeds
  the gate; it does not relax it.

## 6. How we use the 358 dev cases (and why this set, not the 68)

The 68 are the held-out benchmark — never tune on them. The 358 dev cases (filter to the ~312 not flagged
`not_solvable`/`not_self_contained`) are the tuning ground. Protocol:
- Establish each dev model's bare per-cutoff ladder (within-run judge).
- For every candidate gate/threshold, measure the **per-cutoff delta vs bare** and require it to be `>= 0` at
  *every* n (that is the operational version of "only helps"); pick the operating point with the best top-1/top-3
  gain subject to no-regression at any n.
- Track **harm incidents** (cases where a verified move demoted the gold) and read every one — each is a
  verification-soundness bug to fix, not a threshold to nudge.
- Only after the gate is no-regression on dev do we touch the 68 (once), to report.

## 7. Failure modes to design against (from the v1 regression analysis)

- RAG anchoring (salient mimic promoted) → verbatim + diagnosticity gate.
- Reader false-negatives (drops the supporting paper) → coverage queries + don't demote on absence.
- Distillation compression (loses a candidate) → keep a candidate ledger; never silently drop.
- Evidence-grounded framing dropping unsupported-but-correct rare dx → asymmetric demotion.
- Task-type drift (answered management/outcome instead of diagnosis) → task-type detector; only diagnosis moves.
- Cost blowup → abstain early when bare is confident; the gate should fire on a minority of cases.

## 8. Open questions

- Can the precision lane help top-1 *net-positive* on strong models, or is the honest ceiling "neutral at top-1,
  gains at top-3/5"? (Dev set answers this.)
- Is "verbatim discriminator present in the prompt" too strict (kills real wins where the discriminator is
  implicit)? Where is the precision/recall knee?
- Should the recall lane be allowed >1 slot, and if so how to bound it so it can't push a gold out of top-n?
- Do we need a learned calibrator (logistic on gate features) or do hard rules suffice?
- How much of the gain is just "better elicitation of the model's own knowledge" vs genuinely external facts —
  i.e., is retrieval even necessary, or is a verified self-critique most of the win?
