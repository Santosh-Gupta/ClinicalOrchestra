# Gap analysis: the 24 cases that beat both models and the harness (2026-06-14)

## Setup

100-case neuro/psych-intersection benchmark, three stages (judge held fixed = Flash; only the
answer model / harness varies):

| Stage | Model | Harness | Input | Pass | Fail |
| --- | --- | --- | --- | --- | --- |
| 1 | Flash | none | 100 | 71 | 29 |
| 2 | Pro | none | 29 (Flash fails) | 2 | 27 |
| 3 | Flash | full | 27 (both fail cold) | 3 | **24** |

These **24** failed bare Flash, bare Pro, *and* Flash+harness. They are the highest-signal data we
have. This document reverse-engineers each, classifies the failure mechanism, asks whether the
correct path was *reachable* (solvable vs. flawed case), and derives improvement angles at every
level.

## Central thesis (and the paper's spine)

**For these hard cases the diagnostic information is largely retrievable from PubMed. The failures
are hypothesis-formation and query-formulation failures, not knowledge-availability failures.**

Evidence (live PubMed `esearch`, 2026-06-14):

- Long natural-language queries with many ANDed terms return **zero** results
  (`subacute encephalopathy psychosis cognitive decline elderly normal MRI herpes simplex PCR` → 0).
  PubMed ANDs every term; over-specification retrieves nothing. **This is almost certainly a major,
  silent cause of harness retrieval failure.**
- Short, mechanism-focused queries retrieve the answer:
  - `valproate risperidone interaction` → top hit *"Excessive Sedation and Catatonia-Like
    Presentation From Risperidone-Valproate Interaction"* — the **exact** gold mechanism for
    PMC13240619 (which the harness missed, calling it "valproate-induced encephalopathy").
  - `valproate induced catatonia` → *"Valproate-induced Hyperammonemic Encephalopathy Presenting as
    Catatonia."*
  - `infectious encephalitis mimicking autoimmune encephalitis` → *"Autoimmune encephalitis
    misdiagnosis and mimics"* — would push toward the HSV-1 (PMC13239290) the model anchored away
    from.
  - `myoclonic atonic epilepsy gene` → reviews enumerating **SLC6A1** (PMC10339345 gold), which the
    harness left as "genetic cause unknown."

So the lever is not a bigger model; it is **better hypotheses → better (shorter, mechanism/contrast)
queries → read what comes back.**

## Failure taxonomy (the 24 mapped)

**M1 — Anchoring on the common/famous entity, missing the rarer real one (15).** The single biggest
bucket. The challenge author strips the textbook clue (no fever, atypical MRI), and the model settles
on the prototypical diagnosis.
- PMC13239290 HSV-1 encephalitis → "autoimmune encephalitis" *(dangerous: HSV is the treatable
  can't-miss)*
- PMC13260868 DPPX AE → acute intermittent porphyria
- PMC13162229 SREAT/Hashimoto → anti-GAD65 AE
- PMC3011101 carotid-dissection intracranial extension → PACNS
- PMC11662338 RVCL-S → cerebral venous thrombosis
- PMC13208480 global hypoxic-ischemic injury → CVST + SAH
- PMC13049788 congenital vascular variant (MCA hypoplasia + circle-of-Willis) → Bow Hunter's
- PMC11138152 DJ-1/PARK7 Parkinson's → SPG7
- PMC13233052 KCNMA1 epilepsy → pyridoxine-dependent epilepsy
- PMC12104238 asparagine synthetase deficiency → Fryns syndrome
- PMC12971692 SCA12 → FXTAS
- PMC13126082 SPG4/SPAST → CDKL5
- PMC13172017 Mowat-Wilson → Aicardi
- PMC13183691 ATP1A3 relapsing encephalopathy → "mitochondrial, awaiting genetics"
- PMC13250257 illness anxiety disorder → functional movement disorder

**M2 — Missed iatrogenic / drug cause or interaction (4).** The answer is a medication effect; the
model reaches for intrinsic disease.
- PMC13240619 risperidone–valproate interaction catatonia → "valproate encephalopathy"
- PMC11631938 lamotrigine-induced parkinsonism → blamed the 22q11.2 background
- PMC13171436 enzyme-inducing-AED → vitamin-D-deficiency hypocalcemia → status → "hypoparathyroidism"
- PMC13220061 statin rhabdomyolysis with mixed neuromuscular → "anti-HMGCR necrotizing myopathy"

**M3 — Under-commitment / too generic (named the category, not the entity) (2, overlapping).**
- PMC10339345 SLC6A1 disorder → "absence epilepsy, genetic cause unknown"
- PMC13183691 (also M1) → "likely mitochondrial, awaiting confirmation"

**M4 — Missed comorbidity / second pathology (3).** The answer is *two* coexisting conditions, or a
primary plus an explicitly not-excluded second.
- PMC13214945 bvFTD **and** anti-GAD65 AE → only the GAD65 AE
- PMC13219314 AE **but** underlying tumor not excluded → only "AE, likely CASPR2"
- PMC12926095 borderline IQ + ADHD + language disorder, **NOT** autism → only "ADHD"

## Generalizable principles the harness is missing (highest leverage — these are system-prompt /
universal-gate level, not preset-specific)

Ranked by how many of the 24 they touch:

1. **Anti-anchoring / "strip the textbook clue" rule (M1, 15 cases).** Before finalizing the
   prototypical diagnosis, explicitly ask: *what rarer entity produces this same syndrome when the
   classic clue is absent?* Generate and query the mimic. This already exists as preset-specific
   gates; it must be **universal**.
