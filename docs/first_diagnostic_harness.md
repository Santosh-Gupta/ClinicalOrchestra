# First Diagnostic Harness

Last refreshed: 2026-06-11.

This is the first minimal ClinicalHarness loop for difficult diagnostic cases. It does not ask the model to solve the case immediately. It first asks for retrieval ideas: what knowledge would reduce uncertainty, what discriminators matter, and what PubMed/PMC/guideline/review queries should be run.

Update from 2026-06-13 live evaluation: a guided direct-answer benchmark path now exists for quick testing against the 53 public DeepSeek V4 Pro-failed cases. That path uses the learned preset checklists but does not yet run the retrieval loop below. On `deepseek-v4-flash`, it produced 20 lexical passes and 33 lexical fails, which is useful as a prompt-only baseline but not the final harness design.

Second update from 2026-06-13: a first retrieval-guided benchmark path now exists:

```bash
clinical-harness benchmark retrieval-guided-eval \
  --case-id native_PMC3122590 \
  --out-dir runs/retrieval_guided_probe \
  --model deepseek-v4-flash
```

This mode adds:

- preset-specific PubMed concept queries;
- case-feature query generation from markers, organisms, cytogenetics, drugs, organs, and morphology;
- optional multi-round retrieval with follow-up queries when evidence is sparse or a complex preset needs a second look;
- zero-result query broadening;
- source-title/DOI/PMCID exclusion of likely source articles;
- compact PubMed abstract snippets as evidence;
- optional model-subagent evidence distillation into discriminator tables;
- optional PMC full-text snippets for cases where abstracts are insufficient;
- finalization gates for known failure modes;
- resumable/progress-aware run artifacts mirroring `guided-eval`.

Third update from 2026-06-13: the stronger multiround/distilled/full-text controller was run on the 22 failures left after the first retrieval-guided 33-case rerun. It rescued 3 more cases and left 19 conservative lexical failures. Across the original 33 prompt-only failures, retrieval-guided ClinicalHarness has now rescued 14 cases total.

Useful command shape for the stronger controller:

```bash
clinical-harness benchmark retrieval-guided-eval \
  --manifest runs/retrieval_guided_33_prompt_failures_manifest_20260613.jsonl \
  --out-dir runs/retrieval_guided_multiround \
  --model deepseek-v4-flash \
  --max-rounds 2 \
  --max-queries 3 \
  --articles-per-query 3 \
  --distill-evidence \
  --use-full-text
```

Design principle: abstracts are the default because they often contain the high-yield diagnostic information and keep context small. Full text should be requested selectively when the distiller flags that the abstract lacks a needed marker table, diagnostic criteria detail, organism morphology, cytogenetic nuance, or management algorithm. Full-text snippets are still compacted before final-answer prompting.

Initial live probe results:

- `native_PMC3122590`, keratotic lesion: prompt-only failed as pseudoepitheliomatous keratotic and micaceous balanitis; retrieval plus finalization gate passed as penile cutaneous horn.
- Four-case mixed probe in `runs/retrieval_guided_mixed4_20260613`: 4 lexical passes after adding derived aliases for PCNSL / primary CNS lymphoma. Before alias expansion this was 3 lexical passes plus 1 semantic pass.

Next improvement should add a small judge scorer, because alias expansion will remain incomplete for harder semantic equivalence cases.

After the 33-case rerun, the next priority became clear: retrieval must be iterative. The first implementation now supports additional rounds, but the high-value future work is to make the distiller's `additional_queries` and `need_full_text_evidence_ids` decisions drive the second round in live runs.

After the 22-case multiround residual rerun, the next bottleneck is not just retrieval volume. The remaining failures usually have evidence available but need stronger final-answer discipline:

- convert broad pathology lineages into the exact subtype using marker, site, molecular, and morphology constraints;
- separate organism identification from clinical diagnosis, including colonization versus invasive infection;
- force uncommon neuroinflammatory or neuropsychiatric alternatives to beat familiar anchors on discriminating facts;
- add a judge scorer so semantic partials and near-equivalent diagnoses are measured separately from true failures.

## Core Loop

1. Start with the challenge prompt only.
2. Ask the model for query ideas, not a diagnosis.
3. Validate proposed queries against source-shortcut guards.
4. Retrieve PubMed/PMC/general biomedical sources with safe concept queries.
5. Have a separate reader summarize only the clinically useful diagnostic discriminators from retrieved sources.
6. Add those distilled evidence notes back to the case context.
7. Ask the model for a differential update, final answer, or another targeted retrieval round.
8. Score only after the run, using answer keys and source/outcome material that were not visible to the diagnostic agent.

## Implemented Harness Innovations

Current generated prompts include:

- source-shortcut guardrails;
- "ask for query ideas, not diagnosis";
- round budget and previous-query context;
- distilled evidence notes rather than whole papers;
- strict JSON response shapes for query planning, discriminator retrieval, and diagnostic update;
- selectable harness presets/checklists;
- discriminator-first retrieval;
- biomarker interpretation prompts;
- organic psychosis checklist;
- negative-test-does-not-exclude logic through preset instructions;
- pathology lineage verification prompts;
- organ-specific spindle-cell pathology subtype prompts;
- bone vascular tumor and secondary-ABC pathology prompts;
- gnathic bone tumor radiographic discriminator prompts;
- middle-ear mass vascular/neuroendocrine discriminator prompts;
- keratotic skin/genital lesion base-histology prompts;
- prior-cancer unusual-mass metastasis discriminator prompts;
- lipomatous tumor MDM2/molecular discriminator prompts;
- immunocompromised necrotizing infection blunted-sign prompts;
- maxillofacial osteomyelitis odontogenic-source/sequestrum prompts;
- granulomatous overlap TB/sarcoid negative-test prompts;
- CNS granulomatous mass tuberculoma/neurosarcoidosis prompts;
- gynecologic epithelioid tumor small-biopsy IHC prompts;
- sellar xanthogranuloma cystic-mass histology/follow-up prompts;
- temporal-bone inflammatory mass biopsy interpretation prompts;
- mold identification morphology/sequencing/susceptibility prompts;
- prenatal syndromic pattern and recurrence-counseling prompts;
- movement-disorder phenotype/MRPI discriminator prompts;
- ocular infection/inflammation prompts;
- neuroinflammatory demyelination mimic prompts;
- pediatric bone small-round-cell tumor prompts;
- postoperative retained foreign-body prompts;
- persistent hCG localization prompts;
- GI desmoplastic neuroendocrine tumor prompts;
- renal spindle-cell mass prompts;
- immunocompromised retinitis prompts;
- GI neuroendocrine carcinoma prompts;
- hematologic cytogenetic subtype prompts;
- optic pathway neoplasm prompts;
- submucosal gas cyst prompts;
- colonization-versus-infection prompts;
- drug causality timeline prompts;
- two-event bridge diagnosis prompts.
- recurrent/enlarging mass malignancy red-flag prompts.
- cardiac/pericardial mass prompts with cytology false-negative caveats.

Implemented presets:

- `general`
- `neuro_psych`
- `autoimmune_encephalitis`
- `pathology`
- `spindle_cell_pathology`
- `bone_vascular_tumor`
- `gnathic_bone_tumor`
- `middle_ear_mass`
- `keratotic_skin_lesion`
- `prior_cancer_mass`
- `lipomatous_tumor_molecular`
- `mass_malignancy`
- `cardiac_pericardial_mass`
- `adverse_drug_event`
- `infection_microbiology`
- `mold_identification`
- `immunocompromised_necrotizing_infection`
- `maxillofacial_osteomyelitis`
- `granulomatous_overlap`
- `cns_granulomatous_mass`
- `gynecologic_epithelioid_tumor`
- `sellar_xanthogranuloma`
- `temporal_bone_inflammatory_mass`
- `prenatal_syndromic_pattern`
- `movement_disorder_phenotype`
- `ocular_infection_inflammation`
- `neuroinflammatory_demyelination`
- `bone_small_round_cell_tumor`
- `postoperative_foreign_body`
- `persistent_hcg_localization`
- `gi_desmoplastic_neuroendocrine`
- `renal_spindle_cell_mass`
- `immunocompromised_retinitis`
- `gi_neuroendocrine_carcinoma`
- `hematologic_cytogenetic_subtype`
- `optic_pathway_neoplasm`
- `submucosal_gas_cyst`
- `colonization_vs_infection`
- `demyelination`
- `cns_vasculitis`
- `acute_neuro_emergency`
- `vascular_neuro`
- `seizure_mimic`
- `functional_neuro`
- `neuro_oncology`
- `cancer_neuro`
- `prion_sleep`
- `sequential_event`

## Source-Shortcut Guard

The diagnostic agent must not see or search:

- source title or article title;
- DOI;
- PMCID;
- PMID;
- exact quoted prompt text;
- long contiguous prompt phrases.

ClinicalHarness keeps real blocked values internal for validation. Model-facing prompt packets only say that those fields are blocked if known.

## Query Ideas Prompt

Generate a prompt packet:

```bash
clinical-harness case query-prompt examples/cases/synthetic_neuro_case.json \
  --round 1 \
  --max-rounds 3 \
  --preset neuro_psych \
  --out runs/harness_prompts/query_round_1.json
```

The packet contains a model-facing `prompt` asking for strict JSON:

- problem representation;
- uncertainty map;
- query ideas;
- expected evidence;
- stop/continue decision.

The prompt explicitly says not to diagnose yet.

## Query Validation

Validate model-proposed queries before retrieval:

```bash
clinical-harness case validate-queries examples/cases/synthetic_neuro_case.json \
  --query "subacute psychosis seizures autoimmune encephalitis criteria" \
  --query "seronegative autoimmune encephalitis CSF EEG MRI review"
```

The command returns nonzero if a query includes a blocked source identifier, source title, or long exact prompt overlap.

## Evidence Notes

After retrieval, other agents or tools should read the retrieved sources and produce distilled evidence notes. Keep notes short and clinical-discriminator focused. Do not paste whole papers.

JSONL format:

```json
{
  "evidence_id": "pubmed:12345",
  "source_type": "review",
  "citation": "Short citation or source label",
  "useful_facts": [
    "Clinically relevant fact."
  ],
  "diagnostic_discriminators": [
    "Finding that separates diagnosis A from diagnosis B."
  ],
  "discriminator_table": [
    {
      "discriminator": "Specific feature",
      "diagnosis_a": "Diagnosis A",
      "diagnosis_b": "Diagnosis B",
      "case_finding": "Finding in this case",
      "direction": "Favors A"
    }
  ],
  "required_tests_or_markers": [
    "IHC, flow, biomarker, imaging, or serology needed to separate diagnoses."
  ],
  "required_imaging_or_procedures": [
    "MRI/MRV/CTV/CTA/MRA/vessel-wall MRI or procedure needed to separate diagnoses."
  ],
  "required_eeg_or_physiology": [
    "Routine EEG, prolonged EEG, video EEG, sleep study, or other physiology test needed to separate episodic diagnoses."
  ],
  "temporal_semiology_table": [
    {
      "feature": "duration, stereotypy, frequency, awareness, trigger, lesion localization, postictal state, or treatment response",
      "case_finding": "Finding in this case",
      "supports": "Diagnosis supported by this feature",
      "argues_against": "Diagnosis argued against by this feature"
    }
  ],
  "functional_neuro_red_flags": [
    "Sacral, autonomic, reflex, objective sensory-level, or prior spine/pelvic trauma findings that block functional diagnosis closure."
  ],
  "malignancy_red_flags": [
    "Steroid-responsive mass, waxing/waning enhancement, persistent cranial nerve enhancement, leptomeningeal enhancement, or multifocal nerve involvement."
  ],
  "tissue_diagnosis_plan": [
    "Biopsy, CSF cytology/flow, repeat MRI timing, or steroid-withholding consideration before biopsy."
  ],
  "serial_imaging_change_table": [
    {
      "timepoint": "Relative timepoint",
      "finding": "Imaging change",
      "supports": "Diagnosis supported by this change",
      "argues_against": "Diagnosis argued against by this change"
    }
  ],
  "known_cancer_context": [
    "Active, recent, high-stage, or high-risk cancer context relevant to neurologic relapse."
  ],
  "csf_cytology_plan": [
    "Repeat CSF cytology, adequate CSF volume, rapid processing, CSF flow, or cell block when relevant."
  ],
  "negative_test_caveats": [
    "False-negative limits of first MRI, first CSF cytology, normal opening pressure, tumor markers, or PET-CT."
  ],
  "antibody_specificity_table": [
    {
      "antibody_or_panel": "Antibody or panel name",
      "case_result": "Positive, negative, pending, or not tested",
      "supports_subtype": "Named AE subtype supported by this result",
      "argues_against_subtype": "Named AE subtype argued against by this result",
      "test_limitation": "Serum/CSF/panel limitation"
    }
  ],
  "seronegative_ae_criteria": [
    "Probable/seronegative autoimmune encephalitis criteria met by the case."
  ],
  "immunotherapy_escalation_plan": [
    "First-line and second-line immunotherapy, refractory seizure/status epilepticus escalation, and tumor screening."
  ],
  "emergency_neuro_differential": [
    {
      "diagnosis": "Arterial ischemia, CVST, hemorrhage, seizure/status, toxic-metabolic, infection, or inflammatory cause",
      "must_not_miss": true,
      "case_clues": [
        "Emergency clue"
      ],
      "next_test": "Immediate next diagnostic test"
    }
  ],
  "emergency_next_tests": [
    "MRV/CTV, CTA/MRA, EEG, LP, or toxic-metabolic labs."
  ],
  "empty_output_rescue_rule": "Minimum emergency differential and next test required when the model cannot decide.",
  "microbiology_test_plan": [
    "Aerobic, anaerobic, fungal, AFB, TB PCR/culture, Brucella serology/culture, or histopathology strategy."
  ],
  "pathogen_discriminator_table": [
    {
      "pathogen": "Candidate organism",
      "supporting_clues": [
        "Case clues supporting organism"
      ],
      "arguing_against_clues": [
        "Case clues arguing against organism"
      ],
      "required_tests": [
        "Microbiology or pathology needed"
      ],
      "treatment_implication": "Antimicrobial and procedural consequence"
    }
  ],
  "antimicrobial_duration_plan": [
    "Pathogen-specific regimen, duration, surgical drainage/decompression indication, and culture-directed therapy."
  ],
  "prion_phenotype_table": [
    {
      "feature": "Insomnia, dysautonomia, ataxia, myoclonus, MRI DWI/ADC, CSF 14-3-3, RT-QuIC, EEG, or PRNP",
      "case_finding": "Finding in this case",
      "supports": "Prion subtype supported by this feature",
      "argues_against": "Prion subtype argued against by this feature"
    }
  ],
  "exposure_plausibility_table": [
    {
      "exposure": "Candidate exposure",
      "route": "Exposure route",
      "incubation": "Timing plausibility",
      "phenotype_match": "Whether the syndrome matches expected phenotype",
      "supports_or_refutes": "Direction"
    }
  ],
  "drug_causality_table": [
    {
      "candidate_drug": "Drug name",
      "timing": "Relative timing",
      "dechallenge": "Improved/not improved/unknown",
      "rechallenge_or_prophylaxis": "Evidence if present",
      "direction": "Favors or argues against causality"
    }
  ],
  "management_escalation_rules": [
    "When to escalate or preserve essential therapy."
  ],
  "mechanistic_link": "How two temporally separated events could be connected.",
  "caveats": [
    "Limit or uncertainty in this evidence."
  ],
  "source_exclusion_checked": true
}
```

