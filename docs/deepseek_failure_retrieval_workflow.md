# DeepSeek Failure Retrieval Workflow

Last refreshed: 2026-06-11.

This is the working spec for turning failed single-call DeepSeek diagnoses into reusable, retrieval-guided ClinicalHarness workflows. The immediate target is the 30 public ready case challenges that both `deepseek-v4-flash` and `deepseek-v4-pro` failed. The first milestone should focus on the neuro/neuropsychiatry-heavy subset, then generalize to rare tumors/pathology, infection/inflammatory mimics, and derm/drug/genital lesion edge cases.

This document is intentionally stored in ClinicalHarness. NeurologyBM remains the owner of dataset construction, source licensing, splits, answer keys, and benchmark exports.

## Benchmark Inputs

Read these as external inputs. Do not edit them from this repo.

| Input | Path |
| --- | --- |
| Ready manifest, 81 public cases | `/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/ready_llm_eval_manifest_20260611.jsonl` |
| 30 Pro-still-failed case IDs | `/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/ready_38_flash_fail_pro_still_fail_case_ids_20260612.txt` |
| Pro rescue comparison for 38 Flash failures | `/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/ready_38_flash_fail_pro_rescue_comparison_20260612.tsv` |
| Pro answers | `/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/deepseek_runs/deepseek_public_20260612T000541Z/results.tsv` |
| Pro scores | `/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/deepseek_runs/deepseek_public_scores_20260612T001940Z/scores.tsv` |
| Flash answers on ready 81 | `/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/deepseek_runs/deepseek_public_20260611T224853Z/results.tsv` |
| Flash scores on ready 81 | `/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/deepseek_runs/deepseek_public_scores_20260611T230530Z/scores.tsv` |
| Ready corpus report | `/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/ready_81_flash_v4_eval_report_20260611.md` |

Private files under `/Users/santoshg/Coding/NeurologyBM/docs/DO NOT COMMIT TO GITHUB` are not part of the first pass and must not be copied into public artifacts.

## Benchmark State

The ready 81-case public manifest has already been filtered by NeurologyBM for non-empty prompt, self-contained starting prompt, Pro leakage audit, lexical diagnosis/alias leakage audit, and exclusion of non-case/retraction/review/aggregate-only sources.

Baseline:

| Model/run | Pass | Partial | Fail | Ungradable |
| --- | ---: | ---: | ---: | ---: |
| `deepseek-v4-flash` on ready 81 | 16 | 25 | 38 | 2 |
| `deepseek-v4-pro` on the 38 Flash failures | 4 | 3 | 30 | 1 |

## Hard Rules

- Do not retrieve by source title, DOI, PMCID, article title, or exact quoted prompt.
- The challenge prompt is the starting clinical information available to the diagnostic agent.
- Answer key, outcome, source article, and model failure notes are evaluation-only. They must not be visible to the diagnostic agent during test runs.
- Retrieval may use PubMed, PMC, guidelines, reviews, case series, disease criteria, pathology/IHC references, imaging discriminators, and biomedical ontologies.
- Store structured reasoning artifacts, not hidden chain-of-thought: problem representation, first differential, retrieval plan, evidence summaries, evidence map, differential updates, decision points, final answer, and evaluator notes.
- Preserve public/private boundaries and license tier metadata from NeurologyBM.

## Initial Target Cases

The neuro/psych-style failures are the best first milestone because they stress localization, mimics, and discriminating tests:

| Case ID | Expected diagnosis/key | Pro failure pattern | Retrieval lesson |
| --- | --- | --- | --- |
| `transformed_PMC10399123` | Pediatric-onset multiple sclerosis | Anchored on MOGAD | Retrieve demyelinating disease criteria, transient low-titer MOG significance, and CSF-specific OCB discriminators. |
| `transformed_PMC10409533` | Steroid-responsive lymphomatous infiltration / likely CNS lymphoma | Anchored on Ramsay Hunt | Search immunosuppression, cranial neuropathy, steroid response, lymphomatous infiltration, and biopsy/imaging discriminators. |
| `transformed_PMC10540759` | Cerebral venous sinus thrombosis | Anchored on MELAS | Retrieve headache/seizure/stroke-like differential with venous imaging findings and CVST risk factors. |
| `transformed_PMC12581184` | Neuropsychiatric SLE psychosis | Anchored on anti-NMDA encephalitis | Search psychiatric presentation with systemic autoimmune markers, SLE criteria, and autoimmune encephalitis mimics. |
| `transformed_PMC3214133` | Sporadic fatal insomnia | Anchored on iatrogenic CJD | Retrieve prion insomnia/autonomic syndrome discriminators, sleep study findings, and exposure history logic. |
| `transformed_PMC5516732` | Primary angiitis of the CNS | Anchored on RCVS | Retrieve PACNS vs RCVS, vessel-wall MRI, CSF inflammation, biopsy, angiographic course, and thunderclap/time-course discriminators. |
| `transformed_PMC6179031` | Occipital epilepsy | Anchored on Charles Bonnet syndrome | Search visual hallucination differential with EEG, seizure semiology, and ophthalmologic mimic separation. |
| `transformed_PMC7678886` | Seronegative autoimmune encephalitis | Mis-specified as anti-LGI1 | Retrieve seronegative AE criteria, antibody-negative workup, syndrome-based AE diagnosis, and exclusion criteria. |
| `transformed_PMC8115684` | Leptomeningeal carcinomatosis | Anchored on cervical artery dissection | Retrieve multifocal cranial neuropathy/radiculopathy, CSF cytology, leptomeningeal enhancement, and cancer history discriminators. |
| `transformed_PMC8143662` | Tethered cord syndrome | Anchored on conversion disorder | Enforce functional diagnosis only after sacral/autonomic/localizing spinal signs and MRI discriminators are checked. |

