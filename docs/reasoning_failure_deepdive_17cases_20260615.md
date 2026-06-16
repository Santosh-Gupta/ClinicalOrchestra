# Deep dive: the 17 cleaned cases the harness still fails (2026-06-15)

These are the cases that, AFTER mending (deciding result added, gold preserved), still fall outside the
harness's top-5. We expected "the model has the info and reasons wrong." Reading each case's mended
prompt + the harness's ranked-5 + its reasoning trace + the source paper, the 17 split into six
mechanisms — and ~5 of them are STILL broken cases of types the determinacy validator did not catch.
That pushes the true reasoning-failure count well below 17 (so the real solve-rate is even higher than
the 92% headline).

## Category 1 — Comorbidity / conjunction not represented (the model HAS the parts) [~4 cases]

The gold is a coexistence of two conditions; the model lists **both components in its top-5 as
separate entries** but never the conjunction, so exact-match scoring fails.
- **PMC13214945** gold = *bvFTD AND anti-GAD65 AE*. Top-5 has bvFTD (#1) and anti-GAD65 AE (#3)
  separately. Worse, its discriminator_summary mis-reads the (now-added) GAD65 titer "60 UI/mL (ref
  0–5)" as *"refutes AE, supports neurodegeneration"* — a real titer-interpretation error — and
  collapses to pure bvFTD.
- **PMC13110972** gold = *coexistent ALS AND CIDP*; top-5 is all ALS variants (missed the CIDP overlay).
- **PMC13236903** gold = *triple-antibody overlap (MOG+NMDAR+…)*; top-5 #1 = "MOG and NMDAR overlap" —
  got 2 of 3.
