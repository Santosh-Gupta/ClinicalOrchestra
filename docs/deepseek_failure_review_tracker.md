# DeepSeek Failure Review Tracker

Last refreshed: 2026-06-12.

This tracker covers the 30 public ready case challenges that both DeepSeek v4 Flash and DeepSeek v4 Pro failed. The source list is read from NeurologyBM's public benchmark export:

```text
/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/ready_38_flash_fail_pro_still_fail_case_ids_20260612.txt
```

## Boundary Rules

- Keep this file in ClinicalHarness because it describes harness design lessons, not a redistributed benchmark dataset.
- Use only public benchmark identifiers and short, paraphrased summaries in this repo.
- Do not copy full case articles, long article passages, private prompts, NEJM/JAMA-derived material, or files from `docs/DO NOT COMMIT TO GITHUB`.
- Answer keys and source metadata may be used for evaluator-only failure analysis, but must not be included in model-facing diagnostic prompts.
- Preserve source license metadata in run artifacts. PMC availability is not the same thing as unrestricted training permission.
- Retrieval logs are evaluation artifacts, not training data, unless a separate license review approves training use.

## Reviewed Cases

| Case ID | Harness lesson implemented | Main artifact |
| --- | --- | --- |
| `transformed_PMC10399123` | Demyelination and biomarker interpretation gate for pediatric MS vs MOGAD. | `demyelination` preset |
| `transformed_PMC12581184` | Organic psychosis checklist for NPSLE/autoimmune/infectious/toxic/metabolic mimics. | `neuro_psych` preset |
| `transformed_PMC10409533` | Steroid-responsive cranial-nerve/IAC mass gate for lymphoma/neoplastic mimics. | `neuro_oncology` preset |
| `transformed_PMC3214133` | Prion phenotype and exposure-plausibility gate for sFI vs iatrogenic CJD. | `prion_sleep` preset |
| `transformed_PMC5516732` | CNS vasculitis vs RCVS discriminator retrieval and negative-test-does-not-exclude handling. | `cns_vasculitis` preset |
| `transformed_PMC3824813` | Pathology lineage verification for preliminary FNA/cytology/pathology labels. | `pathology` preset |
| `transformed_PMC4825443` | Medication timeline, dechallenge/rechallenge, prophylaxis, and causality scoring. | `adverse_drug_event` preset |
| `transformed_PMC8046463` | Infection microbiology specificity gate for actinomycosis vs brucellar/TB/fungal/pyogenic mimics. | `infection_microbiology` preset |
| `transformed_PMC6499098` | Bridge diagnosis retrieval for temporally separated events. | `sequential_event` preset |
| `transformed_PMC10540759` | Vascular imaging gate before metabolic/inflammatory closure in headache/seizure/focal deficit cases. | `vascular_neuro` preset |
| `transformed_PMC6057707` | Acute neurologic emergency fallback for empty output, coma, headache, infarct, and normal arterial MRA. | `acute_neuro_emergency` preset |
| `transformed_PMC6179031` | Seizure semiology and EEG/prolonged EEG gate before release-hallucination or psychiatric closure. | `seizure_mimic` preset |
| `transformed_PMC8115684` | Known-cancer neurologic syndrome gate with repeat-CSF false-negative logic. | `cancer_neuro` preset |
| `transformed_PMC8143662` | Functional diagnosis stop rule when sacral/autonomic/localizing red flags exist. | `functional_neuro` preset |
| `transformed_PMC7678886` | Autoimmune encephalitis specificity gate for seronegative AE vs named antibody subtype. | `autoimmune_encephalitis` preset |
| `transformed_PMC7507877` | Recurrent/enlarging painful mass gate requiring malignancy red flags, tissue diagnosis, staging, and benign-vs-malignant pathology criteria before benign closure. | `mass_malignancy` preset |
| `transformed_PMC8244580` | Cardiac/pericardial mass gate for recurrent hemorrhagic effusion, negative cytology caveats, vascular tumor discriminators, and surgical tissue diagnosis. | `cardiac_pericardial_mass` preset |
| `transformed_PMC6741398` | Organ-specific spindle-cell pathology gate preventing generic UPS/high-grade sarcoma closure before subtype IHC/molecular discriminator retrieval. | `spindle_cell_pathology` preset |
| `transformed_PMC2413251` | Bone vascular tumor gate for secondary ABC patterns, aggressive recurrence, and endothelial-marker IHC before osteosarcoma/benign ABC closure. | `bone_vascular_tumor` preset |
| `transformed_PMC6761061` | Gnathic bone tumor gate for widened PDL/loss-of-lamina-dura clues and osteoid/matrix assessment before lymphoma/infection closure. | `gnathic_bone_tumor` preset |
| `transformed_PMC6286763` | Middle-ear mass gate using vascular symptoms, bone erosion/retraction-pocket clues, and neuroendocrine IHC before glomus/cholesteatoma closure. | `middle_ear_mass` preset |
| `native_PMC3122590` | Keratotic skin/genital lesion gate requiring morphology-first cutaneous-horn discrimination and base histology malignancy exclusion. | `keratotic_skin_lesion` preset |
| `transformed_PMC10798650` | Prior-cancer unusual-mass gate requiring metastatic recurrence/IHC comparison before syndrome-associated new-primary closure. | `prior_cancer_mass` preset |
| `transformed_PMC10901880` | Lipomatous tumor molecular gate requiring MDM2 FISH interpretation and benign morphology integration before ALT/WDL closure. | `lipomatous_tumor_molecular` preset |
| `transformed_PMC4084793` | Immunocompromised necrotizing infection gate requiring blunted-sign caveats and urgent source-control logic before fungal-only closure. | `immunocompromised_necrotizing_infection` preset |
| `transformed_PMC4291137` | Maxillofacial osteomyelitis gate requiring odontogenic-source caveats and sequestrum imaging before periapical abscess closure. | `maxillofacial_osteomyelitis` preset |
| `transformed_PMC5440415` | Granulomatous overlap gate requiring TB negative-test caveats and anti-TB/steroid decision logic before sarcoidosis-only closure. | `granulomatous_overlap` preset |
| `transformed_PMC10025825` | Gynecologic epithelioid tumor gate requiring small-biopsy caveats, empty-output rescue, and smooth-muscle/PEComa/UTROSCT IHC panel. | `gynecologic_epithelioid_tumor` preset |
| `transformed_PMC10556246` | Sellar cystic-solid mass gate requiring xanthogranuloma/Rathke/craniopharyngioma discriminators, histology plan, and endocrine follow-up. | `sellar_xanthogranuloma` preset |
| `transformed_PMC10765173` | Temporal-bone inflammatory mass gate requiring SCC/inflammatory osteomyelitis differential, biopsy interpretation, and normal-marker caveats. | `temporal_bone_inflammatory_mass` preset |