## Per-Case Analysis Artifact

For each of the 30 still-failed cases, produce a row with:

| Field | Meaning |
| --- | --- |
| `case_id` | NeurologyBM case id. |
| `cluster` | Neuro/psych, rare tumor/pathology, infection/inflammatory mimic, derm/drug/genital edge case, or other. |
| `prompt_available_to_agent` | Yes/no; should always be yes for ready public cases. |
| `expected_key_answer` | Evaluation-only. |
| `flash_failure` | Short summary of Flash wrong answer and why it failed. |
| `pro_failure` | Short summary of Pro wrong answer and why it failed. |
| `organ_system_alignment` | Right system, adjacent system, or wrong system. |
| `anchor_or_mimic` | Common mimic or misleading diagnosis the model over-weighted. |
| `missed_discriminator` | Test, imaging, pathology, lab, time course, epidemiology, or management feature. |
| `retrieval_need` | Criteria, review, case series, guideline, pathology/IHC table, imaging review, or phenotype/disease graph. |
| `ideal_retrieval_sequence` | Ordered concept queries, never title/DOI/PMCID/exact prompt search. |
| `evidence_update_rule` | What evidence should move the differential. |
| `generalizable_rule` | Reusable heuristic learned from this case. |
| `guided_flash_result` | Pass, partial, fail, untested. |
| `retrieved_docs_used` | Evidence IDs used by the final answer. |

## Prototype Controller

The first guided workflow should be deterministic around the model, not a single free-form chat.

1. **Intake**
   - Input: challenge prompt only.
   - Output JSON: age, sex, tempo, syndrome, localization, key positives, key negatives, prior diagnoses/treatments, labs, imaging, pathology, management question.
   - Instruction: do not diagnose yet.
2. **First Differential**
   - Generate 5-10 candidates.
   - Mark each as `common`, `dangerous`, `rare_but_fits`, or `mimic`.
   - Identify discriminating facts needed.
3. **Retrieval Plan**
   - Ask what documents would reduce uncertainty most: diagnostic criteria, imaging discriminators, pathology/IHC tables, management guidelines, rare disease reviews, case-series tables, syndrome localization reviews, or test interpretation references.
4. **Query Generation**
   - Generate concept queries from findings, not source identifiers.
   - Query types:
     - `[syndrome] differential diagnosis [key imaging/pathology]`
     - `[finding A] [finding B] [finding C] case report`
     - `[disease mimic 1] versus [disease mimic 2] MRI`
     - `[IHC markers] [tumor location] diagnosis`
     - `[psychiatric presentation] [autoimmune marker/lab/systemic feature]`
     - `[neurologic symptom] [normal MRI/EEG or specific MRI] differential`
5. **Retrieval And Evidence Extraction**
   - For each document, summarize only clinically relevant discriminators.
   - Extract criteria, required findings, exclusion rules, key mimics, and next management steps.
   - Do not copy long source text.
6. **Differential Update**
   - Re-rank the differential.
   - State which finding rules in/out each top contender.
   - If uncertainty remains, request another retrieval round focused on the highest-yield discriminator.
7. **Final Answer**
   - JSON fields: `final_diagnosis`, `etiology`, `top_differential`, `recommended_next_step`, `confidence`, `evidence_summary`, `uncertainty_or_missing_information`, `retrieved_docs_used`.
8. **Evaluation**
   - Compare against answer key after the run.
   - Output: pass, partial, fail; diagnosis status; next-step status; rationale status; retrieval step that made the difference; generalizability.

## Pro-Assisted Scaffold Design

Use `deepseek-v4-pro` as an offline workflow analyst, not as the diagnostic agent being evaluated. Its job is to compare:

- the challenge prompt available to the agent;
- the failed Flash and Pro answers;
- the evaluator-only answer key and original paper outcome/discussion excerpt;
- the no-shortcut retrieval rules.

The output should be retrieval scaffolding: what knowledge was missing, what document type should have been retrieved, what concept queries are allowed, what evidence should update the differential, and what general rule should become part of ClinicalHarness.