- **PMC13219314** gold = *AE (low-titer CASPR2) WITH underlying tumor*; top-5 has CASPR2-AE (#1) and
  glioma (#3) separately.
**FIX (general, high value):** (a) instruct the model that a candidate may be a CONJUNCTION ("A + B
co-occurring") and to emit it as a single ranked entry when features span two processes; (b) scoring:
credit a comorbidity gold when *all* its components appear in the top-5. This alone likely reclaims
several. It is a representation/scoring gap, not a knowledge gap — the model already found the parts.

## Category 2 — Dangerous anchoring on the prototype despite explicit contrary cues [~2–3]

- **PMC13239290 (HSV-1 encephalitis).** The prompt literally says *"psychiatry recommended expanding
  workup to include infectious, autoimmune, inflammatory etiologies,"* yet the top-5 = DLB, NPH, AE,
  PSP, SREAT — **no infectious/HSV at all.** The visual-hallucinations→DLB anchor dominated and the
  universal "exclude HSV before AE" gate did not override it. The gold is reachable; this is a pure,
  dangerous anchoring failure.
- **PMC13096564 (reflex/startle epilepsy).** The mend added a *HEXA VUS (variant of uncertain
  significance)* from the source; the model dove straight to **Tay-Sachs and the GM2/GM1 gangliosidoses
  (all HEXA-adjacent)** — treating a VUS as diagnostic and ignoring the startle-triggered seizure
  semiology that defines the gold. Two lessons: a VUS must be DOWN-weighted (uncertain ≠ causal), and
  the mend can inject a red herring (faithful to the source, but misleading) — flag VUS additions.
**FIX:** strengthen the contrary-cue override (an explicit "consider infectious" / a VUS must change
ranking); add a "VUS is not diagnostic" reasoning gate.

## Category 3 — INVALID challenge: source is a research/methods paper, gold is not a clinical diagnosis [~2] — NEW broken class

- **PMC13219288.** Source is a basic-neuroscience study of *hemispheric emotional valence*; the "gold"
  — *"hemispheric dissociation of anxiety and autonomic arousal during lateral visual-field viewing"* —
  is an experimental construct, not a diagnosis. The model reasonably said MDD/GAD.
- **PMC12328450.** Source is about *awake-craniotomy language mapping*; the "gold" — *"atypical
  right-hemisphere language representation"* — is an intraoperative mapping finding. The model
  reasonably reasoned about glioma progression.
These are not solvable as diagnostic challenges and should be **dropped**. The determinacy validator
missed them because they aren't specificity defects. **NEW validator rule:** flag cases whose source is
not a diagnostic case report (research/methods/mechanism paper) or whose gold is not a clinical
diagnosis (a neuroscience construct, a mapping/experimental finding).

## Category 4 — Prompt evidence REFUTES the gold [~1] — NEW broken class

- **PMC11743964.** Gold = *psychosis from right-temporal anaplastic astrocytoma recurrence*. But the
  mended prompt states *"MRI with/without contrast showed stable findings WITHOUT evidence of tumor
  recurrence"* and *urine positive for methamphetamine*. The model's #1 (methamphetamine-induced
  psychosis) is the BEST answer to the prompt as written. The gold requires concluding recurrence
  **against** a negative MRI — not supportable from the prompt. **NEW validator rule:** flag cases where
  the prompt contains a result that REFUTES the gold (a negative/normal test for the gold entity), or
  where the gold depends on data the prompt explicitly says is absent.

## Category 5 — Genuine phenotype→gene knowledge/retrieval gap on a determinable case [~1–2]

- **PMC13068090 (KCTD17 myoclonus-dystonia).** Mend added *"WES negative for TOR1A/GCH1/SGCE/ANO3."*
  Source states KCTD17 is the recognized next M-D gene after SGCE. The model's top-5 = ADCY5, KCNN2,
  ATP1A3, **SGCE (which the prompt says is NEGATIVE)**, Tourette — KCTD17 absent. Two failures: it
  ignored a stated negative (listed SGCE) and lacked the phenotype→gene knowledge (KCTD17 after
  SGCE-negative). Reachable via phenotype→gene retrieval; also the mend was imperfect (added negatives,
  not the positive KCTD17 variant — so partly still under-determined at the exact-gene level).
**FIX:** phenotype→gene retrieval for "SGCE-negative myoclonus-dystonia → KCTD17"; a "respect stated
negatives" reasoning gate (do not rank an entity the prompt has excluded).

## Category 6 — Multi-axis / anchored-on-wrong-axis / near-miss wording [~4–5]

- **PMC13250257 (Illness Anxiety Disorder)** — anchored on the *movement* phenotype (functional/HD
  phenocopy/chorea); the core is health anxiety. #5 "anxiety with psychogenic movement" is close.
- **PMC12926095** — gold is a *multi-axis* developmental profile (borderline IQ + ADHD + language, NOT
  autism); model gave single-axis ADHD (#1) with ASD #2. Needs multi-axis output (overlaps Cat 1).
- **PMC8519172 (ketamine encephalatrophy)** — #1 = "chronic ketamine abuse-related…": likely a wording
  near-miss the judge rejected; inspect judge strictness.
- **PMC13049788** — congenital vascular-anomaly *combination*; model gave single mechanisms (Bow
  Hunter's, subclavian steal). Overlaps Cat 1 (conjunction).
- **PMC13220061 (statin rhabdomyolysis + mixed neuro)** — model split into necrotizing myopathy /
  GBS / toxic myopathy; gold is the mixed picture (overlaps Cat 1).

## Headline implications

1. **The 17 are NOT all reasoning failures.** ~5 are still-broken cases of two NEW classes (research-
   finding gold; prompt-refutes-gold). Removing them, the genuine reasoning-failure tail is ~12, and the
   real end-to-end solve-rate is **higher than 92%**.
2. **The single highest-value GENERAL fix is conjunction/comorbidity handling** (Cat 1 + parts of 6):
   the model already finds the components; let it emit and be scored on the conjunction. Likely reclaims
   ~4–6 cases across both dev sets.
3. **Two validator extensions** (Cat 3, 4) for NeurologyBM, and a **VUS / stated-negative reasoning
   gate** (Cat 2, 5) for the harness — all general, all grounded in real cases.
4. **The mend pipeline can inject red herrings** (a VUS) — flag VUS/uncertain additions rather than
   stating them as plain findings.

## Prioritized actions

- **Harness (general):** conjunction-aware output + comorbidity scoring credit; "respect stated
  negatives" and "a VUS is not diagnostic" gates; strengthen contrary-cue override of the prototype.
- **NeurologyBM validator (general):** add `gold_not_a_diagnosis` (research/methods source) and
  `prompt_refutes_gold` flags; flag VUS-only "confirmations" in mends.
- **Re-score** after conjunction credit + dropping the ~5 still-broken cases → the clean reasoning-tail
  number.