2. **Iatrogenic-first rule (M2, 4 cases).** For any new neuro/psych syndrome in a patient on
   medications (or recently changed/added/interacting drugs), build a medication timeline and weigh a
   drug effect/interaction/deficiency *before* intrinsic disease. We *have* an `adverse_drug_event`
   preset — but none of these 4 cases were routed to it. **Lesson: the load-bearing principles must
   be universal gates, not gated behind a preset the router may not pick.**
3. **Treatable / can't-miss exclusion rule (subset of M1, esp. HSV).** Some misses are dangerous, not
   just wrong: HSV-1 encephalitis must be actively excluded (CSF HSV PCR + empiric acyclovir) before
   settling on autoimmune encephalitis, *even without fever or classic mesial-temporal MRI*. A
   universal "treatable emergencies first" gate.
4. **Commit to the specific molecular entity (M3 + genetic M1).** For a recognizable phenotype,
   "genetic cause unknown" is a failure; push to the named gene/syndrome via phenotype→gene
   retrieval. (Caveat: requires the discriminator to be in the prompt — see solvability below.)
5. **Second-pathology / comorbidity rule (M4, 3 cases).** Don't collapse to one label; ask whether
   two conditions coexist, or whether a second remains unexcluded. State it explicitly.

## The retrieval angle (generalizable, validated above)

6. **Short, focused queries — and broaden on zero results.** Cap query term count; prefer 2–4
   high-yield terms; detect empty result sets and automatically broaden (drop terms / OR-group).
   This alone would have changed several outcomes.
7. **Contrast / "X mimicking Y" queries.** `infectious encephalitis mimicking autoimmune
   encephalitis` surfaces the misdiagnosis literature directly. Generalize: when anchored on entity
   A, query "A mimics" and "B vs A distinguishing features."
8. **Phenotype→gene review queries** for the genetic cases (`<phenotype> gene` / `<phenotype>
   genetic causes`) retrieve reviews that enumerate the responsible gene.

## Case-specific augmentation angle (the niche knowledge that can't live in weights)

For the rare-entity cases (RVCL-S, ATP1A3-RECA, SCA12, KCNMA1, DPPX, Mowat-Wilson, ASNSD…), the
discriminating knowledge is genuinely niche. Two complementary mechanisms:
- **A stored knowledge pack** (retrieval-augmented, on disk, not in the prompt budget): curated
  "phenotype → consider-this-rare-entity → discriminator → confirmatory test" cards, retrieved by
  feature match. This is the project's own mini knowledge base, grown from each hard case.
- **Live literature retrieval** with the query improvements above, which (per the thesis) already
  reaches most of these.

## Architecture angles (see dedicated design docs)

9. **Multi-angle diagnostic ensemble** — independent reasoners (anatomic localization; time-course;
   epidemiologic/exposure & drugs; can't-miss/treatable; test/marker-driven; genetic-phenotype) feed
   a long-running coordinator that consolidates. Directly attacks M1–M4 by *forcing* the angles the
   single agent skipped (iatrogenic, can't-miss, second-pathology). → `docs/multi_agent_design...`
10. **Context-isolated scaled retrieval** — per-paper Flash extractor returns only the
    diagnosis-relevant snippet (or nothing) + proposed follow-up queries, so hundreds/thousands of
    papers can be screened without context bloat; a standing query-strategist agent keeps iterating
    queries against the evolving differential. → `docs/scaled_retrieval_design...`

## Solvable vs. flawed (must-do before crediting/blaming the harness)

Some of the 24 may be under-determined (the deciding discriminator was stripped from the prompt) —
the same defect class our refinement guardrails catch. Before treating a case as a harness failure,
confirm the correct path is reachable from the prompt. Provisional reads:
- **Reachable** (clear path, harness limitation): PMC13240619 (drug interaction — retrieval nails
  it), PMC13239290 (HSV can't-miss), PMC13162229 (SREAT vs GAD65), PMC3011101 (dissection vs PACNS).
- **Needs the source checked** (may be under-determined): the pure-genetic entities where the variant
  may have been withheld (SLC6A1, KCNMA1, SCA12, SPG4) — if the variant isn't in the prompt, the best
  reachable answer is a *named gene-panel candidate*, not the exact variant; scoring should reward
  the entity, not the variant string.

**First-pass automated scan (2026-06-14):** 23/24 prompts contain a definitive deciding-result token
(variant/sequencing/PCR/biopsy/titer/"revealed"); only **PMC13233052 (KCNMA1)** flags as likely
under-determined (genetic gold, no variant/sequencing result in the prompt). Implication: the large
majority are genuinely *reachable* — these are harness/model failures, not flawed cases, which is the
strong version of the result (the harness really can improve here). Caveat: the scan is a keyword
heuristic; for the genetic entities where the prompt includes the gene/variant, scoring should reward
the named **entity**, not the exact variant string. **Next (deeper):** fetch each source abstract and
hand-confirm the reachable column for the paper's methods section.

## Eval-mode + cited-report requirements (product-level, see implementation)

11. **Eval mode (anti-cheat):** never retrieve/read the source paper (by pmcid/doi/title) — retrieval
    filter *plus* prompt-level guards. Off by default for the doctor use case.
12. **Cited diagnostic report:** the deliverable lists each useful paper (title/PMID/DOI) and exactly
    *how* it contributed to the diagnosis. This is the project's purpose — information retrieval for
    doctors, not a doctor replacement.