Export analysis packets:

```bash
clinical-harness benchmark deepseek-packets \
  --subset neuro_psych \
  --out runs/deepseek_failure_packets/neuro_psych.jsonl
```

Export all 30 still-failed cases:

```bash
clinical-harness benchmark deepseek-packets \
  --subset all \
  --out runs/deepseek_failure_packets/all_30.jsonl
```

Each JSONL row has:

- `diagnostic_agent_input`: challenge prompt and blocked retrieval shortcuts;
- `evaluator_only`: answer key, next step, source identifiers, license metadata, and paper outcome/discussion excerpt;
- `failed_model_outputs`: Flash and Pro outputs plus score rationales;
- `comparison_prompt`: a ready prompt for Pro to return strict JSON retrieval-scaffold recommendations.

The diagnostic agent run must only receive `diagnostic_agent_input` plus retrieved evidence. It must not receive `evaluator_only` or the Pro scaffold analysis until after scoring.

## Reusable Retrieval Heuristics

| Heuristic | Trigger | Retrieval move |
| --- | --- | --- |
| Psychiatric presentation with organic mimics | Psychosis, catatonia, insomnia, cognitive change, seizures, systemic autoimmune clues | Search AE criteria, NPSLE, toxic/metabolic, prion, endocrine, infection, and systemic disease discriminators. |
| Visual hallucination vs seizure vs ophthalmologic mimic | Visual phenomena, preserved insight, visual field defect, normal/abnormal eye exam | Search occipital epilepsy semiology, EEG utility, Charles Bonnet criteria, migraine aura, and structural occipital lesions. |
| Seronegative autoimmune encephalitis | AE phenotype but antibody negative or incomplete antibody fit | Search Graus-style AE criteria, antibody-negative AE, exclusion rules, MRI/CSF/EEG patterns, and treatment response evidence. |
| Demyelinating disease differential | Optic neuritis, transverse myelitis, ADEM-like presentation, pediatric onset, MOG/AQP4/OCB data | Search pediatric MS vs MOGAD vs NMOSD criteria, MOG titer interpretation, CSF OCB specificity, lesion distribution. |
| CNS vasculitis vs RCVS/infection/malignancy | Multifocal deficits, headache, angiographic narrowing, CSF inflammation | Search PACNS vs RCVS discriminators, vessel-wall imaging, CSF patterns, biopsy indications, infection/malignancy mimics. |
| Sleep/prion/autonomic syndrome | Progressive insomnia, dysautonomia, ataxia, cognitive change, prion concern | Search sporadic fatal insomnia, CJD variants, PSG findings, thalamic PET/MRI, PRNP testing, exposure history. |
| Avoid premature functional diagnosis | Weakness, gait change, pain, bladder/bowel/sacral symptoms, inconsistent exam | Search tethered cord, spinal dysraphism, cauda equina/conus, autonomic/localizing signs, MRI indications. |
| Pathology/IHC edge case | Tumor morphology, unusual site, ambiguous markers | Search marker panels, tumor-specific differential tables, WHO classification, case series, and required stains. |
| Inflammatory/infectious mimic | Steroid response, fever, immune status, CSF abnormalities, mass-like lesions | Search infection/malignancy mimics before finalizing autoimmune or idiopathic inflammatory disease. |

## Model Configuration Target

Use `deepseek-v4-flash` as the default low-cost workhorse for:

- intake extraction;
- first differential;
- retrieval planning;
- query generation;
- evidence extraction;
- differential update;
- final answer.

Keep model routing config-driven. A stronger model may be used later for judge/skeptic roles, but the core research question is whether a guided retrieval workflow lets `deepseek-v4-flash` rescue cases it failed as a single-call model.

Example provider fields when model routing is implemented:

```json
{
  "provider": "deepseek",
  "base_url": "https://api.deepseek.com",
  "api_key_env": "DEEPSEEK_API_KEY",
  "model": "deepseek-v4-flash",
  "role": "reasoner",
  "max_tokens": 4096,
  "temperature": 0.2,
  "cost_per_million_input_tokens": null,
  "cost_per_million_output_tokens": null
}
```

## First Implementation Milestone

1. Add a NeurologyBM manifest adapter that can read the ready public JSONL into ClinicalHarness `ClinicalCase`-like objects without copying the source files.
2. Add a failure-set loader that joins the 30 IDs with Flash/Pro answers and scores: done for analysis-packet export.
3. Add a no-shortcut retrieval guard that blocks title, DOI, PMCID, article title, and exact prompt text from generated queries.
4. Add first prompt-scaffold commands for guarded query planning and evidence-note diagnostic updates: done.
5. Add a structured run mode for `guided_pubmed` with the controller stages above.
6. Run a neuro/psych subset of 5-10 cases with `deepseek-v4-flash`.
7. Report rescued cases and the retrieval step that made the difference.
