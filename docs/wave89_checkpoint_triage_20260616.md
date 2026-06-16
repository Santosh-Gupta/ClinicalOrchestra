# Eighth + Ninth wave generalization checkpoint — failure triage (2026-06-16)

Fresh generalization set: eighth-wave 47-strict + ninth-wave 8-strict = **55 cases** (neither tuned
on). Both run through `validate-cases` first; strict sets inspected clean (prompts present, golds
well-formed under `answer_key.diagnosis`, drop/mend reasoning sound).

## Three-stage funnel (artifacts in `data/eval/wave89_checkpoint/`)

| Stage | Model | Result |
|---|---|---|
| 1 — bare | v4-flash | 40 pass / 15 fail (73%) |
| 2 — bare on the 15 | v4-pro | 5 pass / 9 fail / 1 inconclusive¹ |
| 3 — harness on the 10² | v4-flash | pass@1 = 1, pass@5 = 4 |

**End-to-end: pass@1 = 46/55 (84%), pass@5 = 49/55 (89%)** — squarely in the established cleaned-set
band (88–92%); the system generalizes to fresh data.

¹ PMC12237386 — persistent `IncompleteRead(0 bytes)` on Pro after 6 retries; prompt is small (2 KB),
so a Pro-side connection drop, not oversized context. Carried into Stage 3 as a confirmed Flash-fail.
² 9 confirmed double-failures + the 1 inconclusive.

Of the 4 harness wins, 3 were at gold_rank 2–3 (present-but-mis-ranked) — the **SELECTION** bottleneck
again, not retrieval.

## The 6 residual (pass@5-fail) cases — diagnosed per the IR / reasoning / broken framework

| case | gold | model rank-1 | class |
|---|---|---|---|
| PMC12091614 | ADEM | cerebral venous thrombosis | **reasoning** — classic post-infectious multifocal-FLAIR + encephalopathy ADEM pattern fully present; anchored vascular, ADEM absent from top-5 |
| PMC12946650 | GBS, ASMAN variant | GBS, AMAN variant | **reasoning (subtype)** — prompt states sensory involvement (the ASMAN discriminator); model dropped it. Borderline over-specific subtype |
| PMC13245828 | venous hypertensive myelopathy from cervical rhabdomyolysis | acute transverse myelitis | **IR** — only 7 evidence items; niche mechanism (rhabdo→venous hypertensive myelopathy) not retrieved |
| PMC13239140 | pulmonary spindle-cell carcinoma w/ rhabdoid diff. | malignant rhabdoid tumour (SMARCB1) | **IR/knowledge + mis-scoped** — hard pathology; also a *pulmonary* case that slipped into a neuro batch |
| PMC10853645 | autoimmune-thyroid focal CNS disorder *without* encephalopathy | SREAT / Hashimoto encephalopathy | **over-specific / bespoke gold** — model identified the mechanism (TPO-Ab-mediated CNS disorder); gold's label + "without encephalopathy" hair-splits a standard parent entity |
| PMC12237386 | V4 vertebral-artery connecting-artery anomaly + DKA | persistent primitive hypoglossal artery | **near-miss + conjunction** — right category (rare congenital posterior-circ. vascular anomaly → strokes), wrong specific variant, missed the DKA conjunct |

### Headline
Even the residual failures are mostly "right neighbourhood." The frontier is **subtype granularity
and de-anchoring**, not retrieval coverage — consistent with the project thesis. Breakdown: 2 reasoning
(ADEM anchoring; ASMAN stated-discriminator), 2 IR (myelopathy low-retrieval; pulmonary pathology),
2 gold-quality (bespoke/over-specific label; over-specific anatomical variant + dropped conjunct).

## Actionable, GENERAL follow-ups (no difficulty gate)

1. **NeurologyBM `validate-cases` gap (highest value).** Two kept "determinable" cases (PMC10853645,
   arguably PMC12946650) have golds whose *distinguishing qualifier* — a subtype/variant name, a
   present/absent feature, or a bespoke non-standard label — is **not fairly determinable from the
   prompt** vs a standard parent entity. The current specificity check guards withheld *results*, not
   *granularity/labeling*. Add a check: flag golds that (a) name a subtype/variant whose discriminator
   isn't in the prompt, or (b) use a bespoke label when a standard parent diagnosis fits the prompt
   equally. Repair = relabel to the determinable parent (gold truth preserved at the supported
   granularity), else drop. This is a benchmark-quality fix, not a harness fix.
2. **Data-agent scoping:** PMC13239140 is a pulmonary-oncology case in a neuro batch — tighten the
   neuro/psych intersection filter.
3. **Harness de-anchoring (ADEM):** a broad-differential / pattern-completion lever (don't let a
   vascular anchor evict common inflammatory-demyelinating entities) is indicated — but per the
   measurement-wall conclusion, adopt only on **multi-seed** evidence, not this single case.

## Measurement note
At pass@5 the residual N is 6, and 2 of those are gold-quality artifacts. Single-fix harness deltas
remain below the judge-variance floor; the genuine unlock is still (a) multi-seed headline comparisons
and (b) feeding finding #1 back into benchmark generation so the dev sets stop carrying
subtype-granularity noise.
