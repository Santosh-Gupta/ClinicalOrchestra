# Failure determinacy analysis: broken cases vs reasoning failures (2026-06-15)

We pushed the harness on 52 v4-Pro cold-failures and hit a ~15% plateau across every lever and both
models. Before treating the residual as "reasoning to be augmented," we must separate **broken cases**
(the deciding discriminator is absent from the prompt → unanswerable) from genuine **reasoning
failures** (the discriminator is present, the model picks wrong). This is the gate for entering the
clinical-reasoning-augmentation phase honestly.

## Definition

**Discriminator** = a clinical fact required to reach the published diagnosis. If it lives only in the
source paper and is **absent from the challenge prompt**, the case is **under-determined / broken** —
no system can name the gold from the given information, so it must be fixed in NeurologyBM, not counted
against the harness.

## Two exemplars (read Pro's actual reasoning trace + the source)

- **BROKEN — PMC11138152 (gold: DJ-1/PARK7 AR early-onset PD).** Prompt: full parkinsonism phenotype +
  *"A Parkinson's disease gene panel was sent for sequencing"* → asks *"most likely genetic
  diagnosis?"* **The sequencing result is never given.** DJ-1, PRKN, PINK1 are clinically
  near-identical AR early-onset PD; the gene is not inferable from phenotype. Pro answered **PRKN** (the
  commonest) and itself noted *"awaiting genetic test results."* This is a reasonable answer to an
  under-specified question — the **case is broken** (asks for a specific gene without the result).
- **REASONING — PMC3011101 (gold: intracranial extension of cervical ICA dissection).** Prompt DOES
  contain the discriminators (prior dissection, progressive vessel-wall irregularity + stenosis on DSA,
  progression despite anticoagulation). Pro still answered **PACNS**. The information was present; the
  selection was wrong → a genuine reasoning failure (and a hard, somewhat ambiguous one).

## Scan across the 52 (heuristic: gold names a specific gene/entity whose token is absent from the prompt)

~25/52 flagged, but the heuristic over-counts (diagnosis acronyms like IAD/MCI/MMO are absent from any
prompt yet the entity is clinically determinable). The **robust** subset is the **pure-genetic cases**
(~12–14): SLC6A1, DJ-1/PARK7, KCNMA1, ASNS, SCA12, SPG4/SPAST, ATP1A3, KCTD17, DHDDS, TANGO2, KCNQ3,
Warsaw-breakage. These share the broken pattern: **the prompt asks for the specific gene but withholds
the sequencing result, and the gene is not inferable from a phenotype shared with near-neighbors.**
Antibody cases (CASPR2/Morvan, MOGAD, MNOS, SREAT) are determinate **iff** the prompt gives the serology
— a per-case check.

**Conclusion: a substantial fraction (conservatively the ~12–14 genetic cases, ≈25% of the pool) are
broken/under-determined. The true reasoning-phase denominator is the determinable failures, and the
harness's reclaim on those is meaningfully higher than the raw ~15%.** We ARE partly in the
reasoning-augmentation phase (cases like the dissection one), but the metric is contaminated by broken
cases that must be fixed first.

## Two synergistic fixes

1. **Top-5 ranked differential (now implemented, pass@k scoring).** For the near-neighbor-gene cases,
   the gold is usually *among* the model's candidates (Pro listed DJ-1 in its uncertainty). pass@5
   credits "the right gene is in the differential," which is the honest measure of an information-
   retrieval system and side-steps the over-specification of demanding the exact #1 gene.
2. **Fix the broken cases in NeurologyBM** (spec below) — so the benchmark measures reasoning, not
   guess-the-withheld-gene.

## NeurologyBM case-validation pipeline (spec — to build there)

A new API pipeline (DeepSeek-assisted) that flags/fixes under-determined challenges:
- **Detector:** for each challenge, given (challenge_prompt, answer_key.diagnosis, source full text),
  ask: *is every discriminator needed to reach the gold present in the prompt?* Specifically flag the
  pattern "asks for a specific gene / antibody / pathology / organism whose defining result is stated
  as pending/sent/absent." (This generalizes the refinement guardrails' `solvability` check, now
  applied to *gene/antibody specificity*, not just histology.)
- **Repair options per flagged case:** (a) **add the deciding result** to the prompt from the source
  (e.g. include the sequencing result / the antibody titer / the biopsy IHC) so the gold becomes
  reachable; OR (b) **relax the gold** to the determinable level (e.g. "autosomal-recessive early-onset
  Parkinson's disease" instead of the specific gene) when the source itself only reached the gene by
  sequencing; OR (c) **reframe the question** to the next-best-step (order the gene panel) rather than
  the unobtainable specific entity; OR (d) **drop** the case.
- **Run it over ALL prior dev sets** (second-100, third-100, and earlier) to quantify and repair the
  broken fraction. Report the cleaned pass-rate alongside the raw one.

## Creator improvements (NeurologyBM)

- The refiner's `solvability_audit` should explicitly cover **molecular/antibody specificity**: if the
  answer_key names a specific gene/antibody, the prompt must contain the result that identifies it (or
  the gold must be set at the determinable level). Add this to the refinement prompt + a deterministic
  check (gold gene/antibody token must appear in the prompt, else flag `not_solvable_specificity`).
- Prefer asking for the **determinable** answer: when the source only reaches the gene by sequencing,
  the challenge should either include that result or ask for the syndrome-level diagnosis + the
  confirmatory test.

## Reasoning-failure targets (the genuinely determinable misses — the real augmentation work)

After removing broken cases, the residual reasoning failures (e.g. dissection→PACNS) show the model
*has* the discriminator and weights it wrong — anchoring on a prototypical mimic. This is where
clinical-reasoning augmentation applies: force the model to test the leading hypothesis against the
specific discriminating finding present in the case (here, "prior dissection + progressive vessel-wall
change favors dissection extension over de novo PACNS"). General mechanism candidate: a discriminator-
driven re-rank — for each top candidate, check it against the strongest case-specific finding, and
demote candidates that the finding argues against.
