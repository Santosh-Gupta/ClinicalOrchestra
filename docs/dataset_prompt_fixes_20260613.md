# Dataset Prompt Fixes — 2026-06-13

Two transformed cases in the Pro-failed set were **underdetermined**: their transformed challenge
prompt dropped or altered the findings a clinician needs to reach the keyed diagnosis, violating
the design rule that a challenge prompt must give any doctor all starting information needed to
make the diagnosis and next step, without leaking the outcome. Both were already flagged
`refine_review_status: refined_needs_spotcheck`.

The corrected prompts were reconstructed from the open-access (CC-BY / CC-BY-NC) source articles
and restore only the objective findings — no diagnosis name, no outcome. Canonical text lives in
[`scripts/corrected_case_prompts.py`](../scripts/corrected_case_prompts.py).

## `transformed_PMC12581184` — Neuropsychiatric SLE (NPSLE)

Source: *Psychosis-predominant neuropsychiatric lupus in a severely malnourished adolescent*,
Archive of Clinical Cases, DOI 10.22551/2025.48.1203.10327, PMC12581184.

| Finding | Source article | Transformed prompt (broken) | Corrected |
| --- | --- | --- | --- |
| ANA | 1:1280 | **omitted** | restored (1:1280) |
| anti-dsDNA | >300 IU/mL | **omitted** | restored (>300 IU/mL) |
| Brain MRI/CT | negative | **fabricated** "subcortical white-matter hyperintensities" | corrected to negative |
| CSF | WBC 17, protein 52 | WBC 10, protein 65 | aligned to source |

Without the ANA/anti-dsDNA, NPSLE is not derivable and anti-NMDA encephalitis is the most
reasonable read of the prompt — which is exactly what both DeepSeek models answered. With the
serologies restored, `deepseek-v4-flash` under the harness now commits to NPSLE (verified pass).

## `next_transformed_PMC11066795` — Intrarenal neurofibroma

Source: *Intrarenal neurofibroma: unveiling a diagnostic challenge*, Journal of Surgical Case
Reports, DOI 10.1093/jscr/rjae285, PMC11066795.

The transformed prompt provided only imaging and left histology **"pending"**, while asking for
"the pathological diagnosis and confirmatory IHC." The source article itself states neurofibroma
has no pathognomonic imaging features and is diagnosed **only on histopathology** — so the prompt
withheld its entire diagnostic basis. Restored from the source case:

- Gross: 6 x 6 x 5 cm well-circumscribed, encapsulated tumor, yellowish cut surfaces, confined to
  the lower pole, no Gerota's fascia invasion.
- Microscopy: spindle-cell tumor with **serpentine, wavy nuclei** in a fascicular pattern.
- IHC: tumor cells **focally S100 positive**, **SMA and desmin negative**.
- Para-aortic lymph nodes free of malignancy.

With the histology restored the case becomes a fair neurofibroma-vs-schwannoma discrimination.
This also surfaced a harness bug: the `renal_spindle_cell_mass` finalization gate over-weighted
*encapsulation* (which pushed the model to schwannoma). The gate was corrected to the proper
pathology discriminator — **focal** S100 + serpentine wavy nuclei + **absence of Verocay
bodies/Antoni A-B** = neurofibroma; **diffuse** strong S100 + Verocay + Antoni = schwannoma;
encapsulation is not decisive. After the gate fix, Flash commits to neurofibroma (verified pass).

## Canonical propagation

The corrected `challenge_prompt` (plus `prompt_correction_note` and `prompt_correction_date`
provenance fields) was written to every NeurologyBM JSONL that carries the prompt for these case
ids — 18 records across 17 files — each with a `*.bak_20260613` backup:

- `transformed_PMC12581184`: 11 files (incl. `all_public_deepseek_v4_pro_failed_manifest_20260613`,
  `ready_llm_eval_manifest_20260611`, `ready_38_flash_fail_pro_still_fail_manifest_20260613`, the
  `public_refine_20260611T100758Z/refined_cases.jsonl` source-of-truth, and the dated 0609/0610
  snapshots).
- `next_transformed_PMC11066795`: 6 files (incl. `next100_final_fail_for_harness_manifest_20260613`,
  `next100_ready_manifest_20260612`, the `public_refine_20260612T221437Z/refined_cases.jsonl`
  source-of-truth).

To revert: restore the `*.bak_20260613` files. If NeurologyBM regenerates manifests from a source
pipeline, apply the corrected prompts at the transformation step so the fix is not overwritten.

## Process recommendation

Both failures share a root cause: the transformation step can silently **drop the discriminating
lab/path findings** (and in one case fabricate an imaging finding). Recommend a post-transform
validator that checks the transformed prompt still contains the key findings present in the source
(e.g. required serologies/IHC tokens), and routes any case missing them to human review before it
enters the benchmark.