## Diagnostic Update Prompt

Build a prompt that includes the original challenge, previous queries, round budget, and distilled evidence notes:

```bash
clinical-harness case answer-prompt examples/cases/synthetic_neuro_case.json \
  --notes runs/evidence_notes/synthetic_round_1.jsonl \
  --round 2 \
  --max-rounds 3 \
  --preset neuro_psych \
  --previous-query "subacute psychosis seizures autoimmune encephalitis criteria" \
  --out runs/harness_prompts/answer_round_2.json
```

The prompt asks for strict JSON:

- differential update;
- missing discriminators;
- next retrieval queries;
- final answer when evidence is sufficient;
- stop/continue decision.

## Discriminator Prompt

After an initial differential exists, force discriminator-focused retrieval before final diagnosis:

```bash
clinical-harness case discriminator-prompt examples/cases/synthetic_neuro_case.json \
  --differential runs/differentials/synthetic_round_1.json \
  --round 2 \
  --max-rounds 3 \
  --preset demyelination \
  --previous-query "optic neuritis demyelinating disease criteria" \
  --out runs/harness_prompts/discriminator_round_2.json
```

The prompt asks for strict JSON:

- top mimic pairs;
- needed discriminators;
- biomarker interpretation queries;
- pathology lineage queries;
- vascular imaging queries;
- seizure mimic queries;
- functional neuro queries;
- neuro-oncology queries;
- known-cancer neurologic syndrome queries;
- autoimmune encephalitis specificity queries;
- acute neurologic emergency queries;
- infection microbiology queries;
- immunocompromised necrotizing infection queries;
- maxillofacial osteomyelitis queries;
- granulomatous overlap queries;
- spindle-cell pathology queries;
- bone vascular tumor queries;
- gnathic bone tumor queries;
- middle-ear mass queries;
- keratotic skin lesion queries;
- prior-cancer mass queries;
- lipomatous tumor molecular queries;
- mass malignancy queries;
- cardiac/pericardial mass queries;
- prion/sleep phenotype queries;
- drug causality queries;
- two-event bridge queries;
- management escalation queries.

## Near-Term Next Step

Run the guided direct-answer harness against failed cases:

```bash
clinical-harness benchmark guided-eval \
  --dry-run \
  --limit 3 \
  --out-dir runs/guided_eval_dryrun_sample

DEEPSEEK_API_KEY=... clinical-harness benchmark guided-eval \
  --model deepseek-v4-flash \
  --out-dir runs/guided_eval_deepseek_v4_flash
```

`guided-eval` loads the public Pro-failed manifest, selects the learned preset for each case, writes one model-facing prompt per case, optionally calls an OpenAI-compatible model API, and writes `guided_results.jsonl` plus `guided_results.tsv`.

The remaining gap is the full retrieval controller: model-generated safe queries, PubMed/PMC retrieval, reader-agent evidence notes, iterative discriminator rounds, and final answer scoring. Keep answer keys and original source material evaluator-only until scoring.