Detailed writeups are in [DeepSeek Pro Failure Case Studies](deepseek_pro_failure_case_studies.md).

## Remaining Cases

0 of 30 remain for review.

```text
All 30 public Pro-still-failed cases have an initial harness lesson recorded.
```

## Suggested Next Reviews

- Convert the 30 case-specific presets into runner-level preset selection heuristics.
- Add final-answer validators for required discriminator artifacts per preset.
- Run guided Flash on a 5-10 case subset, then expand to the full 30.

## Next100 Handoff Set

The NeurologyBM agent produced a second public handoff set on 2026-06-13:

```text
/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/next100_final_fail_for_harness_manifest_20260613.jsonl
```

It contains 23 cases failed by both Flash and Pro. Use the same boundary rules as above: short paraphrases only in this repo, no article text, no source metadata in model-facing diagnostic prompts, and answer/source material evaluator-only.

## Next100 Reviewed Cases

| Case ID | Harness lesson implemented | Main artifact |
| --- | --- | --- |
| `next_native_PMC12710301` | Mold identification gate requiring organism-level mycology morphology, sequencing, susceptibility, and CNS/leptomeningeal treatment implications before naming a fungal genus/species. | `mold_identification` preset |
| `next_native_PMC7944237` | Prenatal syndromic pattern gate requiring fetal anomaly table, incomplete Fryns-spectrum comparison, and recurrence/genetic counseling before Meckel-Gruber/ciliopathy closure. | `prenatal_syndromic_pattern` preset |
| `next_transformed_PMC7078665` | Movement-disorder phenotype gate requiring PSP-P vs PSP-RS/PD/MSA/CBD/DLB discriminators and MRPI 2.0/specialist plan before PSP subtype closure. | `movement_disorder_phenotype` preset |
| `next_transformed_PMC7930965` | CNS granulomatous mass gate requiring tuberculoma vs neurosarcoidosis discriminators and anti-TB continuation caveats before stopping TB therapy. | `cns_granulomatous_mass` preset |
| `next_transformed_PMC9979078` | Ocular infection/inflammation gate requiring TB-endemic exposure, diabetes/immunosuppression, IGRA, and anti-TB decision logic before radiation/surgery-only scleral necrosis closure. | `ocular_infection_inflammation` preset |
| `next_transformed_PMC9830568` | Neuroinflammatory demyelination gate requiring MOGAD/ADEM/NMOSD versus infection/neurosarcoid discriminators and MOG/AQP4 cell-based assay testing. | `neuroinflammatory_demyelination` preset |
| `next_native_PMC11980373` | Mold identification gate requiring arthroconidia/morphology, species-level ID, susceptibility, and disseminated fungal source-control treatment planning. | `mold_identification` preset |
| `next_native_PMC3522357` | Pediatric jaw small-round-cell/bone tumor gate requiring Ewing vs osteosarcoma discriminators, CD99/vimentin/EWSR1, and osteoid/matrix assessment. | `bone_small_round_cell_tumor` preset |
| `next_native_PMC5458444` | Postoperative foreign body gate requiring gossypiboma/abscess retrieval and source-control planning before ovarian cyst/tumor closure. | `postoperative_foreign_body` preset |
| `next_native_PMC5590213` | Persistent hCG localization gate requiring extrauterine choriocarcinoma/PUL/phantom hCG comparison and PET-CT localization before uterine GTN closure. | `persistent_hcg_localization` preset |
| `next_transformed_PMC10200070` | GI desmoplastic neuroendocrine gate requiring distal ileal mass, stellate mesenteric desmoplasia, lymph nodes, and resection/lymphadenectomy plan before Peutz-Jeghers closure. | `gi_desmoplastic_neuroendocrine` preset |
| `next_transformed_PMC10240848` | Dual pathology gate requiring pulmonary vascular tumor IHC plus fungal invasion stains/culture before autoimmune pulmonary-renal syndrome closure. | `spindle_cell_pathology` + `mold_identification` presets |
| `next_transformed_PMC10498951` | Spindle-cell sampling pitfall gate requiring carcinosarcoma/biphasic carcinoma consideration despite leiomyosarcoma-like biopsy. | `spindle_cell_pathology` preset |
| `next_transformed_PMC11066795` | Renal spindle-cell mass gate requiring benign neural/mesenchymal mimics and surveillance logic before collecting-duct carcinoma closure. | `renal_spindle_cell_mass` preset |
| `next_transformed_PMC3830810` | Renal spindle-cell mass gate requiring smooth-muscle histology integration before RCC closure when renal leiomyosarcoma remains plausible. | `renal_spindle_cell_mass` preset |
| `next_transformed_PMC4523567` | Immunocompromised retinitis gate requiring toxoplasmosis/PTLD/viral/fungal comparison and sampling false-negative caveats before intraocular PTLD closure. | `immunocompromised_retinitis` preset |
| `next_transformed_PMC9161094` | Neuroinflammatory demyelination gate requiring area postrema + LETM NMOSD/AQP4 testing before lymphoma/biopsy closure. | `neuroinflammatory_demyelination` preset |
| `next_transformed_PMC9332052` | GI neuroendocrine carcinoma gate requiring LCNEC IHC and pancreaticoduodenectomy/lymphadenectomy planning before adenocarcinoma closure. | `gi_neuroendocrine_carcinoma` preset |
| `next_transformed_PMC9934935` | Hematologic cytogenetic subtype gate requiring t(8;21) vs inv(16)/PDGFR confirmation rather than eosinophilia-based AML subtype closure. | `hematologic_cytogenetic_subtype` preset |
| `next_transformed_PMC11039432` | Optic pathway neoplasm gate requiring adult malignant optic glioma/GBM vs PCNSL/inflammatory comparison and targeted optic pathway biopsy. | `optic_pathway_neoplasm` preset |
| `next_transformed_PMC8986709` | Sellar xanthogranuloma gate covers chronic hypopituitarism/headache with T1-hyperintense sellar mass before pituitary apoplexy closure. | `sellar_xanthogranuloma` preset |
| `next_native_PMC9524449` | Submucosal gas cyst gate requiring pneumatosis cystoides intestinalis aspiration/CT confirmation before colonic lipomatosis closure. | `submucosal_gas_cyst` preset |
| `next_native_PMC12506031` | Colonization-vs-infection gate requiring species ecology, culture persistence, clinical syndrome, and no-treatment surveillance before antifungal therapy. | `colonization_vs_infection` preset |

## Next100 Remaining Cases

0 of 23 remain for review.

```text
All 23 next100 Pro-still-failed cases have an initial harness lesson recorded.
```
