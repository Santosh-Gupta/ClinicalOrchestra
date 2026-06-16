# Harness Evolution Ideas — 2026-06-13

Grounded in the failure analysis of the Pro-failed 22-case set (see
[Harness Improvements](harness_improvements_20260613.md)). Ordered by leverage.

## Theme 1 — attack the measured failure modes (variance & anchoring)

1. **Self-consistency sampling — IMPLEMENTED (first delivery).** 5 of 7 residual fails were
   run-to-run variance at greedy decoding (myeloid sarcoma↔DLBCL, angiosarcoma↔EHE,
   clavata↔capitata, committed↔hedged optic glioma). Sample the answer model k times, cluster the
   final diagnoses, majority-vote, and report the winning-cluster fraction as a calibrated
   confidence. See "Implementation" below.
2. **Generalize per-case gates into feature-indexed reasoning principles.** 50+ presets keyed by
   case ID is teaching-to-the-test-adjacent and will not transfer to new cases. The gates that work
   are instances of ~8 cross-cutting heuristics ("a single positive antibody/marker does not
   override the phenotype"; "species/subtype needs a confirmatory test, not a prevalence guess"; "an
   unexplained finding ⇒ consider a second/synchronous pathology"; "a benign entity can mimic a
   malignant mass"; "commit to one entity"). Select them by detected case *features*, not PMC ID.
3. **Forced strongest-alternative pass.** One adversarial turn: produce the lead diagnosis, then
   argue the best rarer/competing entity mapping each retrieved discriminator to a case finding,
   then reconcile. Generalizes better than hand-authored mimic pairs.

## Theme 2 — evaluation integrity

4. **Control set + ablations.** The harness is tuned on cases it was designed to pass; the
   PMC9332052 MANEC regression proved gates can *hurt* previously-passing cases. Need (a) a held-out
   set of cases Flash already passes to detect regressions, and (b) component ablations (relevance
   filter / gates / sampling on-off) to attribute the gains.
5. **Judge rubric + ensemble + calibration set.** Pro vs Flash disagreed on the hibernoma key.
   Replace the single holistic judge call with a structured rubric (same entity? lineage? species?
   acceptable qualifier?) and/or majority-of-3, and hand-label ~30 (candidate, key, verdict) pairs
   to *measure* the judge's error rate. (Secondary-judge fallback is already implemented.)
6. **Evidence-grounded answers.** Require each discriminator to cite the retrieved snippet that
   supports it, and verify the snippet actually says so — makes retrieval load-bearing and guards
   against hallucination. ("No citation support checker exists yet" per the original handoff.)

## Theme 3 — protect the benchmark signal

7. **Automated data-quality auditing.** 3 defects in 22 cases (2 broken prompts + 1 borderline key).
   Add: a post-transform validator (transformed prompt must retain the source's discriminating
   tokens — would have caught both fixed cases); a solvability probe (if a strong model with full
   reasoning cannot reach the key from the prompt alone, the prompt is underdetermined, not "hard");
   an answer-key schema `{primary_entity, acceptable_synonyms, required_specificity}` to make judging
   deterministic.
8. **Multi-axis scoring.** Binary pass/fail loses signal. Score entity / lineage / management
   separately ("benign neural tumor, wrong subtype" > "sarcomatoid RCC"); also score the
   next-management-step, currently ignored.

**Recommended sequence:** 1 (done) → 4 (done, below) → 2 → 5 → 7.

## Implementation: control set + ablations (#4)

`HarnessConfig` feature toggles (default = full harness) make each learned component removable so
its contribution can be measured:

- `use_gates` — inject finalization gates + anchor mimic pair/risks into prompts.
- `use_contrast_queries` — the symmetric "A versus B" retrieval query.
- `use_relevance_filter` — off-topic re-query + zero-relevance suppression.

CLI flags: `--no-gates`, `--no-contrast-queries`, `--no-relevance-filter`. Threaded through query
building, evidence retrieval/ranking, distillation, and the final prompt; unit-tested
(`test_ablation_*`).

**Ablation design.** On gate-dependent cases (ones that flipped *because* of a gate:
prion sFI, actinomycosis, TB-sarcoid overlap, Malassezia speciation, intrarenal neurofibroma,
myeloid sarcoma), run gates-ON vs `--no-gates` with retrieval/relevance/contrast held constant. A
drop when gates are removed shows the gates are load-bearing rather than the retrieval alone.

**Control set.** `runs/control_manifest_flashpass.jsonl` = 10 cases `deepseek-v4-flash` already
passes closed-book (drawn from NeurologyBM flash-pass lists). Running them through the full harness
checks for *regressions* — i.e. that adding retrieval/gates does not break cases the model already
gets right. (Note: control cases map to the `general` preset, which carries no gates, so this run
primarily stresses whether injected retrieval evidence distracts the model.)

### Results

**Ablation — gates are load-bearing.** On 6 gate-dependent cases (corrected manifest, Flash answers,
Flash judge), holding retrieval/relevance/contrast constant and toggling only the gates:

| Config | Pass |
| --- | --- |
| gates ON | **4 / 6** |
| gates OFF (`--no-gates`) | **0 / 6** |

Removing the finalization gates drops every one of these cases. The principle-style gates do real
reasoning work; they are not passing because retrieval handed over the answer. (2 of the 6 —
prion sFI, actinomycosis — failed even with gates ON this run, consistent with the known run-to-run
variance; the gates-vs-no-gates contrast is nonetheless unambiguous.)

**Control — retrieval is double-edged, and regresses cases the model already knows.** 10 cases Flash
passes closed-book, run with retrieval disabled vs the full harness (everything else identical, so
this isolates the effect of the *retrieved evidence*):

| Config | Pass |
| --- | --- |
| closed-book (`--no-retrieve`) | **9 / 10** |
| + retrieval | **7 / 10** |

Two cases regressed *because of* retrieval (`PMC3271452` renal leiomyosarcoma → sarcomatoid RCC;
`PMC3488471` CADASIL → PACNS) — both drifting to a more common/famous mimic that the retrieved
literature surfaced. Zero of the 9 already-correct cases were *improved* by retrieval. (The third
control miss failed both ways — variance, not a regression.)

**Conclusion.** Gates help and are load-bearing. Retrieval helps *hard* cases (it was part of the
3→18 gain) but actively *hurts* cases the model already knows, by anchoring it on a relevant-but-
wrong retrieved entity. **Retrieval should be gated on need, not applied unconditionally.** The
natural control signal already exists: self-consistency *agreement*. High closed-book agreement →
trust the model, skip or down-weight retrieval; low agreement / unstable differential → retrieve.
This unifies ideas #1 and #4 into a concrete next step, and makes the control set a permanent
regression guard for any future change.

## Implementation: self-consistency (#1)

- `src/clinical_harness/consensus.py`: `consensus_diagnosis` (deterministic string clustering — cheap,
  no model calls) and `consensus_diagnosis_judged` (LLM-judge equivalence clustering — unifies
  abbreviation/synonym variants the string version cannot, e.g. "AML with t(8;21)" ==
  "Acute myeloid leukemia with t(8;21); RUNX1-RUNX1T1"). Both return a `ConsensusResult` with the
  representative diagnosis and an `agreement` fraction.
- Wired into `run_retrieval_guided_manifest_eval(..., samples=k, sample_temperature=t)` and the CLI
  flags `--samples` / `--sample-temperature`. With a judge available, clustering uses the judge;
  otherwise it falls back to string clustering. The chosen answer is the majority cluster's
  representative; `agreement` and all sample diagnoses are written to the response artifact and the
  results TSV.

Usage:

```bash
clinical-harness benchmark retrieval-guided-eval \
  --manifest runs/manifest_corrected2_20260613.jsonl --out-dir runs/<dir> \
  --max-rounds 2 --max-queries 3 --distill-evidence \
  --judge --judge-model deepseek-v4-pro --samples 5 --sample-temperature 0.5
```

### First results (k=5, temp 0.5, judge clustering) on the 4 high-variance cases

| Case | Key | Samples (mode) | Agreement | Outcome |
| --- | --- | --- | --- | --- |
| PMC3824813 | myeloid sarcoma | myeloid sarcoma ×2, "indeterminate DLBCL vs myeloid" ×2, empty ×1 | 0.40 | **PASS** (recovered) |
| PMC11039432 | malignant optic glioma / GBM | "adult malignant optic glioma (GBM, IDH-wt)" ×4, empty ×1 | 0.80 | **PASS** (commitment fixed) |
| PMC2413251 | intraosseous angiosarcoma | telangiectatic osteosarcoma ×4, angiosarcoma ×1 | 0.80 | FAIL (confidently wrong) |
| PMC11980373 | Saprochaete clavata | S. capitata ×3, Geotrichum candidum ×2 | 0.60 | FAIL (confidently wrong) |

**Key finding — self-consistency is a diagnostic, not a silver bullet.** It separates two things
the single-run number conflated:

- **True variance** (the answer is the mode, or only the *commitment* was unstable): recovered.
  PMC3824813 now lands on myeloid sarcoma; PMC11039432's hedge collapses to a clean committed GBM.
- **Systematic bias** (the model is *confidently wrong* — high agreement on the wrong mimic):
  exposed, not fixed. PMC2413251 (4/5 say telangiectatic osteosarcoma) and PMC11980373 (0/5 reach
  *clavata*) are not noisy — the earlier "passes" were lucky minority samples. These need better
  reasoning/retrieval (or are beyond Flash), and more sampling will not help.

The agreement fraction makes this actionable: **low agreement → sample more / retrieve more;
high agreement + fail → the model is anchored, invest in gates/retrieval, or flag as out-of-reach.**
This directly motivates evolution ideas #2 (principle gates) and #6 (evidence grounding) for the
confidently-wrong cluster, and validates reporting agreement alongside pass/fail.
