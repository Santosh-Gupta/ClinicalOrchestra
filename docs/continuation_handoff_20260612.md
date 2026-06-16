# Continuation Handoff

Last updated: 2026-06-12.

This file is the fastest way for a new model/agent to resume work on ClinicalHarness.

## Current Project State

ClinicalHarness is a Python standard-library research harness for hard diagnostic case challenges. It is not clinical decision support. The immediate research goal is to make `deepseek-v4-flash` solve cases it failed as a single direct-call model by using a guarded, multi-step retrieval workflow.

The repo was renamed from `ClinicalOrchestra` to `ClinicalHarness`.

- Current checkout path: `/Users/santoshg/Coding/ClinicalHarness`
- Current Python package: `clinical_harness`
- Current primary CLI: `clinical-harness`
- Backward-compatible console script alias: `clinical-orchestra`

The sibling repo `/Users/santoshg/Coding/NeurologyBM` owns dataset creation, licensing, splits, answer keys, and benchmark exports. Do not edit NeurologyBM from this repo unless explicitly asked. ClinicalHarness should consume NeurologyBM exports as external inputs.

## Verification Command

Run this before and after changes:

```bash
cd /Users/santoshg/Coding/ClinicalHarness
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Current expected result: 48 passing tests.

The repo has no runtime dependencies outside the Python standard library.

## Implemented Code

### Retrieval

- `src/clinical_harness/ncbi.py`
  - Rate-limited NCBI E-Utilities client.
  - Supports API key, email/tool metadata, retries, gzip, optional `--insecure` for local broken cert stores.
- `src/clinical_harness/pubmed.py`
  - PubMed `ESearch`.
  - PubMed `EFetch` XML parsing.
  - Extracts PMID, PMCID, DOI, title, abstract, journal, publication year, publication types, URL.
- `src/clinical_harness/pmc.py`
  - PMC `ESearch`.
  - PMC `EFetch` full-text JATS XML parsing.
  - Extracts PMCID, PMID, DOI, title, abstract, journal, publication year, license marker, URL, body sections.

### Case/run primitives

- `src/clinical_harness/schemas.py`
  - Serializable dataclasses: `ClinicalCase`, `ProblemRepresentation`, `SearchQuery`, `EvidenceRecord`, `CandidateDiagnosis`, `StructuredAnswer`, `RunManifest`, `ModelCallRecord`.
  - `EvidenceRecord` includes `pmid`, `pmcid`, `doi`, source-exclusion flags, and provenance fields.
- `src/clinical_harness/cases.py`
  - JSON case loader.
- `src/clinical_harness/ledger.py`
  - Run directory writer for manifest, events, queries, evidence, answer.
- `src/clinical_harness/case_runner.py`
  - Deterministic first-slice `case run`.
  - Generates template PubMed queries.
  - Optionally retrieves PubMed abstracts.
  - Writes placeholder structured answer.
  - Source-exclusion checks currently match PMID, PMCID, DOI, and title.

### DeepSeek benchmark prep

- `src/clinical_harness/deepseek_failures.py`
  - Loads NeurologyBM ready manifest and DeepSeek Flash/Pro results/scores.
  - Exports per-case analysis packets for the 30 public cases failed by both Flash and Pro.
  - Keeps `diagnostic_agent_input` separate from `evaluator_only`.

### First diagnostic harness prompt scaffold

- `src/clinical_harness/diagnostic_harness.py`
  - Builds guarded query-idea prompts.
  - Builds discriminator-focused retrieval prompts.
  - Builds diagnostic update prompts from distilled evidence notes.
  - Validates proposed retrieval queries against source-title/DOI/PMCID/PMID/exact-prompt shortcuts.
  - Redacts real blocked identifiers from model-facing prompts.
  - Implements harness presets: `general`, `neuro_psych`, `autoimmune_encephalitis`, `pathology`, `spindle_cell_pathology`, `bone_vascular_tumor`, `gnathic_bone_tumor`, `middle_ear_mass`, `keratotic_skin_lesion`, `prior_cancer_mass`, `lipomatous_tumor_molecular`, `mass_malignancy`, `cardiac_pericardial_mass`, `adverse_drug_event`, `infection_microbiology`, `mold_identification`, `immunocompromised_necrotizing_infection`, `maxillofacial_osteomyelitis`, `granulomatous_overlap`, `cns_granulomatous_mass`, `gynecologic_epithelioid_tumor`, `sellar_xanthogranuloma`, `temporal_bone_inflammatory_mass`, `prenatal_syndromic_pattern`, `movement_disorder_phenotype`, `ocular_infection_inflammation`, `neuroinflammatory_demyelination`, `bone_small_round_cell_tumor`, `postoperative_foreign_body`, `persistent_hcg_localization`, `gi_desmoplastic_neuroendocrine`, `renal_spindle_cell_mass`, `immunocompromised_retinitis`, `gi_neuroendocrine_carcinoma`, `hematologic_cytogenetic_subtype`, `optic_pathway_neoplasm`, `submucosal_gas_cyst`, `colonization_vs_infection`, `demyelination`, `cns_vasculitis`, `acute_neuro_emergency`, `vascular_neuro`, `seizure_mimic`, `functional_neuro`, `neuro_oncology`, `cancer_neuro`, `prion_sleep`, `sequential_event`.

## Implemented CLI

```bash
clinical-harness pubmed search "query" --limit 10 --format text|json
clinical-harness pmc search "query" --limit 3 --format text|json
clinical-harness pmc fetch PMC3122590 --format text|json
clinical-harness case run examples/cases/synthetic_neuro_case.json --mode pubmed_only --no-retrieve
clinical-harness case query-prompt examples/cases/synthetic_neuro_case.json --round 1 --max-rounds 3 --out query.json
clinical-harness case validate-queries examples/cases/synthetic_neuro_case.json --query "safe concept query"
clinical-harness case discriminator-prompt examples/cases/synthetic_neuro_case.json --differential differential.json --round 2 --preset demyelination --out discriminator.json
clinical-harness case answer-prompt examples/cases/synthetic_neuro_case.json --notes notes.jsonl --round 2 --max-rounds 3 --out answer.json
clinical-harness benchmark deepseek-packets --subset neuro_psych --out runs/deepseek_failure_packets/neuro_psych.jsonl
clinical-harness benchmark deepseek-packets --subset all --out runs/deepseek_failure_packets/all_30.jsonl
```

If live NCBI calls fail locally with certificate errors, use `--insecure` only as a local workaround. Do not use it in production runs.

## Key Data Inputs From NeurologyBM

Public benchmark files used by ClinicalHarness:

```text
/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/ready_llm_eval_manifest_20260611.jsonl
/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/ready_38_flash_fail_pro_still_fail_case_ids_20260612.txt
/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/ready_38_flash_fail_pro_rescue_comparison_20260612.tsv
/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/deepseek_runs/deepseek_public_20260612T000541Z/results.tsv
/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/deepseek_runs/deepseek_public_scores_20260612T001940Z/scores.tsv
/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/deepseek_runs/deepseek_public_20260611T224853Z/results.tsv
/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/deepseek_runs/deepseek_public_scores_20260611T230530Z/scores.tsv
```

Private files under `/Users/santoshg/Coding/NeurologyBM/docs/DO NOT COMMIT TO GITHUB` are not first-pass inputs and must not be copied into public artifacts.

## Critical Safety/Benchmark Rules

- Do not retrieve by source title, article title, DOI, PMCID, PMID, or exact quoted prompt.
- Do not expose answer keys, source article title, DOI, PMCID, outcome, or original paper discussion to the diagnostic agent before scoring.
- Model-facing prompts should only contain the challenge prompt, previous safe queries, round budget, and distilled evidence notes.
- Source identifiers may be used internally by guards/scorers to block leakage.
- Store structured artifacts, not hidden chain-of-thought.
- Retrieval logs and benchmark traces are evaluation artifacts, not training data.

## Evidence Note Format

The first harness loop expects distilled evidence notes as JSONL:

```json
{
  "evidence_id": "pubmed:12345",
  "source_type": "review",
  "citation": "Short citation or source label",
  "useful_facts": ["Clinically relevant fact."],
  "diagnostic_discriminators": ["Finding that separates diagnosis A from diagnosis B."],
  "caveats": ["Limit or uncertainty in this evidence."],
  "source_exclusion_checked": true
}
```

Implemented optional fields:

- `discriminator_table`
- `required_tests_or_markers`
- `required_imaging_or_procedures`
- `required_eeg_or_physiology`
- `temporal_semiology_table`
- `functional_neuro_red_flags`
- `malignancy_red_flags`
- `tissue_diagnosis_plan`
- `serial_imaging_change_table`
- `known_cancer_context`
- `csf_cytology_plan`
- `negative_test_caveats`
- `antibody_specificity_table`
- `seronegative_ae_criteria`
- `immunotherapy_escalation_plan`
- `emergency_neuro_differential`
- `emergency_next_tests`
- `empty_output_rescue_rule`
- `microbiology_test_plan`
- `pathogen_discriminator_table`
- `antimicrobial_duration_plan`
- `prion_phenotype_table`
- `exposure_plausibility_table`
- `drug_causality_table`
- `management_escalation_rules`
- `mechanistic_link`

## DeepSeek Pro Failure Lessons Already Documented

See `docs/deepseek_pro_failure_case_studies.md`.

Progress through the 30 Pro-still-failed public cases is tracked in `docs/deepseek_failure_review_tracker.md`.

Current implemented lessons include biomarker interpretation, organic psychosis, autoimmune encephalitis antibody-specificity handling, CNS vasculitis false-negative handling, acute neurologic emergency empty-output rescue, pathology lineage verification, infection microbiology specificity, adverse-drug timeline causality, two-event bridge diagnosis, vascular-neuro imaging gates, seizure-mimic semiology/EEG gates, functional-neuro structural red-flag stop rules, neuro-oncology steroid-responsive mass gates, known-cancer neurologic syndrome gates, and prion/sleep phenotype gates.

Analyzed failures:

1. Pediatric MS miscalled as MOGAD.
   - Feature to add: biomarker interpretation and demyelination discriminator retrieval.
2. NPSLE psychosis miscalled as anti-NMDA encephalitis.
   - Feature to add: organic psychosis mimic checklist.
3. PACNS miscalled as RCVS.
   - Feature to add: mimic-pair discriminator table and negative-test-does-not-exclude rule.
4. Myeloid sarcoma miscalled as large cell lymphoma.
   - Feature to add: pathology lineage verification with IHC/flow/cytogenetics and marrow-workup requirements.
5. Arsenic trioxide-induced erythema multiforme miscalled as ATRA-induced EM.
   - Feature to add: drug causality timeline, dechallenge/rechallenge, Naranjo-style causality, and essential-therapy-preserving management.
6. CVST miscalled as MELAS.
   - Feature added: vascular-neuro imaging gate with MRV/CTV-style discriminator retrieval before metabolic workup.

## Highest-Value Next Implementation

The next model should implement **prompt-output validation and model routing** before live benchmark runs.

Recommended next slice:

1. Add JSON validators for model outputs from:
   - `query-prompt`
   - `discriminator-prompt`
   - `answer-prompt`
2. Add validation tests ensuring:
   - answer key never appears in query prompt;
   - DOI/PMCID/title are redacted from prompts but blocked in query validation;
   - preset prompt contains the correct required checklist;
   - unsafe exact-title/PMCID/DOI queries fail validation.
3. Add model-provider config and a dry-run/mock model interface.
4. Then wire DeepSeek API calls.

## What Not To Do Next

- Do not start with a fully autonomous agent.
- Do not feed whole retrieved papers into the diagnosis model.
- Do not expose evaluator-only answer/source material to the diagnostic run.
- Do not scrape locked/proprietary challenge sources.
- Do not hard-code DeepSeek as the only possible provider; keep model routing configurable.

## Known Limitations

- `case run` currently uses PubMed only; PMC exists as CLI infrastructure but is not wired into the runner.
- Structured answer generation is still a placeholder.
- A minimal OpenAI-compatible model client exists in `src/clinical_harness/model_client.py`.
- `clinical-harness benchmark guided-eval` can run guided direct-answer prompts on the 53 public Pro-failed manifest when `DEEPSEEK_API_KEY` or `OPENAI_API_KEY` is configured.
- The full retrieval controller is still missing: model-generated queries, safe retrieval, reader-agent evidence notes, iterative rounds, and final scoring in one run.
- No scoring implementation exists yet beyond loading NeurologyBM score exports.
- No batch runner exists yet.
- No evidence ranker or citation support checker exists yet.

## Useful Smoke Commands

Generate first query prompt:

```bash
clinical-harness case query-prompt examples/cases/synthetic_neuro_case.json \
  --round 1 --max-rounds 3 --out /tmp/query.json
```

Validate safe query:

```bash
clinical-harness case validate-queries examples/cases/synthetic_neuro_case.json \
  --query "subacute psychosis seizures autoimmune encephalitis criteria"
```

Export all 30 failed-case analysis packets:

```bash
clinical-harness benchmark deepseek-packets \
  --subset all \
  --out /tmp/clinical-harness-30-packets.jsonl
```

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
