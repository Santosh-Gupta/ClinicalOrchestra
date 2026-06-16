# Roadmap

ClinicalHarness should grow in layers. Each layer should be useful and testable before the next is added.

## Phase 0: PubMed Search Foundation

Status: implemented for the first working slice.

- PubMed search CLI.
- Abstract retrieval via EFetch.
- PMC search/fetch CLI.
- PMC JATS section parsing.
- Structured JSON output.
- Unit tests for PubMed and PMC XML parsing.
- Deterministic single-case runner can write run artifacts and optional PubMed evidence.
- DeepSeek failure packet export is implemented for the 30 public Pro-still-failed cases.
- First guarded prompt scaffold is implemented for query planning, query validation, and evidence-note diagnostic updates.

Next improvements:

- add PMID fetch by id
- add query templates for neurology syndromes
- improve query generation from problem representations
- add structured discriminator-prompt command: done
- add harness presets for neuro/psych, autoimmune encephalitis, pathology, spindle-cell pathology, bone vascular tumor, gnathic bone tumor, middle-ear mass, keratotic skin lesion, prior-cancer mass, lipomatous tumor molecular, mass malignancy, cardiac/pericardial mass, adverse drug event, infection microbiology, immunocompromised necrotizing infection, maxillofacial osteomyelitis, granulomatous overlap, demyelination, CNS vasculitis, acute neuro emergency, vascular neuro, seizure-mimic, functional-neuro, neuro-oncology, cancer-neuro, prion-sleep, and sequential-event cases: done

## Phase 1: Case Attempt Runner

Goal: run a single benchmark case through a reproducible workflow.

Tasks:

- define `ClinicalCase` schema: done
- define serializable run, evidence, answer, and model-call schemas: done
- load cases from JSON: done
- create problem representation manually or via LLM: deterministic template started
- generate PubMed queries: deterministic template started
- collect evidence: PubMed abstracts supported
- collect full text: PMC CLI supported, not yet wired into the case runner
- produce a final structured answer: placeholder answer supported
- write a run trace: done
- support source-excluded retrieval when source identifiers are known: PMID, DOI, and title controls started
- source-excluded retrieval also checks PMCID: done
- query prompt generation redacts source identifiers while keeping internal validation: done
- evidence-note answer prompt supports distilled source summaries: done
- keep tests runnable without external LLM calls: done

## Phase 1A: First Diagnostic Harness

Goal: make the guided retrieval loop explicit before live model calls.

Status: started.

Implemented:

- `case query-prompt` asks for retrieval ideas, not final diagnosis.
- `case validate-queries` blocks source-title/DOI/PMCID/PMID/exact-prompt shortcuts.
- `case answer-prompt` feeds distilled evidence notes, prior queries, and round budget back to the model.
- Model-facing prompt packets redact real blocked identifiers.

Next tasks:

- extend evidence notes with `discriminator_table`, `required_tests_or_markers`, `drug_causality_table`, and `management_escalation_rules`: done
- add `mechanistic_link` evidence field for two-event bridge diagnoses: done
- add `case discriminator-prompt`: done
- add harness presets: done
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
- prevent final answer when no top-mimic discriminator evidence has been retrieved
- prevent final answer when named autoimmune encephalitis subtypes lack antibody/specificity evidence
- prevent final answer when spindle-cell tumors lack organ-specific subtype marker evidence
- prevent final answer when ABC-like aggressive bone lesions lack secondary-ABC and endothelial-marker evidence
- prevent final answer when jaw bone tumors lack gnathic radiographic and matrix discriminator evidence
- prevent final answer when middle-ear masses lack vascular/cholesteatoma/neuroendocrine discriminator evidence
- prevent final answer when keratotic skin/genital lesions lack base-histology malignancy exclusion
- prevent final answer when prior-cancer unusual masses lack metastatic recurrence and IHC comparison evidence
- prevent final answer when lipomatous tumors lack MDM2/CDK4 molecular interpretation and benign morphology integration
- prevent final answer when recurrent/enlarging painful masses lack malignancy red-flag and tissue-diagnosis evidence
- prevent final answer when cardiac/pericardial masses lack cytology-caveat and tissue-diagnosis evidence
- prevent final answer when immunocompromised soft-tissue necrosis lacks blunted-sign and urgent source-control evidence
- prevent final answer when infection cases lack pathogen-specific microbiology/pathology evidence
- prevent final answer when mold-identification cases lack organism-level morphology/sequencing and susceptibility evidence
- prevent final answer when maxillofacial infection lacks odontogenic-source and sequestrum-imaging evidence
- prevent final answer when granulomatous overlap lacks TB negative-test caveats and treatment decision evidence
- prevent final answer when CNS granulomatous masses lack tuberculoma/neurosarcoidosis table and anti-TB continuation caveats
- prevent final answer when gynecologic epithelioid tumors lack small-biopsy caveats and smooth-muscle/PEComa/UTROSCT IHC panel evidence
- prevent final answer when sellar cystic-solid masses lack xanthogranuloma/Rathke/craniopharyngioma discriminator and histology/follow-up evidence
- prevent final answer when temporal-bone destructive masses lack biopsy interpretation and inflammatory-malignancy mimic evidence
- prevent final answer when prenatal syndromic cases lack fetal anomaly pattern table and recurrence/genetic counseling evidence
- prevent final answer when movement-disorder cases lack phenotype subtype table and MRPI/MRPI 2.0 or specialist-plan evidence
- prevent final answer when ocular infection/inflammation cases lack infectious mimic and immunosuppression/escalation evidence
- prevent final answer when neuroinflammatory demyelination cases lack MOG/AQP4 and infection-exclusion evidence
- prevent final answer when pediatric bone tumors lack Ewing/osteosarcoma IHC/molecular discriminators
- prevent final answer when postoperative abdominal masses lack retained-foreign-body/source-control evidence
- prevent final answer when persistent hCG cases lack localization strategy after negative pelvic imaging
- prevent final answer when GI/renal/optic pathway tumor cases lack site-specific pathology and management discriminators
- prevent final answer when submucosal colonic lesions lack gas-cyst aspiration/CT evidence
- prevent final answer when culture-positive ICU/NICU cases lack colonization-vs-infection evidence
- prevent empty answers in acute neurologic emergencies
- prevent final answer when seizure-mimic cases lack semiology/EEG evidence
- prevent final answer when functional-neuro cases lack structural red-flag evidence
- prevent final answer when neuro-oncology cases lack malignancy/tissue-plan evidence
- prevent final answer when cancer-neuro cases lack repeat-CSF/negative-test caveat evidence
- prevent final answer when prion-sleep cases lack phenotype/exposure-plausibility evidence
- only then wire DeepSeek model calls

## Phase 2: Evidence Filtering

Goal: reduce noisy retrieval.

Tasks:

- rank PubMed results by case relevance
- detect original-source leakage
- extract candidate diagnoses from abstracts
- cluster duplicate diagnoses and aliases
- add citation-backed evidence summaries

## Phase 3: LLM Orchestration

Goal: compare orchestration strategies.

Strategies:

- provider-agnostic model routing for cheap APIs, mid models, and strong adjudicators
- single model with retrieval
- query generator + evidence extractor + diagnosis synthesizer
- multi-agent differential diagnosis
- specialist agents by neurology subspecialty
- counterfactual evidence checking

## Phase 4: Benchmark Harness

Goal: evaluate many cases reproducibly.

Tasks:

- batch case runner
- closed-book vs PubMed-only vs web-enabled modes
- answer alias matching
- LLM-as-judge with audit samples
- cost/latency reporting
- leaderboard tables

## Phase 5: Integration With NeurologyBM

Goal: use NeurologyBM as a benchmark source and ClinicalHarness as an attempt engine.

Tasks:

- import NeurologyBM case schema
- preserve train/eval split boundaries
- support source-excluded retrieval
- evaluate retrieval benefit by case difficulty
- preserve NeurologyBM license tier and source-family metadata in every run manifest

## Agent Handoff

The startup prompt for the Diagnosis Agent owner is in [Diagnosis Agent Handoff Prompt](diagnosis_agent_handoff_prompt.md). The repo boundary with NeurologyBM is in [Project Split](project_split.md).

## Non-Goals For Now

- clinical deployment
- patient-specific advice
- autonomous treatment recommendation
- training on retrieval logs
- scraping proprietary challenge sites into git
