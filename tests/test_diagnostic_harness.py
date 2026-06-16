import json
import tempfile
import unittest
from pathlib import Path

from clinical_harness.diagnostic_harness import (
    build_answer_packet,
    build_discriminator_packet,
    build_query_ideas_packet,
    load_evidence_notes,
    validate_retrieval_queries,
)


class DiagnosticHarnessTests(unittest.TestCase):
    def test_query_prompt_excludes_answer_key_and_includes_round_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            case_path = _write_case(Path(tmpdir))

            packet = build_query_ideas_packet(
                case_path,
                round_index=1,
                max_rounds=3,
                previous_queries=("autoimmune encephalitis criteria",),
                preset="neuro_psych",
            )

        self.assertEqual(packet.stage, "query_ideas")
        self.assertEqual(packet.preset, "neuro_psych")
        self.assertEqual(packet.max_rounds, 3)
        self.assertIn("autoimmune encephalitis criteria", packet.prompt)
        self.assertIn("ClinicalHarness", packet.prompt)
        self.assertIn("Do not give a final diagnosis", packet.prompt)
        self.assertIn("organic mimics", packet.prompt)
        self.assertIn("top_mimic_pairs", packet.prompt)
        self.assertNotIn("anti-NMDA receptor encephalitis", packet.prompt)
        self.assertNotIn("PMC123456", packet.prompt)
        self.assertNotIn("10.0000/source", packet.prompt)
        self.assertNotIn("Source Article Title", packet.prompt)
        self.assertEqual(packet.blocked_shortcuts["pmcid"], "blocked_if_known")

    def test_validate_retrieval_queries_blocks_source_shortcuts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            case_path = _write_case(Path(tmpdir))

            violations = validate_retrieval_queries(
                case_path,
                (
                    "PMC123456 diagnosis",
                    "10.0000/source diagnosis",
                    "Source Article Title neurologic case",
                    "A 19 year old woman has subacute psychosis insomnia orofacial movements and two generalized seizures",
                    "subacute psychosis seizures differential diagnosis",
                ),
            )

        reasons = [violation.reason for violation in violations]
        self.assertIn("pmcid", reasons)
        self.assertIn("doi", reasons)
        self.assertIn("case_or_source_title", reasons)
        self.assertIn("exact_prompt_overlap", reasons)
        self.assertEqual(len(violations), 4)

    def test_answer_prompt_uses_distilled_evidence_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            notes_path = root / "notes.jsonl"
            notes_path.write_text(
                json.dumps(
                    {
                        "evidence_id": "pubmed:1",
                        "source_type": "review",
                        "citation": "Example review",
                        "useful_facts": ["CSF pleocytosis supports inflammatory encephalitis."],
                        "diagnostic_discriminators": ["Orofacial dyskinesias distinguish NMDAR syndrome."],
                        "discriminator_table": [
                            {
                                "discriminator": "orofacial dyskinesias",
                                "diagnosis_a": "NMDAR encephalitis",
                                "diagnosis_b": "primary psychosis",
                            }
                        ],
                        "required_tests_or_markers": ["CSF autoimmune encephalitis panel"],
                        "required_imaging_or_procedures": ["MRI brain with contrast"],
                        "required_eeg_or_physiology": ["prolonged EEG"],
                        "temporal_semiology_table": [
                            {
                                "feature": "stereotypy",
                                "case_finding": "recurrent stereotyped visual episodes",
                                "supports": "occipital seizures",
                            }
                        ],
                        "functional_neuro_red_flags": ["urinary retention"],
                        "malignancy_red_flags": ["steroid-responsive mass"],
                        "tissue_diagnosis_plan": ["CSF cytology and flow cytometry"],
                        "serial_imaging_change_table": [
                            {
                                "timepoint": "3 months",
                                "finding": "near-complete mass resolution",
                                "supports": "steroid-responsive lymphoma",
                            }
                        ],
                        "known_cancer_context": ["stage IV epithelial ovarian cancer"],
                        "csf_cytology_plan": ["repeat CSF cytology with adequate volume"],
                        "negative_test_caveats": ["first negative cytology does not exclude leptomeningeal disease"],
                        "antibody_specificity_table": [
                            {
                                "antibody_or_panel": "VGKC complex",
                                "case_result": "negative",
                                "argues_against_subtype": "LGI1",
                            }
                        ],
                        "seronegative_ae_criteria": ["bilateral medial temporal T2 hyperintensity"],
                        "immunotherapy_escalation_plan": ["second-line rituximab for refractory disease"],
                        "emergency_neuro_differential": [
                            {
                                "diagnosis": "CVST",
                                "must_not_miss": True,
                                "case_clues": ["headache", "coma", "normal arterial MRA"],
                                "next_test": "MRV",
                            }
                        ],
                        "emergency_next_tests": ["MRV/CTV"],
                        "empty_output_rescue_rule": "Return a minimum emergency differential.",
                        "microbiology_test_plan": ["anaerobic culture for Actinomyces"],
                        "pathogen_discriminator_table": [
                            {
                                "pathogen": "Actinomyces",
                                "supporting_clues": ["indolent abscess"],
                                "required_tests": ["anaerobic culture", "histopathology"],
                            }
                        ],
                        "antimicrobial_duration_plan": ["prolonged penicillin-based therapy"],
                        "mold_identification_table": [
                            {
                                "organism": "Microascus/Scopulariopsis",
                                "supporting_colony_or_microscopy": ["annellides and conidia"],
                                "confirmatory_test": "sequencing",
                            }
                        ],
                        "fungal_lab_test_plan": ["fungal culture morphology and sequencing"],
                        "antifungal_susceptibility_plan": ["CNS penetration and susceptibility-guided azole"],
                        "neutropenic_infection_caveats": ["lack of gas does not exclude necrotizing fasciitis"],
                        "necrotizing_infection_discriminator_table": [
                            {
                                "entity": "necrotizing fasciitis",
                                "supporting_clues": ["rapid necrosis in neutropenia"],
                                "urgent_action": "surgical exploration",
                            }
                        ],
                        "surgical_source_control_plan": ["urgent debridement"],
                        "granulomatous_overlap_table": [
                            {
                                "entity": "tuberculous sarcoidosis overlap",
                                "supporting_clues": ["Mantoux and ACE elevated"],
                                "negative_test_caveat": "negative IGRA does not exclude active TB",
                            }
                        ],
                        "tb_negative_test_caveats": ["negative IGRA does not exclude active TB"],
                        "dual_therapy_decision_plan": ["anti-TB therapy plus corticosteroids"],
                        "cns_granuloma_discriminator_table": [
                            {
                                "entity": "CNS tuberculoma",
                                "supporting_clues": ["positive Quantiferon"],
                                "biopsy_or_lab_caveat": "non-caseating granuloma can occur in TB",
                            }
                        ],
                        "tb_treatment_continuation_plan": ["continue anti-TB drugs while cultures are pending"],
                        "granulomatous_biopsy_caveats": ["two weeks without improvement is not enough to exclude tuberculoma"],
                        "spindle_cell_differential_table": [
                            {
                                "entity": "mammary stromal sarcoma",
                                "supporting_clues": ["spindle cell breast tumor"],
                                "required_markers": ["CD10", "CD34", "desmin", "SMA"],
                            }
                        ],
                        "organ_specific_marker_panel": ["CD10", "CD34", "desmin", "SMA"],
                        "sarcoma_subtype_plan": ["Do not stop at generic UPS."],
                        "bone_tumor_red_flags": ["age >50 with ABC-like lesion"],
                        "bone_lesion_discriminator_table": [
                            {
                                "entity": "intraosseous angiosarcoma",
                                "supporting_clues": ["secondary ABC pattern"],
                                "required_markers": ["CD31", "CD34", "ERG"],
                            }
                        ],
                        "endothelial_marker_plan": ["repeat biopsy with CD31/CD34/ERG"],
                        "gnathic_radiographic_red_flags": ["widened periodontal ligament space"],
                        "jaw_lesion_discriminator_table": [
                            {
                                "entity": "gnathic osteosarcoma",
                                "supporting_clues": ["widened PDL"],
                                "radiographic_discriminator": "loss of lamina dura",
                            }
                        ],
                        "bone_matrix_assessment_plan": ["osteoid production assessment"],
                        "middle_ear_mass_discriminator_table": [
                            {
                                "entity": "adenomatous neuroendocrine tumor",
                                "supporting_clues": ["retrotympanic mass without bone erosion"],
                                "required_ihc_or_test": "synaptophysin",
                            }
                        ],
                        "otologic_imaging_red_flags": ["absence of pulsatile tinnitus"],
                        "neuroendocrine_ihc_plan": ["synaptophysin", "chromogranin", "cytokeratin"],
                        "keratotic_lesion_discriminator_table": [
                            {
                                "entity": "cutaneous horn",
                                "supporting_clues": ["horn-like hyperkeratosis"],
                                "base_malignancy_risk": "SCC at base",
                            }
                        ],
                        "skin_base_histology_plan": ["wide excision including base"],
                        "dermatology_malignancy_caveats": ["surface hyperkeratosis can hide malignant base"],
                        "maxillofacial_infection_discriminator_table": [
                            {
                                "entity": "chronic suppurative osteomyelitis",
                                "supporting_clues": ["purulent fistula after trauma"],
                                "required_dental_or_bone_finding": "sequestrum",
                            }
                        ],
                        "sequestrum_imaging_plan": ["panoramic radiograph or cone-beam CT"],
                        "odontogenic_source_caveats": ["absence of odontogenic source lowers periapical abscess"],
                        "prenatal_anomaly_pattern_table": [
                            {
                                "candidate_syndrome": "Fryns syndrome",
                                "supporting_anomalies": ["facial dysmorphism", "pulmonary hypoplasia"],
                                "classic_but_absent_feature": "diaphragmatic hernia",
                            }
                        ],
                        "fetal_genetic_testing_plan": ["karyotype and exome/panel if available"],
                        "recurrence_counseling_plan": ["autosomal recessive 25% recurrence risk"],
                        "movement_disorder_phenotype_table": [
                            {
                                "entity": "PSP-P",
                                "supporting_clues": ["asymmetric onset", "initial levodopa response"],
                                "eye_movement_or_fall_discriminator": "slowed vertical saccades without frank gaze palsy",
                            }
                        ],
                        "parkinsonism_imaging_plan": ["MRPI 2.0"],
                        "movement_specialist_management_plan": ["movement disorders specialist referral"],
                        "prior_cancer_mass_context": ["prior melanoma"],
                        "metastasis_mimic_table": [
                            {
                                "entity": "metastatic melanoma",
                                "supporting_clues": ["new unusual-site mass"],
                                "required_ihc_or_marker": "SOX10",
                            }
                        ],
                        "metastatic_ihc_plan": ["S100/SOX10 and Melan-A/HMB-45"],
                        "lipomatous_tumor_discriminator_table": [
                            {
                                "entity": "lipoma with hibernoma component",
                                "supporting_clues": ["mature adipocytes without atypia"],
                                "required_molecular_or_ihc": "MDM2 FISH",
                            }
                        ],
                        "mdm2_testing_plan": ["negative MDM2 FISH supports benign lipomatous tumor"],
                        "benign_lipomatous_features": ["no lipoblasts", "brown fat cells"],
                        "mass_malignancy_red_flags": ["recurrent mass without prior histology"],
                        "tissue_sampling_plan": ["histopathology and IHC"],
                        "benign_malignant_pathology_table": [
                            {
                                "entity": "leiomyosarcoma",
                                "supporting_clues": ["recurrent enlarging painful mass"],
                                "required_pathology": ["mitotic count", "necrosis", "atypia"],
                            }
                        ],
                        "cardiac_pericardial_red_flags": ["recurrent hemorrhagic pericardial effusion"],
                        "pericardial_fluid_caveats": ["negative cytology does not exclude cardiac sarcoma"],
                        "cardiac_tumor_discriminator_table": [
                            {
                                "entity": "angiosarcoma",
                                "supporting_clues": ["heterogeneously enhancing pericardial mass"],
                                "required_tissue_or_marker": "endothelial markers",
                            }
                        ],
                        "cardiac_tissue_plan": ["surgical biopsy with endothelial IHC"],
                        "prion_phenotype_table": [
                            {
                                "feature": "insomnia and dysautonomia",
                                "case_finding": "progressive sleep/autonomic syndrome",
                                "supports": "sporadic fatal insomnia",
                            }
                        ],
                        "exposure_plausibility_table": [
                            {
                                "exposure": "cadaveric graft",
                                "phenotype_match": "weak",
                                "supports_or_refutes": "refutes iatrogenic CJD",
                            }
                        ],
                        "drug_causality_table": [],
                        "management_escalation_rules": ["Escalate immunotherapy if severe and infectious workup negative."],
                        "mechanistic_link": "Inflammatory CNS syndrome links psychiatric symptoms and seizures.",
                        "caveats": ["Review is general evidence, not the source case."],
                        "source_exclusion_checked": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            notes = load_evidence_notes(notes_path)

            packet = build_answer_packet(
                case_path,
                evidence_notes=notes,
                round_index=2,
                max_rounds=3,
                previous_queries=("autoimmune encephalitis criteria",),
                preset="neuro_psych",
            )

        self.assertEqual(packet.stage, "diagnostic_update")
        self.assertEqual(packet.preset, "neuro_psych")
        self.assertIn("distilled_evidence_notes", packet.prompt)
        self.assertIn("pubmed:1", packet.prompt)
        self.assertIn("discriminator_table", packet.prompt)
        self.assertIn("required_tests_or_markers", packet.prompt)
        self.assertIn("required_imaging_or_procedures", packet.prompt)
        self.assertIn("required_eeg_or_physiology", packet.prompt)
        self.assertIn("temporal_semiology_table", packet.prompt)
        self.assertIn("functional_neuro_red_flags", packet.prompt)
        self.assertIn("malignancy_red_flags", packet.prompt)
        self.assertIn("tissue_diagnosis_plan", packet.prompt)
        self.assertIn("serial_imaging_change_table", packet.prompt)
        self.assertIn("known_cancer_context", packet.prompt)
        self.assertIn("csf_cytology_plan", packet.prompt)
        self.assertIn("negative_test_caveats", packet.prompt)
        self.assertIn("antibody_specificity_table", packet.prompt)
        self.assertIn("seronegative_ae_criteria", packet.prompt)
        self.assertIn("immunotherapy_escalation_plan", packet.prompt)
        self.assertIn("emergency_neuro_differential", packet.prompt)
        self.assertIn("emergency_next_tests", packet.prompt)
        self.assertIn("empty_output_rescue_rule", packet.prompt)
        self.assertIn("microbiology_test_plan", packet.prompt)
        self.assertIn("pathogen_discriminator_table", packet.prompt)
        self.assertIn("antimicrobial_duration_plan", packet.prompt)
        self.assertIn("mold_identification_table", packet.prompt)
        self.assertIn("fungal_lab_test_plan", packet.prompt)
        self.assertIn("antifungal_susceptibility_plan", packet.prompt)
        self.assertIn("neutropenic_infection_caveats", packet.prompt)
        self.assertIn("necrotizing_infection_discriminator_table", packet.prompt)
        self.assertIn("surgical_source_control_plan", packet.prompt)
        self.assertIn("granulomatous_overlap_table", packet.prompt)
        self.assertIn("tb_negative_test_caveats", packet.prompt)
        self.assertIn("dual_therapy_decision_plan", packet.prompt)
        self.assertIn("cns_granuloma_discriminator_table", packet.prompt)
        self.assertIn("tb_treatment_continuation_plan", packet.prompt)
        self.assertIn("granulomatous_biopsy_caveats", packet.prompt)
        self.assertIn("spindle_cell_differential_table", packet.prompt)
        self.assertIn("organ_specific_marker_panel", packet.prompt)
        self.assertIn("sarcoma_subtype_plan", packet.prompt)
        self.assertIn("bone_tumor_red_flags", packet.prompt)
        self.assertIn("bone_lesion_discriminator_table", packet.prompt)
        self.assertIn("endothelial_marker_plan", packet.prompt)
        self.assertIn("gnathic_radiographic_red_flags", packet.prompt)
        self.assertIn("jaw_lesion_discriminator_table", packet.prompt)
        self.assertIn("bone_matrix_assessment_plan", packet.prompt)
        self.assertIn("middle_ear_mass_discriminator_table", packet.prompt)
        self.assertIn("otologic_imaging_red_flags", packet.prompt)
        self.assertIn("neuroendocrine_ihc_plan", packet.prompt)
        self.assertIn("keratotic_lesion_discriminator_table", packet.prompt)
        self.assertIn("skin_base_histology_plan", packet.prompt)
        self.assertIn("dermatology_malignancy_caveats", packet.prompt)
        self.assertIn("maxillofacial_infection_discriminator_table", packet.prompt)
        self.assertIn("sequestrum_imaging_plan", packet.prompt)
        self.assertIn("odontogenic_source_caveats", packet.prompt)
        self.assertIn("gynecologic_epithelioid_tumor_table", packet.prompt)
        self.assertIn("uterine_smooth_muscle_ihc_plan", packet.prompt)
        self.assertIn("small_biopsy_malignancy_caveats", packet.prompt)
        self.assertIn("sellar_mass_discriminator_table", packet.prompt)
        self.assertIn("sellar_histology_plan", packet.prompt)
        self.assertIn("pituitary_follow_up_plan", packet.prompt)
        self.assertIn("temporal_bone_mass_discriminator_table", packet.prompt)
        self.assertIn("temporal_bone_biopsy_plan", packet.prompt)
        self.assertIn("inflammatory_malignancy_mimic_caveats", packet.prompt)
        self.assertIn("prenatal_anomaly_pattern_table", packet.prompt)
        self.assertIn("fetal_genetic_testing_plan", packet.prompt)
        self.assertIn("recurrence_counseling_plan", packet.prompt)
        self.assertIn("movement_disorder_phenotype_table", packet.prompt)
        self.assertIn("parkinsonism_imaging_plan", packet.prompt)
        self.assertIn("movement_specialist_management_plan", packet.prompt)
        self.assertIn("prior_cancer_mass_context", packet.prompt)
        self.assertIn("metastasis_mimic_table", packet.prompt)
        self.assertIn("metastatic_ihc_plan", packet.prompt)
        self.assertIn("lipomatous_tumor_discriminator_table", packet.prompt)
        self.assertIn("mdm2_testing_plan", packet.prompt)
        self.assertIn("benign_lipomatous_features", packet.prompt)
        self.assertIn("mass_malignancy_red_flags", packet.prompt)
        self.assertIn("tissue_sampling_plan", packet.prompt)
        self.assertIn("benign_malignant_pathology_table", packet.prompt)
        self.assertIn("cardiac_pericardial_red_flags", packet.prompt)
        self.assertIn("pericardial_fluid_caveats", packet.prompt)
        self.assertIn("cardiac_tumor_discriminator_table", packet.prompt)
        self.assertIn("cardiac_tissue_plan", packet.prompt)
        self.assertIn("prion_phenotype_table", packet.prompt)
        self.assertIn("exposure_plausibility_table", packet.prompt)
        self.assertIn("management_escalation_rules", packet.prompt)
        self.assertIn("stop_or_continue", packet.prompt)
        self.assertNotIn("anti-NMDA receptor encephalitis", packet.prompt)

    def test_discriminator_prompt_injects_preset_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "MOGAD", "rank": 1},
                        {"diagnosis": "pediatric MS", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                previous_queries=("optic neuritis demyelinating disease criteria",),
                preset="demyelination",
            )

        self.assertEqual(packet.stage, "discriminator_retrieval")
        self.assertEqual(packet.preset, "demyelination")
        self.assertIn("MOGAD", packet.prompt)
        self.assertIn("antibody titers", packet.prompt)
        self.assertIn("biomarker_interpretation_queries", packet.prompt)
        self.assertIn("pathology_lineage_queries", packet.prompt)
        self.assertIn("two_event_bridge_queries", packet.prompt)
        self.assertNotIn("PMC123456", packet.prompt)
        self.assertNotIn("10.0000/source", packet.prompt)

    def test_vascular_neuro_preset_requires_vessel_imaging_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "MELAS", "rank": 1},
                        {"diagnosis": "cerebral venous sinus thrombosis", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="vascular_neuro",
            )

        self.assertEqual(packet.preset, "vascular_neuro")
        self.assertIn("MRV/CTV", packet.prompt)
        self.assertIn("vascular_imaging_queries", packet.prompt)
        self.assertIn("cerebral venous sinus thrombosis", packet.prompt)

    def test_seizure_mimic_preset_requires_semiology_and_eeg_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "Charles Bonnet syndrome", "rank": 1},
                        {"diagnosis": "occipital lobe epilepsy", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="seizure_mimic",
            )

        self.assertEqual(packet.preset, "seizure_mimic")
        self.assertIn("seizure_mimic_queries", packet.prompt)
        self.assertIn("prolonged EEG", packet.prompt)
        self.assertIn("stereotypy", packet.prompt)
        self.assertIn("Charles Bonnet syndrome", packet.prompt)

    def test_functional_neuro_preset_requires_structural_red_flag_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "conversion disorder", "rank": 1},
                        {"diagnosis": "tethered cord syndrome", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="functional_neuro",
            )

        self.assertEqual(packet.preset, "functional_neuro")
        self.assertIn("functional_neuro_queries", packet.prompt)
        self.assertIn("absent anal wink", packet.prompt)
        self.assertIn("urinary retention", packet.prompt)
        self.assertIn("tethered cord", packet.prompt)

    def test_neuro_oncology_preset_requires_steroid_responsive_mass_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "Ramsay Hunt syndrome", "rank": 1},
                        {"diagnosis": "primary CNS lymphoma", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="neuro_oncology",
            )

        self.assertEqual(packet.preset, "neuro_oncology")
        self.assertIn("neuro_oncology_queries", packet.prompt)
        self.assertIn("steroid-responsive CNS mass", packet.prompt)
        self.assertIn("PCNSL", packet.prompt)
        self.assertIn("CSF flow cytometry", packet.prompt)

    def test_prion_sleep_preset_requires_phenotype_and_exposure_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "iatrogenic CJD", "rank": 1},
                        {"diagnosis": "sporadic fatal insomnia", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="prion_sleep",
            )

        self.assertEqual(packet.preset, "prion_sleep")
        self.assertIn("prion_sleep_queries", packet.prompt)
        self.assertIn("sleep/autonomic syndrome", packet.prompt)
        self.assertIn("exposure route", packet.prompt)
        self.assertIn("sporadic fatal insomnia", packet.prompt)

    def test_cancer_neuro_preset_requires_repeat_csf_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "cervical artery dissection", "rank": 1},
                        {"diagnosis": "leptomeningeal carcinomatosis", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="cancer_neuro",
            )

        self.assertEqual(packet.preset, "cancer_neuro")
        self.assertIn("cancer_neuro_queries", packet.prompt)
        self.assertIn("first negative CSF cytology", packet.prompt)
        self.assertIn("repeat CSF cytology", packet.prompt)
        self.assertIn("leptomeningeal carcinomatosis", packet.prompt)

    def test_autoimmune_encephalitis_preset_blocks_unproven_antibody_subtype(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "anti-LGI1 limbic encephalitis", "rank": 1},
                        {"diagnosis": "seronegative autoimmune encephalitis", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="autoimmune_encephalitis",
            )

        self.assertEqual(packet.preset, "autoimmune_encephalitis")
        self.assertIn("autoimmune_encephalitis_queries", packet.prompt)
        self.assertIn("Do not finalize LGI1", packet.prompt)
        self.assertIn("seronegative autoimmune encephalitis", packet.prompt)
        self.assertIn("immunotherapy escalation", packet.prompt)

    def test_acute_neuro_emergency_preset_blocks_empty_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={"candidates": []},
                round_index=2,
                max_rounds=3,
                preset="acute_neuro_emergency",
            )

        self.assertEqual(packet.preset, "acute_neuro_emergency")
        self.assertIn("acute_neuro_emergency_queries", packet.prompt)
        self.assertIn("do not return an empty diagnosis", packet.prompt)
        self.assertIn("MRV/CTV", packet.prompt)
        self.assertIn("CVST", packet.prompt)

    def test_infection_microbiology_preset_requires_pathogen_specific_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "brucellar spondylitis", "rank": 1},
                        {"diagnosis": "actinomycotic spinal infection", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="infection_microbiology",
            )

        self.assertEqual(packet.preset, "infection_microbiology")
        self.assertIn("infection_microbiology_queries", packet.prompt)
        self.assertIn("anaerobic culture", packet.prompt)
        self.assertIn("Actinomyces", packet.prompt)
        self.assertIn("Brucella", packet.prompt)

    def test_mold_identification_preset_requires_organism_level_lab_discriminators(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "Cladophialophora bantiana phaeohyphomycosis", "rank": 1},
                        {"diagnosis": "Microascus/Scopulariopsis invasive sinusitis", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="mold_identification",
            )

        self.assertEqual(packet.preset, "mold_identification")
        self.assertIn("mold_identification_queries", packet.prompt)
        self.assertIn("Microascus/Scopulariopsis", packet.prompt)
        self.assertIn("Cladophialophora", packet.prompt)
        self.assertIn("colony morphology", packet.prompt)
        self.assertIn("conidia/hyphae/annellides", packet.prompt)
        self.assertIn("CNS/leptomeningeal involvement", packet.prompt)

    def test_mass_malignancy_preset_requires_tissue_diagnosis_for_recurrent_mass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "vaginal leiomyoma", "rank": 1},
                        {"diagnosis": "primary vaginal leiomyosarcoma", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="mass_malignancy",
            )

        self.assertEqual(packet.preset, "mass_malignancy")
        self.assertIn("mass_malignancy_queries", packet.prompt)
        self.assertIn("prior excision without histology", packet.prompt)
        self.assertIn("leiomyosarcoma", packet.prompt)
        self.assertIn("histopathology", packet.prompt)

    def test_cardiac_pericardial_mass_preset_requires_cytology_caveat_and_tissue_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "primary cardiac lymphoma", "rank": 1},
                        {"diagnosis": "pericardial angiosarcoma", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="cardiac_pericardial_mass",
            )

        self.assertEqual(packet.preset, "cardiac_pericardial_mass")
        self.assertIn("cardiac_pericardial_mass_queries", packet.prompt)
        self.assertIn("negative pericardial fluid cytology", packet.prompt)
        self.assertIn("angiosarcoma", packet.prompt)
        self.assertIn("surgical biopsy", packet.prompt)
        self.assertIn("CD31", packet.prompt)

    def test_spindle_cell_pathology_preset_requires_organ_specific_marker_panel(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "undifferentiated pleomorphic sarcoma", "rank": 1},
                        {"diagnosis": "mammary stromal sarcoma", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="spindle_cell_pathology",
            )

        self.assertEqual(packet.preset, "spindle_cell_pathology")
        self.assertIn("spindle_cell_pathology_queries", packet.prompt)
        self.assertIn("Do not stop at generic sarcoma", packet.prompt)
        self.assertIn("mammary stromal sarcoma", packet.prompt)
        self.assertIn("CD10", packet.prompt)
        self.assertIn("CD34", packet.prompt)
        self.assertIn("desmin", packet.prompt)
        self.assertIn("SMA", packet.prompt)

    def test_bone_vascular_tumor_preset_requires_secondary_abc_and_endothelial_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "telangiectatic osteosarcoma", "rank": 1},
                        {"diagnosis": "intraosseous angiosarcoma with secondary aneurysmal bone cyst", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="bone_vascular_tumor",
            )

        self.assertEqual(packet.preset, "bone_vascular_tumor")
        self.assertIn("bone_vascular_tumor_queries", packet.prompt)
        self.assertIn("secondary aneurysmal bone cyst", packet.prompt)
        self.assertIn("telangiectatic osteosarcoma", packet.prompt)
        self.assertIn("intraosseous angiosarcoma", packet.prompt)
        self.assertIn("CD31", packet.prompt)
        self.assertIn("ERG", packet.prompt)

    def test_gnathic_bone_tumor_preset_requires_pdl_and_matrix_discriminators(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "primary bone lymphoma", "rank": 1},
                        {"diagnosis": "gnathic osteosarcoma", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="gnathic_bone_tumor",
            )

        self.assertEqual(packet.preset, "gnathic_bone_tumor")
        self.assertIn("gnathic_bone_tumor_queries", packet.prompt)
        self.assertIn("widened periodontal ligament space", packet.prompt)
        self.assertIn("loss of lamina dura", packet.prompt)
        self.assertIn("Do not exclude osteosarcoma", packet.prompt)
        self.assertIn("primary bone lymphoma", packet.prompt)
        self.assertIn("osteoid", packet.prompt)

    def test_middle_ear_mass_preset_requires_vascular_and_neuroendocrine_discriminators(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "glomus tympanicum", "rank": 1},
                        {"diagnosis": "adenomatous neuroendocrine tumor of the middle ear", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="middle_ear_mass",
            )

        self.assertEqual(packet.preset, "middle_ear_mass")
        self.assertIn("middle_ear_mass_queries", packet.prompt)
        self.assertIn("pulsatile tinnitus", packet.prompt)
        self.assertIn("bone erosion", packet.prompt)
        self.assertIn("adenomatous neuroendocrine tumor", packet.prompt)
        self.assertIn("synaptophysin", packet.prompt)
        self.assertIn("chromogranin", packet.prompt)

    def test_keratotic_skin_lesion_preset_requires_base_histology(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "pseudoepitheliomatous keratotic balanitis", "rank": 1},
                        {"diagnosis": "penile cutaneous horn", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="keratotic_skin_lesion",
            )

        self.assertEqual(packet.preset, "keratotic_skin_lesion")
        self.assertIn("keratotic_skin_lesion_queries", packet.prompt)
        self.assertIn("cutaneous horn", packet.prompt)
        self.assertIn("base histology", packet.prompt)
        self.assertIn("wide excision", packet.prompt)
        self.assertIn("SCC", packet.prompt)

    def test_prior_cancer_mass_preset_requires_metastasis_before_new_primary_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "malignant peripheral nerve sheath tumor", "rank": 1},
                        {"diagnosis": "metastatic melanoma", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="prior_cancer_mass",
            )

        self.assertEqual(packet.preset, "prior_cancer_mass")
        self.assertIn("prior_cancer_mass_queries", packet.prompt)
        self.assertIn("prior malignancy", packet.prompt)
        self.assertIn("metastatic melanoma", packet.prompt)
        self.assertIn("MPNST", packet.prompt)
        self.assertIn("S100/SOX10", packet.prompt)
        self.assertIn("Melan-A/HMB-45", packet.prompt)

    def test_lipomatous_tumor_molecular_preset_requires_mdm2_fish_interpretation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "atypical lipomatous tumor/well-differentiated liposarcoma", "rank": 1},
                        {"diagnosis": "intramuscular lipoma with hibernoma component", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="lipomatous_tumor_molecular",
            )

        self.assertEqual(packet.preset, "lipomatous_tumor_molecular")
        self.assertIn("lipomatous_tumor_molecular_queries", packet.prompt)
        self.assertIn("MDM2 FISH", packet.prompt)
        self.assertIn("negative amplification supports benign", packet.prompt)
        self.assertIn("hibernoma", packet.prompt)
        self.assertIn("no lipoblasts", packet.prompt)

    def test_immunocompromised_necrotizing_infection_preset_requires_blunted_sign_caveats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "cutaneous mucormycosis", "rank": 1},
                        {"diagnosis": "necrotizing fasciitis", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="immunocompromised_necrotizing_infection",
            )

        self.assertEqual(packet.preset, "immunocompromised_necrotizing_infection")
        self.assertIn("immunocompromised_necrotizing_infection_queries", packet.prompt)
        self.assertIn("lack of gas does not exclude necrotizing fasciitis", packet.prompt)
        self.assertIn("paucicellular biopsy", packet.prompt)
        self.assertIn("urgent surgical exploration", packet.prompt)
        self.assertIn("cutaneous mucormycosis", packet.prompt)

    def test_maxillofacial_osteomyelitis_preset_requires_sequestrum_imaging(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "periapical abscess", "rank": 1},
                        {"diagnosis": "chronic suppurative osteomyelitis of the maxilla", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="maxillofacial_osteomyelitis",
            )

        self.assertEqual(packet.preset, "maxillofacial_osteomyelitis")
        self.assertIn("maxillofacial_osteomyelitis_queries", packet.prompt)
        self.assertIn("odontogenic source", packet.prompt)
        self.assertIn("sequestrum", packet.prompt)
        self.assertIn("panoramic radiograph", packet.prompt)
        self.assertIn("cone-beam CT", packet.prompt)

    def test_granulomatous_overlap_preset_requires_tb_caveats_and_dual_therapy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "sarcoidosis", "rank": 1},
                        {"diagnosis": "tuberculous sarcoidosis overlap", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="granulomatous_overlap",
            )

        self.assertEqual(packet.preset, "granulomatous_overlap")
        self.assertIn("granulomatous_overlap_queries", packet.prompt)
        self.assertIn("negative IGRA does not exclude active TB", packet.prompt)
        self.assertIn("Mantoux", packet.prompt)
        self.assertIn("epididymitis/azoospermia", packet.prompt)
        self.assertIn("anti-TB plus steroids", packet.prompt)

    def test_cns_granulomatous_mass_preset_requires_tb_continuation_caveats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "neurosarcoidosis", "rank": 1},
                        {"diagnosis": "intracranial tuberculoma", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="cns_granulomatous_mass",
            )

        self.assertEqual(packet.preset, "cns_granulomatous_mass")
        self.assertIn("cns_granulomatous_mass_queries", packet.prompt)
        self.assertIn("non-caseating granuloma caveat", packet.prompt)
        self.assertIn("positive IGRA/Quantiferon", packet.prompt)
        self.assertIn("absent pulmonary TB caveat", packet.prompt)
        self.assertIn("two-week nonresponse caveat", packet.prompt)
        self.assertIn("continue anti-TB plus steroids", packet.prompt)

    def test_gynecologic_epithelioid_tumor_preset_requires_small_biopsy_ihc_panel(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "PEComa", "rank": 1},
                        {"diagnosis": "epithelioid leiomyosarcoma", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="gynecologic_epithelioid_tumor",
            )

        self.assertEqual(packet.preset, "gynecologic_epithelioid_tumor")
        self.assertIn("gynecologic_epithelioid_tumor_queries", packet.prompt)
        self.assertIn("small biopsy limitation", packet.prompt)
        self.assertIn("desmin/SMA", packet.prompt)
        self.assertIn("HMB-45/Melan-A", packet.prompt)
        self.assertIn("inhibin/calretinin", packet.prompt)
        self.assertIn("empty output rescue", packet.prompt)

    def test_sellar_xanthogranuloma_preset_requires_cyst_histology_and_followup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "adamantinomatous craniopharyngioma", "rank": 1},
                        {"diagnosis": "sellar xanthogranuloma", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="sellar_xanthogranuloma",
            )

        self.assertEqual(packet.preset, "sellar_xanthogranuloma")
        self.assertIn("sellar_xanthogranuloma_queries", packet.prompt)
        self.assertIn("T1/T2 hyperintense cyst", packet.prompt)
        self.assertIn("foamy macrophages", packet.prompt)
        self.assertIn("cholesterol clefts", packet.prompt)
        self.assertIn("postoperative hormone follow-up", packet.prompt)

    def test_temporal_bone_inflammatory_mass_preset_keeps_malignancy_open_until_biopsy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "external auditory canal SCC", "rank": 1},
                        {"diagnosis": "xanthogranulomatous osteomyelitis", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="temporal_bone_inflammatory_mass",
            )

        self.assertEqual(packet.preset, "temporal_bone_inflammatory_mass")
        self.assertIn("temporal_bone_inflammatory_mass_queries", packet.prompt)
        self.assertIn("normal ESR/CRP caveat", packet.prompt)
        self.assertIn("foamy histiocytes", packet.prompt)
        self.assertIn("malignant cell exclusion", packet.prompt)
        self.assertIn("incisional biopsy/debridement", packet.prompt)

    def test_prenatal_syndromic_pattern_preset_requires_fetal_pattern_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "Meckel-Gruber syndrome", "rank": 1},
                        {"diagnosis": "Fryns syndrome without diaphragmatic hernia", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="prenatal_syndromic_pattern",
            )

        self.assertEqual(packet.preset, "prenatal_syndromic_pattern")
        self.assertIn("prenatal_syndromic_pattern_queries", packet.prompt)
        self.assertIn("Fryns syndrome without diaphragmatic hernia", packet.prompt)
        self.assertIn("Meckel-Gruber syndrome", packet.prompt)
        self.assertIn("facial dysmorphism", packet.prompt)
        self.assertIn("no diaphragmatic hernia", packet.prompt)
        self.assertIn("no polydactyly", packet.prompt)
        self.assertIn("autosomal recessive recurrence risk", packet.prompt)

    def test_movement_disorder_phenotype_preset_requires_psp_variant_discriminators(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            packet = build_discriminator_packet(
                case_path,
                differential={
                    "candidates": [
                        {"diagnosis": "PSP-Richardson syndrome", "rank": 1},
                        {"diagnosis": "PSP-parkinsonism predominant", "rank": 2},
                    ]
                },
                round_index=2,
                max_rounds=3,
                preset="movement_disorder_phenotype",
            )

        self.assertEqual(packet.preset, "movement_disorder_phenotype")
        self.assertIn("movement_disorder_phenotype_queries", packet.prompt)
        self.assertIn("PSP-P", packet.prompt)
        self.assertIn("PSP-RS", packet.prompt)
        self.assertIn("initial levodopa response", packet.prompt)
        self.assertIn("slowed vertical saccades without frank gaze palsy", packet.prompt)
        self.assertIn("MRPI 2.0", packet.prompt)
        self.assertIn("movement disorders specialist", packet.prompt)

    def test_remaining_next100_cluster_presets_expose_query_buckets(self) -> None:
        cases = (
            ("ocular_infection_inflammation", "ocular_infection_inflammation_queries", "TB-endemic exposure"),
            ("neuroinflammatory_demyelination", "neuroinflammatory_demyelination_queries", "MOG-IgG cell-based assay"),
            ("bone_small_round_cell_tumor", "bone_small_round_cell_tumor_queries", "CD99/vimentin"),
            ("postoperative_foreign_body", "postoperative_foreign_body_queries", "gossypiboma"),
            ("persistent_hcg_localization", "persistent_hcg_localization_queries", "PET-CT localization"),
            ("gi_desmoplastic_neuroendocrine", "gi_desmoplastic_neuroendocrine_queries", "stellate mesenteric lesion"),
            ("renal_spindle_cell_mass", "renal_spindle_cell_mass_queries", "smooth muscle bundles"),
            ("immunocompromised_retinitis", "immunocompromised_retinitis_queries", "anti-toxoplasma therapy"),
            ("gi_neuroendocrine_carcinoma", "gi_neuroendocrine_carcinoma_queries", "chromogranin/synaptophysin/CD56"),
            ("hematologic_cytogenetic_subtype", "hematologic_cytogenetic_subtype_queries", "RUNX1-RUNX1T1"),
            ("optic_pathway_neoplasm", "optic_pathway_neoplasm_queries", "targeted optic pathway biopsy"),
            ("submucosal_gas_cyst", "submucosal_gas_cyst_queries", "needle aspiration gas bubbles"),
            ("colonization_vs_infection", "colonization_vs_infection_queries", "clinical stability without therapy"),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_path = _write_case(root)
            for preset, bucket, phrase in cases:
                with self.subTest(preset=preset):
                    packet = build_discriminator_packet(
                        case_path,
                        differential={"candidates": [{"diagnosis": "common mimic", "rank": 1}]},
                        round_index=2,
                        max_rounds=3,
                        preset=preset,
                    )
                    self.assertEqual(packet.preset, preset)
                    self.assertIn(bucket, packet.prompt)
                    self.assertIn(phrase, packet.prompt)


def _write_case(root: Path) -> Path:
    path = root / "case.json"
    path.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "title": "Synthetic neurologic case",
                "prompt": (
                    "A 19-year-old woman has subacute psychosis, insomnia, orofacial movements, "
                    "and two generalized seizures over three weeks. Cerebrospinal fluid shows "
                    "mild lymphocytic pleocytosis."
                ),
                "answer_key": {"final_diagnosis": "anti-NMDA receptor encephalitis"},
                "metadata": {
                    "source_exclusion": {
                        "title": "Source Article Title",
                        "pmcid": "PMC123456",
                        "doi": "10.0000/source",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
