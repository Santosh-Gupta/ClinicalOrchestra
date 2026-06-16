# Design: multi-angle diagnostic agent ensemble (2026-06-14)

## Why this fits (grounded in the 24 failures)

The hard-24 failures (`hard24_gap_analysis`) were not random — a single reasoner skipped *specific
angles*: it never built a drug timeline (M2, iatrogenic), never ran the can't-miss infection
exclusion (HSV), never asked "could two things coexist?" (M4), never pushed to the specific gene
(M3). A single chain anchors on one framing and the others go unexamined. **An ensemble that forces
each angle to be argued independently is a direct structural fix for exactly these misses** — it is
diagnostic "dropout": if the localization angle whiffs, the exposure/iatrogenic angle is still firing.

This mirrors how hard problems are attacked in practice (and how clinicians run a differential):
several independent framings, then synthesis.

## The angles (each a cheap Flash agent with a distinct system prompt)

These are genuinely different routes to a diagnosis, not rephrasings:

1. **Anatomic localization** — where is the lesion (cortical/white-matter/cord/NMJ/muscle/vascular
   territory)? What localizes here?
2. **Time-course / tempo** — hyperacute vs subacute vs chronic-relapsing; the tempo shortlist differs
   sharply (e.g. relapsing → channelopathy/autoimmune/vascular).
3. **Epidemiologic / exposure / iatrogenic** — meds (timeline, interactions, withdrawal,
   deficiencies), toxins, travel, diet, occupation. *Owns the M2 misses.*
4. **Can't-miss / treatable-first** — actively tries to exclude the dangerous treatable entities
   (HSV, bacterial, vascular emergency, metabolic). *Owns the HSV-type misses.*
5. **Test / marker / molecular** — what single test most changes the posterior; for phenotype→gene,
   names the candidate gene/panel. *Owns the M3/genetic misses.*
6. **Common-mimic skeptic** — assumes the obvious answer is the trap; argues the rarer entity that
   fits when the textbook clue is stripped. *Owns the M1 anchoring misses.*

## Topology (matches the user's framing)

- A **long-running coordinator** holds the shared diagnostic state (problem representation, live
  differential with probabilities, open questions, evidence ledger).
- Angle agents run **concurrently** (bounded pool; they're independent), each producing a structured
  contribution: candidate diagnoses + the discriminator they'd want + proposed queries.
- Agents **poll** the coordinator's current state and **contribute** back — so a later round can react
  to what other angles surfaced (the exposure agent sees the localization agent's lesion site).
- The coordinator **consolidates**: merges candidates, reconciles conflicts, decides whether the
  differential is resolved (reuse adaptive-rounds sufficiency logic), and writes the final answer +
  cited report.

This is a blackboard architecture: shared state, specialist contributors, a synthesizing controller.
It composes with scaled retrieval — each angle's proposed queries feed the query-strategist loop, and
per-paper extracts land in the shared ledger.

## Consolidation rules (the coordinator's job)

- A candidate raised by ≥2 independent angles is weighted up.
- The can't-miss agent has a **veto-to-investigate**: if it flags HSV/treatable, that must be
  addressed (excluded with a named test) before closure — encodes the universal can't-miss gate at
  the architecture level.
- Disagreement is signal: when angles diverge, that *is* the discriminator to retrieve next.
- Apply the universal finalization gates to the consolidated answer.

## Cost / when to invoke

Six Flash agents/round is cheap (DeepSeek 2500 concurrent), but unnecessary for easy cases. Gate the
ensemble on difficulty: run the single fast path first; escalate to the ensemble only when
self-consistency agreement is low or the differential stays unresolved after the first round (ties
into need-gated retrieval). Easy cases stay cheap; the hard-24-type cases get the full fan-out.

## Build order (incremental, each independently testable)

1. Define the 6 angle prompts + a structured `AngleContribution` schema.
2. Coordinator state object + consolidation (deterministic merge first, LLM synthesis second).
3. Run angles concurrently (reuse the bounded-pool + rate-limit infra already built).
4. Difficulty gate (self-consistency agreement) to decide single-path vs ensemble.
5. Evaluate on the hard-24 first (does the ensemble reclaim cases the single path missed?), then the
   full 100 to check it doesn't regress easy cases (control-set discipline).

## Risks

- More agents → more ways to introduce a confident wrong candidate; consolidation must be skeptical,
  not additive.
- Latency: parallelism helps, but the coordinator's serial synthesis is the critical path.
- Evaluation must isolate the ensemble's lift from the universal-gates lift (run them as separate
  ablation arms).

## Validation findings (2026-06-14, core built in `diagnostic_ensemble.py`)

Smoke-tested live on the HSV (PMC13239290) and drug-interaction (PMC13240619) cases:

1. **The angle decomposition works — it surfaces the right hypothesis the single chain missed.** The
   `cant_miss` angle independently produced "HSV encephalitis — start empiric acyclovir," and
   `exposure_iatrogenic` produced the valproate-toxicity line. This is the core value: a dedicated
   angle finds what the anchored single chain skips.
2. **Reasoning-token budget bites here too (ADR-017).** At `max_tokens=2048` two or three angles
   truncated to empty per case; raising to 8192 eliminated all angle errors. Any new model call in
   this repo must assume the reasoning budget tax.
3. **The can't-miss veto is a precision/recall knob, and prompt-tuning it on single cases oscillates.**
   A strong veto reclaimed HSV (correct) but over-fired on the drug case (reflexively led with HSV for
   an encephalopathy fully explained by valproate). Grounding the veto ("only if case-supported AND not
   better explained by another candidate") fixed the drug case but let HSV revert. With run-to-run
   variance on top, **single-case tuning is unsound; this must be calibrated against the full hard set
   + the control set.**

### Open design choice surfaced by validation

The veto strength is partly a *product* decision, not just an accuracy one: for a clinical safety
tool, a false negative on HSV (missing it) is worse than a false positive (an extra workup), so a
high-recall "cry wolf" veto may be the right default even though it lowers single-answer diagnostic
*precision* on a benchmark. Recommendation: make veto strength a **tunable parameter**, default toward
safety in doctor mode and toward precision in eval mode, and calibrate on the full set. A more robust
alternative to LLM weighing: **deterministically surface any case-grounded can't-miss as a co-leading
"must exclude" item in the report**, rather than forcing the single `final_diagnosis` string to carry
it — which also fits the cited-report deliverable better than a single label.
