"""Retrieval-guided evaluation for Pro-failed public case manifests."""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .diagnostic_harness import PRESET_CHECKLISTS, _model_visible_case_id, redacted_blocked_shortcuts
from .knowledge_pack import match_cards
from .paper_analysis import analyze_papers
from .preset_selection import select_preset
from .guided_eval import (
    DEFAULT_ALL_PUBLIC_PRO_FAILED_MANIFEST,
    answer_key_from_manifest_row,
    case_from_manifest_row,
    lexical_score,
    load_failed_manifest,
    parse_json_object,
)
from .consensus import consensus_diagnosis, consensus_diagnosis_judged
from .judge import JudgeVerdict, score_diagnosis
from .model_client import OpenAICompatibleChatClient
from .ncbi import NcbiClient
from .pmc import fetch_pmc_articles
from .pubmed import pubmed_search
from .schemas import ClinicalCase, JsonSerializableMixin


QUERY_THEMES_BY_PRESET: dict[str, tuple[str, ...]] = {
    "general": ("diagnostic criteria differential diagnosis review", "clinical discriminator mimics review"),
    "demyelination": (
        "pediatric multiple sclerosis MOGAD NMOSD ADEM diagnostic criteria review",
        "MOG antibody false positive pediatric multiple sclerosis oligoclonal bands MRI lesions review",
    ),
    "autoimmune_encephalitis": (
        "seronegative autoimmune encephalitis diagnostic criteria antibody subtype review",
        "autoimmune encephalitis antibody specificity LGI1 NMDAR CASPR2 diagnostic criteria",
    ),
    "neuro_psych": (
        "psychosis neuropsychiatric lupus anti NMDA encephalitis differential diagnosis review",
        "organic psychosis autoimmune encephalitis systemic lupus discriminators review",
    ),
    "neuro_oncology": (
        "steroid responsive CNS lymphoma cranial neuropathy leptomeningeal enhancement review",
        "Ramsay Hunt syndrome mimic lymphoma internal auditory canal facial nerve enhancement",
    ),
    "vascular_neuro": (
        "cerebral venous sinus thrombosis stroke mimic seizure headache MRV diagnosis",
        "CVST MELAS stroke-like episode differential diagnosis MRI venography",
    ),
    "cns_vasculitis": (
        "primary angiitis central nervous system RCVS differential CSF vessel wall MRI biopsy",
        "PACNS biopsy false negative leptomeningeal enhancement diagnosis review",
    ),
    "seizure_mimic": (
        "occipital epilepsy visual hallucinations Charles Bonnet syndrome EEG differential",
        "visual hallucinations seizure mimic ophthalmologic psychiatric differential review",
    ),
    "functional_neuro": (
        "tethered cord syndrome adult conversion disorder urinary retention saddle anesthesia",
        "functional neurological disorder red flags conus cauda equina tethered cord review",
    ),
    "cancer_neuro": (
        "leptomeningeal carcinomatosis negative CSF cytology repeat sensitivity review",
        "ovarian cancer leptomeningeal metastasis cranial neuropathy headache diagnosis",
    ),
    "prion_sleep": (
        "sporadic fatal insomnia prion disease differential CJD autonomic insomnia review",
        "fatal insomnia diagnostic criteria thalamus PRNP RT QuIC review",
    ),
    "spindle_cell_pathology": (
        "organ specific spindle cell neoplasm immunohistochemistry differential diagnosis review",
        "spindle cell sarcoma mimics cytokeratin desmin SMA CD34 CD10 IHC review",
    ),
    "gynecologic_epithelioid_tumor": (
        "uterine epithelioid leiomyosarcoma PEComa UTROSCT immunohistochemistry differential",
        "gynecologic epithelioid tumor HMB45 Melan-A desmin SMA inhibin calretinin review",
    ),
    "mold_identification": (
        "invasive mold infection identification morphology conidia arthroconidia sequencing antifungal susceptibility",
        "rare invasive mould species laboratory identification MALDI-TOF sequencing differential review",
    ),
    "hematologic_cytogenetic_subtype": (
        "acute myeloid leukemia eosinophilia inv(16) t(8;21) cytogenetic differential",
        "AML cytogenetic subtype eosinophilia FISH RT-PCR diagnostic criteria review",
    ),
    "persistent_hcg_localization": (
        "persistent beta hCG after ectopic pregnancy negative ultrasound PET CT localization",
        "extrauterine choriocarcinoma persistent hCG omental metastasis diagnosis review",
    ),
    "colonization_vs_infection": (
        "ICU positive culture colonization versus infection criteria review",
        "respiratory culture colonization contamination invasive infection diagnostic criteria",
    ),
    "renal_spindle_cell_mass": (
        "renal spindle cell mass leiomyosarcoma sarcomatoid renal cell carcinoma immunohistochemistry",
        "renal mesenchymal tumor spindle cell differential diagnosis IHC review",
    ),
    "keratotic_skin_lesion": (
        "cutaneous horn squamous cell carcinoma",
        "penile cutaneous horn",
    ),
    "bone_vascular_tumor": (
        "secondary aneurysmal bone cyst angiosarcoma endothelial markers CD31 ERG differential",
        "ABC-like bone lesion older adult vascular tumor telangiectatic osteosarcoma differential",
    ),
    "gnathic_bone_tumor": (
        "gnathic osteosarcoma periodontal ligament widening jaw lesion differential diagnosis",
        "mandible lytic lesion osteosarcoma osteomyelitis lymphoma odontogenic tumor radiographic discriminator",
    ),
    "middle_ear_mass": (
        "middle ear adenomatous neuroendocrine tumor glomus tympanicum cholesteatoma differential",
        "retrotympanic mass neuroendocrine tumor synaptophysin chromogranin cytokeratin review",
    ),
    "maxillofacial_osteomyelitis": (
        "chronic suppurative osteomyelitis jaw draining fistula sequestrum cone beam CT",
        "maxillofacial osteomyelitis odontogenic abscess trauma differential diagnosis review",
    ),
    "temporal_bone_inflammatory_mass": (
        "external auditory canal destructive mass xanthogranulomatous osteomyelitis squamous cell carcinoma differential",
        "temporal bone inflammatory mass skull base osteomyelitis malignancy biopsy review",
    ),
    "prenatal_syndromic_pattern": (
        "Fryns syndrome without diaphragmatic hernia prenatal differential Meckel Gruber",
        "fetal anomaly syndrome renal cysts facial dysmorphism pulmonary hypoplasia recurrence counseling",
    ),
    "ocular_infection_inflammation": (
        "ocular tuberculosis scleritis uveitis immunosuppressed differential diagnosis review",
        "necrotizing scleritis infectious mimics tuberculosis toxoplasmosis syphilis fungal review",
    ),
    "bone_small_round_cell_tumor": (
        "Ewing sarcoma jaw osteomyelitis osteosarcoma small round blue cell CD99 EWSR1",
        "pediatric mandibular bone lesion sunray periosteal reaction Ewing osteosarcoma differential",
    ),
    "postoperative_foreign_body": (
        "gossypiboma postoperative abdominal mass abscess imaging spongiform whorled sign",
        "retained surgical sponge pelvic mass differential diagnosis review",
    ),
    "sellar_xanthogranuloma": (
        "sellar xanthogranuloma Rathke cleft cyst craniopharyngioma MRI histology review",
        "cystic sellar mass cholesterol clefts foamy macrophages xanthogranuloma differential",
    ),
    "gi_desmoplastic_neuroendocrine": (
        "small bowel neuroendocrine tumor desmoplastic mesenteric mass intussusception differential",
        "ileal neuroendocrine tumor mesenteric desmoplasia Peutz Jeghers differential",
    ),
    "immunocompromised_retinitis": (
        "transplant retinochoroiditis toxoplasmosis PTLD viral retinitis differential PCR negative",
        "immunocompromised uveitis retinitis toxoplasma lymphoma fungal viral differential review",
    ),
    "gi_neuroendocrine_carcinoma": (
        "ampullary large cell neuroendocrine carcinoma adenocarcinoma immunohistochemistry Ki-67",
        "pancreatobiliary neuroendocrine carcinoma chromogranin synaptophysin CD56 differential",
    ),
    "optic_pathway_neoplasm": (
        "adult malignant optic glioma optic pathway glioblastoma lymphoma inflammatory differential",
        "optic nerve chiasm enlargement rapid visual loss biopsy glioblastoma review",
    ),
    "submucosal_gas_cyst": (
        "pneumatosis cystoides intestinalis submucosal colonic lesions gas aspiration differential",
        "colonoscopy multiple submucosal gas cysts lipoma lymphangioma differential",
    ),
    "prior_cancer_mass": (
        "prior malignancy new soft tissue mass metastasis versus new primary immunohistochemistry",
        "unusual site metastasis recurrent mass tissue diagnosis IHC review",
    ),
    "lipomatous_tumor_molecular": (
        "well differentiated liposarcoma atypical lipomatous tumor MDM2 FISH negative hibernoma differential",
        "deep lipomatous tumor MDM2 CDK4 amplification benign hibernoma differential review",
    ),
    "mass_malignancy": (
        "recurrent enlarging painful soft tissue mass biopsy malignancy red flags leiomyosarcoma",
        "benign versus malignant soft tissue mass recurrence size pain tissue diagnosis review",
    ),
    "cardiac_pericardial_mass": (
        "cardiac angiosarcoma pericardial effusion negative cytology biopsy CD31 ERG",
        "pericardial mass recurrent hemorrhagic effusion lymphoma mesothelioma angiosarcoma differential",
    ),
    "adverse_drug_event": (
        "drug adverse reaction causality timeline dechallenge rechallenge Naranjo prophylaxis continuation",
        "medication induced adverse event onset window rechallenge prophylaxis case review",
    ),
    "infection_microbiology": (
        "culture negative osteomyelitis abscess actinomycosis tuberculosis brucella fungal differential",
        "indolent abscess negative AFB PCR anaerobic culture actinomyces diagnosis review",
    ),
    "immunocompromised_necrotizing_infection": (
        "neutropenic necrotizing fasciitis absent leukocytosis no gas diagnosis surgical exploration",
        "immunocompromised skin necrosis mucormycosis necrotizing fasciitis differential review",
    ),
    "granulomatous_overlap": (
        "sarcoidosis tuberculosis overlap negative IGRA granulomatous uveitis epididymitis review",
        "granulomatous disease TB sarcoid fungal syphilis Bartonella differential negative tests",
    ),
    "neuroinflammatory_demyelination": (
        "MOG antibody disease NMOSD neurosarcoidosis lymphoma infection differential review",
        "longitudinally extensive transverse myelitis area postrema MOGAD AQP4 diagnostic criteria",
    ),
    "cns_granulomatous_mass": (
        "CNS tuberculoma noncaseating granuloma neurosarcoidosis negative culture differential",
        "intracranial granulomatous mass tuberculoma neurosarcoidosis biopsy PCR culture review",
    ),
    "movement_disorder_phenotype": (
        "PSP parkinsonism predominant Richardson syndrome MRPI levodopa response diagnostic criteria",
        "progressive supranuclear palsy variants PSP-P vertical saccades freezing falls review",
    ),
    "acute_neuro_emergency": (
        "cerebral venous thrombosis coma seizure normal arterial MRA MRV diagnosis",
        "acute severe headache seizure aphasia CVST stroke mimic emergency differential",
    ),
    "pathology": (
        "unusual pathology lineage immunohistochemistry flow cytometry cytogenetics differential diagnosis",
        "cytology preliminary pathology discordant clinical features required IHC molecular tests",
    ),
    "sequential_event": (
        "two sequential clinical events bridge diagnosis false negative initial workup repeat imaging biopsy",
        "delayed diagnosis sequential events mechanistic link differential diagnosis case review",
    ),
}


FINALIZATION_GATES_BY_PRESET: dict[str, tuple[str, ...]] = {
    "keratotic_skin_lesion": (
        "Separate the clinical morphologic diagnosis from the underlying/base histology.",
        "If retrieved evidence and case morphology support cutaneous horn, do not replace it with pseudoepitheliomatous keratotic and micaceous balanitis unless the case provides base histology proving that entity.",
        "When base pathology is unknown, final_diagnosis should name the visible morphologic lesion and recommended_next_step should address excision/biopsy of the base and malignancy risk.",
    ),
    "gynecologic_epithelioid_tumor": (
        "Do not finalize PEComa or UTROSCT unless melanocytic or sex-cord markers support it.",
        "If smooth-muscle malignancy remains most consistent, final_diagnosis should name epithelioid leiomyosarcoma and reserve mimics for the differential.",
    ),
    "neuro_oncology": (
        "Steroid responsiveness or fluctuating enhancement must increase concern for lymphoma rather than reassure against malignancy.",
        "Do not finalize Ramsay Hunt or benign neuritis unless infectious evidence clearly outweighs neoplastic cranial-nerve/leptomeningeal evidence.",
    ),
    "autoimmune_encephalitis": (
        "Separate syndrome-level autoimmune encephalitis from antibody subtype.",
        "If antibody evidence is absent or nonspecific, final_diagnosis should not name a specific antibody subtype.",
    ),
    "functional_neuro": (
        "A functional diagnosis is allowed only after structural localizing red flags have been explained.",
        "Sacral sensory, bladder/bowel, conus/cauda, or tethered-cord clues must override psychiatric closure.",
    ),
    "mold_identification": (
        "Do not stop at broad mold categories when retrieved evidence provides organism-level lab discriminators.",
        "Final diagnosis should include the organism level only when morphology, culture, or sequencing clues support it.",
    ),
    "spindle_cell_pathology": (
        "Do not stop at generic spindle-cell neoplasm or undifferentiated sarcoma when organ-specific marker patterns support a named subtype.",
        "When the spindle-cell biopsy is from a carcinoma-prone organ (esophagus, breast, lung), explicitly consider biphasic carcinosarcoma or sarcomatoid carcinoma, since a small biopsy can sample only the spindle component.",
        "A polypoid/ulceroproliferative intraluminal esophageal spindle-cell malignancy is most often carcinosarcoma (spindle cell squamous carcinoma); a pan-CK-negative small biopsy does NOT exclude it because the carcinomatous component is focal. Favor carcinosarcoma over leiomyosarcoma for a polypoid esophageal spindle tumor.",
        "If markers are missing, final_diagnosis should remain provisional and recommended_next_step must specify the marker panel.",
    ),
    "demyelination": (
        "A single positive, low-titer, or transient MOG antibody does not establish MOGAD and does not exclude MS.",
        "If CSF-restricted oligoclonal bands, silent new MRI lesions fulfilling dissemination in time/space, or short eccentric cord lesions are present, weight the diagnosis toward multiple sclerosis.",
    ),
    "neuro_psych": (
        "If systemic lupus criteria (serology, multiorgan involvement) are met and psychosis is present, neuropsychiatric SLE is the default explanation and should be the final_diagnosis.",
        "Do not name anti-NMDA receptor encephalitis as the final_diagnosis unless the case reports a POSITIVE NMDAR antibody. If NMDAR testing is merely pending/absent while lupus features are present, finalize NPSLE and list anti-NMDA encephalitis only in the differential.",
    ),
    "prion_sleep": (
        "Before invoking iatrogenic CJD, confirm the exposure is a recognized prion transmission route (dura mater graft, cadaveric pituitary hormone, corneal transplant, neurosurgical instruments); a cadaveric bone graft is not an established route.",
        "A progressive insomnia / dysautonomia / thalamic-degeneration phenotype with negative family history and PRNP without a mutation supports sporadic fatal insomnia.",
    ),
    "pathology": (
        "Do not default to the most common lymphoma; if monocytic/myeloid differentiation, marrow involvement, or an AML history is present, verify myeloid markers (MPO, CD33, CD117, lysozyme, CD68) before calling B-cell lymphoma.",
        "Final lineage must rest on a marker panel, not on prevalence.",
    ),
    "adverse_drug_event": (
        "Build a dechallenge/rechallenge timeline for every co-administered drug; do not attribute the reaction to the most famous agent by default.",
        "When two drugs are given together (e.g. ATRA + arsenic trioxide in APL), the agent whose start/stop tracks the eruption is the cause, even if it is the less commonly blamed one.",
        "If an antibiotic was dechallenged but the eruption persists and progresses, the antibiotic is exonerated; reconsider the continued essential agents. In APL, arsenic trioxide (ATO) is a recognized cause of erythema multiforme and should be favored over ATRA and over an already-withdrawn antibiotic.",
    ),
    "hematologic_cytogenetic_subtype": (
        "Eosinophilia alone does not establish AML with inv(16)/M4Eo; AML with t(8;21) can present with marked eosinophilia, dysplasia, and Auer rods.",
        "inv(16)/M4Eo eosinophils characteristically show abnormal basophilic (purple) granules and a monocytic component; their ABSENCE, together with morphologically near-normal eosinophil maturation and lack of a monocytic population, argues against inv(16) and supports t(8;21).",
        "Do not finalize a cytogenetic subtype without FISH/karyotype evidence distinguishing inv(16)/t(16;16) from t(8;21); name the subtype the morphology/flow best support and state the confirmatory test.",
    ),
    "neuroinflammatory_demyelination": (
        "An area postrema syndrome (intractable hiccups/vomiting) and/or longitudinally extensive transverse myelitis points to AQP4-IgG NMOSD; do not default to MOGAD.",
        "Resolve MOGAD vs NMOSD with paired MOG-IgG and AQP4-IgG cell-based assays rather than treating both as equally likely.",
    ),
    "infection_microbiology": (
        "Do not replace one 'great mimicker' with another; map the case's organism-specific clues to a single best-fit pathogen.",
        "Sulfur granules, filamentous branching Gram-positive rods, or actinomycotic colonies favor actinomycosis over melioidosis/TB/pyogenic mimics; weight these before naming an endemic mimic.",
    ),
    "renal_spindle_cell_mass": (
        "Include benign neural/mesenchymal tumors (neurofibroma, schwannoma; S100/SOX10 positive) in the differential for a renal spindle-cell mass.",
        "Do not default to malignant sarcomatoid RCC or collecting-duct carcinoma when PAX8/CK are negative and S100 is positive; that pattern supports a benign neural tumor.",
        "When the evidence points to a benign neural tumor, commit to the specific entity using the S100 pattern and architecture, NOT encapsulation (which is unreliable): FOCAL/patchy S100 with serpentine wavy nuclei and ABSENCE of Verocay bodies/Antoni A-B is a neurofibroma; DIFFUSE strong S100 with Verocay bodies and Antoni A-B is a schwannoma. A circumscribed or encapsulated contour does not by itself make a focally-S100+ serpentine-nucleus tumor a schwannoma.",
    ),
    "granulomatous_overlap": (
        "When the case has both TB-specific features (e.g. epididymal involvement, caseation, endemic exposure) and sarcoid-specific features (non-caseating granulomas, multi-organ noninfectious pattern), consider a TB-sarcoid overlap syndrome.",
        "Do not collapse the diagnosis to a single granulomatous disease when exclusion of the other is incomplete.",
    ),
    "colonization_vs_infection": (
        "Decide colonization-vs-infection and species identification separately; getting the colonization call right does not excuse a wrong species.",
        "Use lipid dependence and growth characteristics to identify Malassezia species: M. furfur is lipid-dependent; M. pachydermatis is the non-lipid-dependent ('bowling pin') yeast that grows on standard media.",
    ),
    "gi_neuroendocrine_carcinoma": (
        "When large-cell neuroendocrine morphology plus diffuse neuroendocrine markers and a high Ki-67 are present, the diagnosis is large-cell neuroendocrine carcinoma (LCNEC).",
        "Do not default to mixed adenoneuroendocrine carcinoma (MANEC) unless a distinct second component (e.g. an adenocarcinoma part of >=30%) is actually described; absent that, name the pure neuroendocrine carcinoma subtype.",
    ),
}


ANCHOR_MIMIC_PAIRS_BY_PRESET: dict[str, tuple[str, ...]] = {
    "demyelination": ("pediatric-onset multiple sclerosis", "MOGAD/NMOSD/ADEM"),
    "neuro_psych": ("NPSLE/lupus psychosis", "anti-NMDA receptor encephalitis"),
    "prion_sleep": ("sporadic fatal insomnia", "iatrogenic CJD"),
    "bone_vascular_tumor": ("intraosseous angiosarcoma with secondary ABC", "telangiectatic osteosarcoma"),
    "pathology": ("myeloid sarcoma/granulocytic sarcoma", "DLBCL/lymphoma"),
    "adverse_drug_event": ("arsenic trioxide adverse event", "ATRA adverse event"),
    "spindle_cell_pathology": ("organ-specific spindle-cell subtype or biphasic carcinosarcoma", "generic sarcoma/common mimic"),
    "mold_identification": ("case-specific species", "familiar genus or sibling species"),
    "hematologic_cytogenetic_subtype": ("AML with t(8;21)", "AML with inv(16)"),
    "neuroinflammatory_demyelination": ("AQP4-IgG NMOSD (area postrema/LETM)", "MOGAD"),
    "infection_microbiology": ("indolent organism with specific clues (e.g. actinomycosis)", "another 'great mimicker' (TB/melioidosis)"),
    "renal_spindle_cell_mass": ("benign neural/mesenchymal mimic (neurofibroma/schwannoma)", "malignant sarcomatoid RCC/collecting-duct"),
    "granulomatous_overlap": ("TB-sarcoid overlap syndrome", "single granulomatous disease"),
    "colonization_vs_infection": ("case-specific species by ecology/lipid-dependence", "familiar sibling species"),
}


# Applied to EVERY case regardless of preset. Derived from the 24 hardest failures
# (docs/hard24_gap_analysis_20260614.md): the load-bearing diagnostic principles must be universal,
# because the failures clustered in cases the preset router did NOT send to a matching preset
# (e.g. drug-interaction cases that never hit adverse_drug_event). Kept short and high-signal since
# they prepend to every prompt.
UNIVERSAL_FINALIZATION_GATES: tuple[str, ...] = (
    "Base rates first (Occam + the common-is-common rule): a COMMON diagnosis that fully explains all "
    "the findings IS the answer — do not trade it for a rarer or more exotic one to seem precise or "
    "clever. Combined UMN+LMN signs are ALS until proven otherwise; the classic syndrome gets the "
    "classic diagnosis. Only escalate to a rarer entity when the common diagnosis leaves specific "
    "findings unexplained OR the textbook clue is conspicuously absent. This rule outranks the "
    "de-anchoring and specificity rules below; apply those only after the common diagnosis has failed.",
    "Anti-anchoring (when the common diagnosis FAILS to explain the case): name the rarer entity that "
    "produces this same syndrome and actively seek or exclude it — the case may have had its textbook "
    "clue removed. But do not invoke a rare entity that no case feature supports.",
    "Iatrogenic-first: for any new neuro/psychiatric syndrome in a patient on, recently started, "
    "changed, withdrawn, or potentially interacting medications, build a medication timeline and weigh "
    "a drug effect / interaction / withdrawal / drug-induced deficiency (and drug->metabolic chains, "
    "e.g. enzyme-inducing AED -> low vitamin D -> hypocalcemia) alongside intrinsic disease. A positive "
    "dechallenge (symptoms resolve when the drug is stopped/substituted) is strong evidence.",
    "Treatable can't-miss when the case supports it: exclude a treatable emergency before a diagnosis "
    "of exclusion WHEN case features actually raise it — e.g. exclude HSV/infectious encephalitis (CSF "
    "HSV PCR + empiric acyclovir) before settling on autoimmune encephalitis in a compatible "
    "encephalitic case. Do not reflexively list every can't-miss for a presentation that does not raise it.",
    "Commit to the specific entity the evidence supports — but never MANUFACTURE a rare/exotic diagnosis "
    "to appear precise. Name a rare entity only when a discriminating case feature supports it over the "
    "common one. For a genetic phenotype the case points to, disambiguate the GENE rather than a "
    "near-neighbor (SPG7 vs DJ-1, FXTAS vs SCA12, CDKL5 vs SPG4, 'mitochondrial' vs ATP1A3); but a "
    "recognizable common acquired disease (e.g. ALS) is a specific answer, not a 'too-generic' one. When "
    "a syndrome is near-pathognomonic for an antibody subtype (young woman with orofacial dyskinesias + "
    "autonomic instability + psychiatric -> anti-NMDAR), commit to it; hedge to syndrome-level only when "
    "the picture is genuinely nonspecific. Conversely, do NOT default to anti-NMDAR (or any single "
    "antibody) without that antibody's evidence: 'seronegative autoimmune encephalitis' is valid when "
    "criteria are met without a positive antibody, and when features span more than one antibody "
    "syndrome name the OVERLAP (e.g. MOG+NMDAR, or Morvan/CASPR2 features) rather than forcing one.",
    "Seek the refuting test: name the single objective result that would most argue AGAINST your "
    "leading diagnosis and check whether the case already contains it. A discordant result overrides a "
    "fitting story (a NORMAL DaTscan argues for drug-induced parkinsonism over neurodegeneration; a "
    "transient/low-titer antibody or an evolving lesion on follow-up imaging argues against autoimmune "
    "closure and for re-imaging / a second pathology; elevated antithyroid antibodies point to SREAT).",
    "The prior/referral label is a hypothesis, not the answer: a new presentation in a patient with a "
    "KNOWN rare disease is most likely a complication or relapse of that disease (do not diagnose around "
    "it); a referral 'for X' does not make the diagnosis X.",
    "Global vs focal, and parsimony: distinguish a diffuse/global process from a systemic insult "
    "(e.g. diffuse cerebral edema after shock/arrest = global anoxic injury, not a focal vascular "
    "event); do not add complications the case does not support.",
    "Parsimony before comorbidity: prefer ONE diagnosis that explains all findings. Invoke a second "
    "pathology only when specific findings remain unexplained by the first, or a marker / known disease "
    "demands it — never add a speculative second diagnosis.",
)


def finalization_gates_for(preset: str, config: "HarnessConfig") -> list[str]:
    """Universal gates (every case) + preset-specific gates. Empty when gates are ablated off."""
    if not config.use_gates:
        return []
    return [*UNIVERSAL_FINALIZATION_GATES, *FINALIZATION_GATES_BY_PRESET.get(preset, ())]


ANCHOR_RISKS_BY_PRESET: dict[str, tuple[str, ...]] = {
    "demyelination": ("Do not let a single positive, low-titer, or transient MOG antibody override MS-specific MRI/OCB/time-course evidence.",),
    "neuro_psych": ("Do not default to anti-NMDA encephalitis when systemic lupus evidence supports NPSLE.",),
    "prion_sleep": ("Do not let remote exposure plausibility override the fatal insomnia phenotype; verify the exposure is a recognized prion transmission route.",),
    "bone_vascular_tumor": ("ABC-like hemorrhagic bone lesions in adults can be secondary to vascular malignancy.",),
    "pathology": ("Do not assign the most common lymphoma lineage without checking myeloid/monocytic markers and marrow/AML context.",),
    "adverse_drug_event": ("Build a symmetric medication timeline for every co-administered drug before blaming the more familiar one.",),
    "spindle_cell_pathology": ("Generic spindle-cell sarcoma is not a final subtype when an organ-specific entity or a biphasic carcinosarcoma/sarcomatoid carcinoma remains.",),
    "mold_identification": ("Do not substitute a familiar genus or the more commonly reported sibling species for the species the morphology/sequencing clues indicate.",),
    "hematologic_cytogenetic_subtype": ("Eosinophilia does not establish inv(16); demand cytogenetics/FISH for both inv(16) and t(8;21).",),
    "neuroinflammatory_demyelination": ("Do not default to MOGAD; an area postrema syndrome plus longitudinally extensive myelitis points to AQP4-IgG NMOSD pending cell-based assays.",),
    "infection_microbiology": ("Do not swap one 'great mimicker' for another; weight organism-specific clues (sulfur granules/filamentous Gram-positive rods favor actinomycosis).",),
    "renal_spindle_cell_mass": ("A benign neural/mesenchymal tumor (S100+ neurofibroma/schwannoma) can mimic a malignant renal spindle-cell mass; do not default to sarcomatoid RCC.",),
    "granulomatous_overlap": ("When TB-specific and sarcoid-specific features coexist with incomplete exclusion, consider an overlap syndrome rather than forcing one label.",),
    "colonization_vs_infection": ("Separate the colonization-vs-infection call from species identification; fix the species by ecology and lipid-dependence (M. furfur is lipid-dependent; M. pachydermatis is not).",),
}


COMPLEX_PRESETS_REQUIRING_SECOND_LOOK = {
    "spindle_cell_pathology",
    "pathology",
    "mold_identification",
    "demyelination",
    "neuro_psych",
    "prion_sleep",
    "bone_vascular_tumor",
    "adverse_drug_event",
    "infection_microbiology",
    "hematologic_cytogenetic_subtype",
    "sequential_event",
}


@dataclass(frozen=True)
class HarnessConfig:
    """Feature toggles for ablation studies.

    Defaults = the full harness. Turning a flag off removes one learned component so its
    contribution can be measured independently:

    - ``use_gates``: inject the per-preset finalization gates + anchor mimic pair/risks into the
      distillation and final-answer prompts (the anti-anchoring closure rules).
    - ``use_contrast_queries``: add the symmetric "A versus B" mimic-contrast retrieval query.
    - ``use_relevance_filter``: re-query on all-off-topic results and suppress zero-relevance
      evidence from the model-facing packet.
    - ``adaptive_rounds``: let the distillation subagent decide whether another retrieval round is
      needed (based on whether it can confidently discriminate the lead diagnosis from its top
      mimic), instead of always running a fixed number of rounds. ``max_rounds`` becomes a safety
      cap and ``min_rounds`` a floor. Turn off to reproduce fixed-round ablations.
    """

    use_gates: bool = True
    use_contrast_queries: bool = True
    use_relevance_filter: bool = True
    adaptive_rounds: bool = True
    min_rounds: int = 1
    # Inject feature-matched cards from the stored knowledge pack (rare-entity discriminators) into
    # the final prompt as "specific entities to consider." Niche knowledge the model lacks in weights.
    use_knowledge_pack: bool = True
    # Context-isolated scaled retrieval (ADR-040): screen EVERY retrieved paper in its own Flash call
    # and feed only the distilled relevant notes to the final prompt, instead of capping at the top-8
    # raw abstracts. Decouples papers-screened from context-used so breadth (more top-n / queries) can
    # actually be increased. Off by default (opt-in experiment).
    use_paper_extractor: bool = False
    paper_extractor_concurrency: int = 8
    # Discriminator-driven re-rank (ADR-037): a focused second pass that reorders the model's own top-5
    # by case-specific discriminator match rather than base-rate familiarity. Targets the ranking error
    # where the gold is in the top-5 but a prototypical near-neighbor is #1.
    use_rerank: bool = False
    # Eval mode (default ON for benchmarking): the harness must never retrieve, read, or rely on the
    # specific source paper a benchmark vignette was derived from (matched by pmcid/doi/title) — that
    # would be cheating. Turn OFF for the real doctor-assist use case, where reading the actual source
    # case report (if one exists) is legitimate and useful.
    eval_mode: bool = True


@dataclass(frozen=True)
class RetrievalQuery(JsonSerializableMixin):
    query_id: str
    query: str
    source: str
    intent: str
    round_index: int = 1
    generated_by: str = "preset_template"


@dataclass(frozen=True)
class RetrievalEvidence(JsonSerializableMixin):
    evidence_id: str
    query_id: str
    rank: int
    pmid: str | None
    pmcid: str | None
    doi: str | None
    title: str | None
    journal: str | None
    publication_year: str | None
    publication_types: tuple[str, ...]
    url: str | None
    abstract_snippet: str | None
    source_api: str = "pubmed"
    source_scope: str = "abstract"
    full_text_snippet: str | None = None
    excluded: bool = False
    exclusion_reason: str | None = None
    relevance: int = 0


@dataclass(frozen=True)
class EvidenceSynthesis(JsonSerializableMixin):
    case_id: str
    preset: str
    synthesis_round: int
    useful_discriminators: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    top_mimic_pair: tuple[str, ...] = field(default_factory=tuple)
    anchor_risks: tuple[str, ...] = field(default_factory=tuple)
    additional_queries: tuple[str, ...] = field(default_factory=tuple)
    need_full_text_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    more_retrieval_needed: bool = False
    differential_resolved: bool = False
    remaining_uncertainty: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RetrievalGuidedEvalRow(JsonSerializableMixin):
    case_id: str
    preset: str
    expected_diagnosis: str
    model_final_diagnosis: str | None
    lexical_score: str
    query_count: int
    evidence_count: int
    synthesis_path: str | None
    prompt_path: str
    query_path: str
    evidence_path: str
    response_path: str | None
    error: str | None = None
    # Primary correctness signal when an LLM judge is enabled. ``score`` is the
    # judge-or-lexical verdict actually used for pass/fail accounting; the lexical_score
    # field above is retained as the cheap pre-pass for transparency/regression tracking.
    score: str | None = None
    score_method: str | None = None
    judge_match_type: str | None = None
    judge_rationale: str | None = None
    # Self-consistency: number of answer samples and the winning-cluster agreement fraction.
    samples: int = 1
    agreement: float | None = None
    # Top-5 ranked differential: 1-based rank at which the gold diagnosis first matches a ranked
    # candidate (None if not in the top 5). pass@k = gold_rank is not None and gold_rank <= k.
    gold_rank: int | None = None


EventEmitter = Callable[[dict[str, Any]], None]
ModelCallRecorder = Callable[[dict[str, Any]], None]
ToolCallRecorder = Callable[[dict[str, Any]], None]


class _CaseTrace:
    """Writes viewer-compatible per-case events and forwards them to an optional callback."""

    def __init__(
        self,
        *,
        run_id: str,
        case_id: str,
        path: Path,
        emitter: EventEmitter | None,
    ) -> None:
        self.run_id = run_id
        self.case_id = case_id
        self.path = path
        self.emitter = emitter
        self.seq = 0
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    def emit(
        self,
        event_type: str,
        actor: str,
        title: str,
        *,
        round_index: int | None = None,
        summary: str | None = None,
        status: str = "ok",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            event = {
                "id": f"e{self.seq:04d}",
                "seq": self.seq,
                "ts": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "run_id": self.run_id,
                "case_id": self.case_id,
                "round": round_index,
                "type": event_type,
                "actor": actor,
                "title": title,
                "summary": summary,
                "status": status,
                "payload": payload or {},
            }
            self.seq += 1
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
        if self.emitter is not None:
            try:
                self.emitter(event)
            except Exception:
                # Observation must not change evaluation semantics.
                pass
        return event


def run_retrieval_guided_manifest_eval(
    *,
    manifest_path: str | Path = DEFAULT_ALL_PUBLIC_PRO_FAILED_MANIFEST,
    out_dir: str | Path,
    case_ids: tuple[str, ...] = (),
    limit: int | None = None,
    dry_run: bool = False,
    retrieve: bool = True,
    pubmed_client: NcbiClient | None = None,
    pmc_client: NcbiClient | None = None,
    model_client: OpenAICompatibleChatClient | None = None,
    model_name: str | None = None,
    max_queries: int = 2,
    articles_per_query: int = 3,
    max_rounds: int = 1,
    distill_evidence: bool = False,
    use_full_text: bool = False,
    skip_existing: bool = False,
    progress: bool = False,
    judge: bool = False,
    judge_client: OpenAICompatibleChatClient | None = None,
    judge_model: str | None = None,
    samples: int = 1,
    sample_temperature: float = 0.5,
    use_preset_overrides: bool = True,
    concurrency: int = 1,
    config: HarnessConfig = HarnessConfig(),
    emitter: EventEmitter | None = None,
) -> tuple[RetrievalGuidedEvalRow, ...]:
    rows = load_failed_manifest(manifest_path)
    if case_ids:
        wanted = set(case_ids)
        rows = [row for row in rows if row["case_id"] in wanted]
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise ValueError("no cases selected")
    if max_queries < 1:
        raise ValueError("max_queries must be at least 1")
    if articles_per_query < 1:
        raise ValueError("articles_per_query must be at least 1")
    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")
    if retrieve and pubmed_client is None:
        raise ValueError("pubmed_client is required when retrieve=True")
    if use_full_text and pmc_client is None:
        raise ValueError("pmc_client is required when use_full_text=True")
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    # Construct the answer client once, up front, so concurrent workers share one thread-safe
    # client instead of racing on lazy initialization inside the per-case body.
    if model_client is None and not dry_run:
        model_client = OpenAICompatibleChatClient.from_env(model=model_name)
    judge_fallback_client: OpenAICompatibleChatClient | None = None
    if judge and judge_client is None and not dry_run:
        # Resolve an independent judge model when requested (e.g. deepseek-v4-pro grading
        # deepseek-v4-flash answers); otherwise reuse the answer client. The judge only runs on
        # lexical non-passes, so this stays cheap.
        resolved_judge_model = judge_model or os.getenv("DEEPSEEK_JUDGE_MODEL")
        if resolved_judge_model:
            judge_client = OpenAICompatibleChatClient.from_env(model=resolved_judge_model)
            # Secondary judge (the answer model) backs up the slower primary judge if it
            # times out, so a flaky pro-judge call does not collapse to the lexical proxy.
            judge_fallback_client = model_client or OpenAICompatibleChatClient.from_env(model=model_name)
        else:
            judge_client = model_client or OpenAICompatibleChatClient.from_env(model=model_name)
    total = len(rows)
    run_id = root.name

    def _run_case(index: int, manifest_row: dict[str, Any]) -> RetrievalGuidedEvalRow:
        case = case_from_manifest_row(manifest_row)
        answer_key = answer_key_from_manifest_row(manifest_row)
        has_expected_answer = _has_expected_answer(answer_key, manifest_row)
        expected_diagnosis = answer_key["diagnosis"] if has_expected_answer else ""
        preset = select_preset(case.prompt, case_id=case.case_id, use_overrides=use_preset_overrides)
        if progress:
            print(f"[{index}/{total}] retrieval-guided {case.case_id} preset={preset}", file=sys.stderr, flush=True)

        query_path = root / f"{case.case_id}.queries.json"
        evidence_path = root / f"{case.case_id}.evidence.json"
        synthesis_path = root / f"{case.case_id}.synthesis.json"
        prompt_path = root / f"{case.case_id}.retrieval_prompt.txt"
        response_path = root / f"{case.case_id}.retrieval_response.json"
        event_path = root / f"{case.case_id}.events.jsonl"

        if skip_existing and response_path.exists():
            stored = json.loads(response_path.read_text(encoding="utf-8"))
            content = stored.get("content")
            model_payload = content if isinstance(content, dict) else None
            error_value = stored.get("error")
            error = error_value if isinstance(error_value, str) else None
            queries = _read_json_array(query_path, RetrievalQuery)
            evidence = _read_json_array(evidence_path, RetrievalEvidence)
            syntheses = _read_json_array(synthesis_path, EvidenceSynthesis)
            final = _optional_str(model_payload, "final_diagnosis") if model_payload else None
            _jc = judge_client if judge else None
            row = RetrievalGuidedEvalRow(
                case_id=case.case_id,
                preset=preset,
                expected_diagnosis=expected_diagnosis,
                model_final_diagnosis=final,
                query_count=len(queries),
                evidence_count=len([item for item in evidence if not item.excluded]),
                synthesis_path=str(synthesis_path) if syntheses else None,
                prompt_path=str(prompt_path),
                query_path=str(query_path),
                evidence_path=str(evidence_path),
                response_path=str(response_path),
                error=error,
                gold_rank=(
                    _gold_rank(_ranked_diagnoses(model_payload), answer_key, judge_client=_jc, fallback_client=judge_fallback_client)
                    if has_expected_answer
                    else None
                ),
                **_score_fields(final, answer_key if has_expected_answer else None, judge_client=_jc, fallback_client=judge_fallback_client),
            )
            if event_path.exists():
                return row
            trace = _CaseTrace(run_id=run_id, case_id=case.case_id, path=event_path, emitter=emitter)
            trace.emit(
                "case_started",
                "runner",
                f"Case {case.case_id}",
                summary=f"preset: {preset}",
                payload={"preset": preset, "expected_diagnosis": expected_diagnosis or None},
            )
            _emit_existing_case_trace(trace, row)
            return row

        trace = _CaseTrace(run_id=run_id, case_id=case.case_id, path=event_path, emitter=emitter)
        trace.emit(
            "case_started",
            "runner",
            f"Case {case.case_id}",
            summary=f"preset: {preset}",
            payload={"preset": preset, "expected_diagnosis": expected_diagnosis or None},
        )

        def record_model_call(payload: dict[str, Any]) -> None:
            actor = str(payload.pop("actor", "system"))
            title = str(payload.pop("title", "Model call"))
            round_value = payload.pop("round", None)
            status = "error" if payload.get("error") else "ok"
            trace.emit(
                "model_call",
                actor,
                title,
                round_index=round_value if isinstance(round_value, int) else None,
                summary=_model_call_event_summary(payload),
                status=status,
                payload=payload,
            )

        def record_tool_call(payload: dict[str, Any]) -> None:
            actor = str(payload.pop("actor", "retriever"))
            title = str(payload.pop("title", "Tool call"))
            round_value = payload.pop("round", None)
            status = "error" if payload.get("error") else "ok"
            trace.emit(
                "tool_call",
                actor,
                title,
                round_index=round_value if isinstance(round_value, int) else None,
                summary=_tool_call_event_summary(payload),
                status=status,
                payload=payload,
            )

        queries: tuple[RetrievalQuery, ...] = ()
        evidence: tuple[RetrievalEvidence, ...] = ()
        syntheses: tuple[EvidenceSynthesis, ...] = ()
        previous_queries: set[str] = set()
        for round_index in range(1, max_rounds + 1):
            trace.emit("round_started", "system", f"Round {round_index}", round_index=round_index)
            round_queries = build_retrieval_queries(
                case,
                preset=preset,
                max_queries=max_queries,
                round_index=round_index,
                previous_queries=tuple(previous_queries),
                evidence=evidence,
                synthesis=syntheses[-1] if syntheses else None,
                config=config,
            )
            previous_queries.update(query.query for query in round_queries)
            queries = (*queries, *round_queries)
            for query in round_queries:
                trace.emit(
                    "query_generated",
                    "planner",
                    query.query,
                    round_index=round_index,
                    summary=f"{query.source} · {query.generated_by}",
                    payload=query.to_dict(),
                )
            if retrieve:
                assert pubmed_client is not None
                round_evidence = collect_pubmed_evidence(
                    pubmed_client,
                    case,
                    queries=round_queries,
                    articles_per_query=articles_per_query,
                    seen_pmids={item.pmid for item in evidence if item.pmid},
                    preset=preset,
                    config=config,
                    tool_call_recorder=record_tool_call,
                )
                evidence = (*evidence, *round_evidence)
                kept = [item for item in round_evidence if not item.excluded]
                trace.emit(
                    "search_executed",
                    "retriever",
                    f"Retrieved {len(round_evidence)} record(s)",
                    round_index=round_index,
                    summary=f"{len(kept)} kept after exclusion",
                    payload={"total": len(round_evidence), "kept": len(kept)},
                )
                for item in round_evidence:
                    trace.emit(
                        "evidence_retrieved",
                        "retriever",
                        item.title or item.evidence_id,
                        round_index=round_index,
                        summary=_evidence_event_summary(item),
                        status="warn" if item.excluded else "ok",
                        payload=item.to_dict(),
                    )
            else:
                trace.emit(
                    "search_executed",
                    "retriever",
                    "Retrieval skipped",
                    round_index=round_index,
                    status="info",
                    payload={"total": 0, "kept": 0, "retrieve": False},
                )
            if use_full_text and retrieve:
                assert pmc_client is not None
                evidence = enrich_evidence_with_full_text(
                    pmc_client,
                    case,
                    evidence=evidence,
                    tool_call_recorder=record_tool_call,
                )
            if distill_evidence and not dry_run:
                assert model_client is not None  # eagerly constructed before dispatch
                synthesis = distill_retrieved_evidence(
                    model_client,
                    case,
                    preset=preset,
                    evidence=evidence,
                    round_index=round_index,
                    config=config,
                    model_call_recorder=record_model_call,
                )
            else:
                synthesis = deterministic_evidence_synthesis(
                    case,
                    preset=preset,
                    evidence=evidence,
                    round_index=round_index,
                    config=config,
                )
            syntheses = (*syntheses, synthesis)
            trace.emit(
                "synthesis",
                "synthesizer",
                f"Synthesis · {len(synthesis.useful_discriminators)} discriminator(s)",
                round_index=round_index,
                summary=(
                    "resolved" if synthesis.differential_resolved else
                    "more retrieval needed" if synthesis.more_retrieval_needed else
                    "synthesized evidence"
                ),
                status="warn" if synthesis.more_retrieval_needed else "ok",
                payload=synthesis.to_dict(),
            )
            trace.emit("round_completed", "system", f"Round {round_index} complete", round_index=round_index)
            if not should_run_another_round(
                preset=preset,
                round_index=round_index,
                max_rounds=max_rounds,
                evidence=evidence,
                synthesis=synthesis,
                previous_queries=previous_queries,
                config=config,
            ):
                break

        query_path.write_text(json.dumps([query.to_dict() for query in queries], indent=2, sort_keys=True) + "\n")
        evidence_path.write_text(
            json.dumps([item.to_dict() for item in evidence], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        synthesis_path_value = str(synthesis_path) if syntheses else None
        if syntheses:
            synthesis_path.write_text(
                json.dumps([item.to_dict() for item in syntheses], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        paper_analyses: tuple = ()
        if config.use_paper_extractor and not dry_run and retrieve:
            assert model_client is not None
            included_ev = [item for item in evidence if not item.excluded]
            differential_context = "; ".join(
                d.get("entity", "") for syn in syntheses for d in syn.useful_discriminators
            )[:600] or "open differential"
            # Hand the screener the model's full working differential so its relevance judgment is
            # nuanced to THIS case (not topical). One cheap Flash call, reused across all papers.
            clinical_reasoning = _initial_clinical_assessment(
                model_client,
                case,
                preset,
                model_call_recorder=record_model_call,
            )
            paper_analyses = analyze_papers(
                model_client,
                papers=[
                    {"evidence_id": e.evidence_id, "pmid": e.pmid, "doi": e.doi, "title": e.title,
                     "abstract_snippet": e.abstract_snippet, "full_text_snippet": e.full_text_snippet}
                    for e in included_ev
                ],
                case_summary=case.prompt,
                differential_context=differential_context,
                clinical_reasoning=clinical_reasoning,
                concurrency=config.paper_extractor_concurrency,
                model_call_recorder=record_model_call,
            )

        prompt = build_retrieval_guided_final_prompt(
            case,
            preset=preset,
            evidence=evidence,
            syntheses=syntheses,
            max_rounds=max_rounds,
            config=config,
            paper_analyses=paper_analyses,
        )
        prompt_path.write_text(prompt, encoding="utf-8")
        trace.emit(
            "prompt_built",
            "diagnostician",
            "Final prompt assembled",
            summary=_prompt_event_summary(prompt),
            payload=_prompt_event_payload(prompt),
        )

        model_payload: dict[str, Any] | None = None
        error: str | None = None
        agreement: float | None = None
        response_path_value: str | None
        if dry_run:
            response_path_value = None
        else:
            assert model_client is not None  # eagerly constructed before dispatch
            model_payload, response_payload, error, agreement = _generate_final_answer(
                model_client,
                prompt=prompt,
                case=case,
                preset=preset,
                samples=samples,
                sample_temperature=sample_temperature,
                consensus_judge=judge_client if judge else None,
                model_call_recorder=record_model_call,
            )
            response_path.write_text(json.dumps(response_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            response_path_value = str(response_path)
            trace.emit(
                "model_response",
                "diagnostician",
                f"Model response · {response_payload.get('model') or model_name or 'unknown model'}",
                summary=_model_response_event_summary(response_payload),
                status="error" if error else "ok",
                payload={
                    "model": response_payload.get("model"),
                    "latency_ms": response_payload.get("latency_ms"),
                    "usage": _response_usage(response_payload),
                    "error": response_payload.get("error"),
                    "raw_content": response_payload.get("raw_content"),
                    "raw": response_payload.get("raw"),
                    "content": response_payload.get("content"),
                    "self_consistency": response_payload.get("self_consistency"),
                },
            )
            if config.use_rerank and model_payload:
                _candidates = _ranked_diagnoses(model_payload)
                if len(_candidates) >= 2:
                    assert model_client is not None
                    _ev = "; ".join(d.get("entity", "") for syn in syntheses for d in syn.useful_discriminators)[:600]
                    _reranked = rerank_differential(
                        model_client,
                        case=case,
                        candidates=_candidates,
                        evidence_summary=_ev,
                        model_call_recorder=record_model_call,
                    )
                    model_payload["ranked_differential"] = [{"rank": i + 1, "diagnosis": d} for i, d in enumerate(_reranked)]
                    model_payload["final_diagnosis"] = _reranked[0]
            if model_payload:
                _write_case_report(root / f"{case.case_id}.report.md", case, model_payload)
                trace.emit(
                    "answer",
                    "diagnostician",
                    _optional_str(model_payload, "final_diagnosis") or "(no diagnosis)",
                    summary=_optional_str(model_payload, "recommended_next_step"),
                    payload=model_payload,
                )
            elif error:
                trace.emit("error", "diagnostician", "Final answer failed", status="error", payload={"error": error})

        final = _optional_str(model_payload, "final_diagnosis") if model_payload else None
        _jc = judge_client if judge else None
        row = RetrievalGuidedEvalRow(
            case_id=case.case_id,
            preset=preset,
            expected_diagnosis=expected_diagnosis,
            model_final_diagnosis=final,
            query_count=len(queries),
            evidence_count=len([item for item in evidence if not item.excluded]),
            synthesis_path=synthesis_path_value,
            prompt_path=str(prompt_path),
            query_path=str(query_path),
            evidence_path=str(evidence_path),
            response_path=response_path_value,
            error=error,
            samples=samples,
            agreement=agreement,
            gold_rank=(
                _gold_rank(_ranked_diagnoses(model_payload), answer_key, judge_client=_jc, fallback_client=judge_fallback_client)
                if has_expected_answer
                else None
            ),
            **_score_fields(
                final,
                answer_key if has_expected_answer else None,
                judge_client=_jc,
                fallback_client=judge_fallback_client,
                model_call_recorder=record_model_call,
            ),
        )
        if has_expected_answer:
            trace.emit(
                "judge",
                "judge",
                f"Verdict: {row.score or row.lexical_score}",
                summary=row.judge_match_type,
                status="pass" if row.score == "pass" else "fail" if row.score == "fail" else "info",
                payload={
                    "score": row.score,
                    "score_method": row.score_method,
                    "judge_match_type": row.judge_match_type,
                    "judge_rationale": row.judge_rationale,
                    "expected_diagnosis": row.expected_diagnosis,
                    "model_final_diagnosis": row.model_final_diagnosis,
                    "lexical_score": row.lexical_score,
                    "agreement": row.agreement,
                    "samples": row.samples,
                },
            )
        trace.emit(
            "case_completed",
            "runner",
            "Case complete" if not row.error else "Case errored",
            status="error" if row.error else ("pass" if row.score == "pass" else "ok"),
            payload={"error": row.error},
        )
        if progress:
            status = "error" if error else (row.score or row.lexical_score)
            print(
                f"[{index}/{total}] completed status={status} evidence={row.evidence_count}",
                file=sys.stderr,
                flush=True,
            )
        return row

    def _safe_run_case(index: int, manifest_row: dict[str, Any]) -> RetrievalGuidedEvalRow:
        # Isolate per-case failures so one unhandled error (e.g. an exhausted-retry network fault)
        # does not abort the whole batch; it becomes an error row and the run continues.
        try:
            return _run_case(index, manifest_row)
        except Exception as exc:  # noqa: BLE001 - record and continue.
            case_id = str(manifest_row.get("case_id", "unknown"))
            try:
                expected = answer_key_from_manifest_row(manifest_row)["diagnosis"]
            except Exception:  # noqa: BLE001
                expected = ""
            if progress:
                print(f"[{index}/{total}] {case_id} ERRORED: {exc}", file=sys.stderr, flush=True)
            _write_error_case_trace(root / f"{case_id}.events.jsonl", run_id, case_id, str(exc), emitter)
            return RetrievalGuidedEvalRow(
                case_id=case_id,
                preset="error",
                expected_diagnosis=expected,
                model_final_diagnosis=None,
                lexical_score="not_run",
                query_count=0,
                evidence_count=0,
                synthesis_path=None,
                prompt_path="",
                query_path="",
                evidence_path="",
                response_path=None,
                error=str(exc),
            )

    if concurrency > 1 and total > 1:
        # Cases are independent, so evaluate them on a bounded thread pool. The work is I/O-bound
        # (NCBI + model HTTP), so threads suffice; the NCBI client serializes its own rate limit and
        # the model client retries on 429, keeping us within each backend's concurrency ceiling.
        ordered: list[RetrievalGuidedEvalRow | None] = [None] * total
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            future_to_index = {
                pool.submit(_safe_run_case, index, manifest_row): index - 1
                for index, manifest_row in enumerate(rows, start=1)
            }
            for future in as_completed(future_to_index):
                ordered[future_to_index[future]] = future.result()
        result_rows = [row for row in ordered if row is not None]
    else:
        result_rows = [_safe_run_case(index, manifest_row) for index, manifest_row in enumerate(rows, start=1)]
    write_retrieval_guided_results(root, tuple(result_rows))
    return tuple(result_rows)


def rerank_differential(
    model_client: OpenAICompatibleChatClient, *, case: ClinicalCase, candidates: list[str],
    evidence_summary: str = "",
    model_call_recorder: ModelCallRecorder | None = None,
) -> list[str]:
    """Re-rank a FIXED candidate list by case-specific discriminator match, not familiarity.

    The dominant residual failure is a ranking error: the gold is in the model's top-5 but a
    prototypical near-neighbor is ranked #1 (≈half the in-top-5 cases). This focused second pass forces
    the model to evaluate each candidate's single most DEFINING feature against the case and rank
    evidence-match over base-rate familiarity — promoting the entity whose discriminator is actually
    present. It may not add or drop candidates, so it cannot hallucinate a new answer.
    """
    if len(candidates) < 2:
        return candidates
    prompt = (
        "Re-rank this FIXED list of candidate diagnoses for the case. Do NOT add, drop, or rename any "
        "candidate. For EACH candidate, name its single most DEFINING/discriminating feature, then state "
        "whether that feature is PRESENT, ABSENT, or UNKNOWN in this case. Then rank so that candidates "
        "whose defining feature is PRESENT come first, ordered by strength of case-specific match — rank "
        "by how well the case's specific findings fit, NOT by how common or familiar the diagnosis is. "
        "A prototypical diagnosis whose defining feature is absent must drop below a rarer one whose "
        "defining feature is present.\n\n"
        'Return strict JSON: {"ranked": ["<verbatim candidate>", ...]} containing exactly the same '
        "candidates, reordered.\n\n"
        f"Case:\n{case.prompt}\n\n"
        + (f"Relevant evidence:\n{evidence_summary}\n\n" if evidence_summary else "")
        + f"Candidates (to reorder, verbatim):\n{json.dumps(candidates, ensure_ascii=False)}\n"
    )
    try:
        result = model_client.chat(prompt=prompt, temperature=0.0, max_tokens=4096)
        payload = parse_json_object(result.content)
        _record_model_call(
            model_call_recorder,
            stage="rerank_differential",
            actor="synthesizer",
            title="Rerank differential",
            prompt=prompt,
            result=result,
            parsed=payload,
            max_tokens=4096,
            temperature=0.0,
        )
    except Exception as exc:  # noqa: BLE001 - re-rank is best-effort; keep original order on failure.
        _record_model_call(
            model_call_recorder,
            stage="rerank_differential",
            actor="synthesizer",
            title="Rerank differential failed",
            prompt=prompt,
            error=str(exc),
            max_tokens=4096,
            temperature=0.0,
        )
        return candidates
    new = payload.get("ranked")
    if not isinstance(new, list):
        return candidates
    # Keep only original candidates (guard against drift), preserve any the model dropped, dedupe.
    lower = {c.lower(): c for c in candidates}
    seen: set[str] = set()
    out: list[str] = []
    for item in new:
        if isinstance(item, str) and item.lower() in lower and item.lower() not in seen:
            seen.add(item.lower())
            out.append(lower[item.lower()])
    for c in candidates:  # append any candidate the re-rank omitted, original order
        if c.lower() not in seen:
            out.append(c)
    return out


def _initial_clinical_assessment(
    model_client: OpenAICompatibleChatClient,
    case: ClinicalCase,
    preset: str,
    *,
    model_call_recorder: ModelCallRecorder | None = None,
) -> str:
    """One cheap Flash call producing the working differential + discriminators sought.

    This becomes the 'clinical reasoning so far' handed to every per-paper screener, so relevance is
    judged against THIS case's specific hypotheses, not the topic in general. Closed-book (no
    retrieval); it's a reasoning seed, not the answer.
    """
    prompt = (
        "You are forming an initial diagnostic assessment to GUIDE a literature search (not to finalize "
        "a diagnosis). From the case, give a concise working differential and what you need to resolve "
        "it. Plain text, <=200 words. Cover: problem representation (one line); top 4-6 candidate "
        "diagnoses spanning common AND can't-miss AND rarer mimics, each with the one feature for/against "
        "it; the specific discriminators or tests that would separate them; and any can't-miss entity to "
        "exclude. Do not commit to a single answer.\n\n"
        f"Case:\n{case.prompt}\n"
    )
    try:
        result = model_client.chat(prompt=prompt, temperature=0.0, max_tokens=4096)
        _record_model_call(
            model_call_recorder,
            stage="initial_clinical_assessment",
            actor="planner",
            title="Initial clinical assessment",
            prompt=prompt,
            result=result,
            max_tokens=4096,
            temperature=0.0,
        )
        return result.content.strip()[:2000]
    except Exception as exc:  # noqa: BLE001 - reasoning seed is best-effort; fall back to no extra context.
        _record_model_call(
            model_call_recorder,
            stage="initial_clinical_assessment",
            actor="planner",
            title="Initial clinical assessment failed",
            prompt=prompt,
            error=str(exc),
            max_tokens=4096,
            temperature=0.0,
        )
        return ""


def _generate_final_answer(
    model_client: OpenAICompatibleChatClient,
    *,
    prompt: str,
    case: ClinicalCase,
    preset: str,
    samples: int,
    sample_temperature: float,
    consensus_judge: OpenAICompatibleChatClient | None,
    model_call_recorder: ModelCallRecorder | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any], str | None, float | None]:
    """Run the final-answer model once, or k times for self-consistency.

    Returns (chosen_payload, response_payload_to_write, error, agreement). With samples>1 the k
    diagnoses are clustered (judge-based when a judge is available, else string-based) and the
    representative of the majority cluster is chosen; ``agreement`` is the winning-cluster fraction.
    """

    def _one(temperature: float, sample_index: int) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
        try:
            # Generous completion budget: reasoning models spend tokens on hidden reasoning before
            # emitting the answer JSON, and a too-small cap silently truncates to empty content
            # (finish_reason=length) on exactly the hardest cases, which would read as a wrong answer.
            result = model_client.chat(prompt=prompt, temperature=temperature, max_tokens=12000)
        except Exception as exc:
            _record_model_call(
                model_call_recorder,
                stage="final_answer",
                actor="diagnostician",
                title=f"Final answer sample {sample_index}",
                prompt=prompt,
                error=str(exc),
                max_tokens=12000,
                temperature=temperature,
            )
            return None, {"case_id": case.case_id, "preset": preset, "error": str(exc)}, str(exc)
        try:
            payload = parse_json_object(result.content)
        except Exception as exc:
            _record_model_call(
                model_call_recorder,
                stage="final_answer",
                actor="diagnostician",
                title=f"Final answer sample {sample_index}",
                prompt=prompt,
                result=result,
                error=f"model response was not valid JSON: {exc}",
                max_tokens=12000,
                temperature=temperature,
            )
            return None, {
                "case_id": case.case_id, "preset": preset, "model": result.model,
                "latency_ms": result.latency_ms, "error": f"model response was not valid JSON: {exc}",
                "raw_content": result.content, "raw": result.raw,
            }, f"model response was not valid JSON: {exc}"
        _record_model_call(
            model_call_recorder,
            stage="final_answer",
            actor="diagnostician",
            title=f"Final answer sample {sample_index}",
            prompt=prompt,
            result=result,
            parsed=payload,
            max_tokens=12000,
            temperature=temperature,
        )
        return payload, {
            "case_id": case.case_id, "preset": preset, "model": result.model,
            "latency_ms": result.latency_ms, "content": payload, "raw": result.raw,
        }, None

    if samples <= 1:
        payload, response_payload, error = _one(0.0, 1)
        return payload, response_payload, error, None

    sample_payloads: list[dict[str, Any] | None] = []
    sample_finals: list[str] = []
    last_error: str | None = None
    for sample_index in range(1, samples + 1):
        payload, _resp, err = _one(sample_temperature, sample_index)
        sample_payloads.append(payload)
        sample_finals.append((_optional_str(payload, "final_diagnosis") or "") if payload else "")
        if err:
            last_error = err
    if consensus_judge is not None:
        result = consensus_diagnosis_judged(
            sample_finals,
            consensus_judge,
            model_call_recorder=model_call_recorder,
        )
    else:
        result = consensus_diagnosis(sample_finals)
    # Choose the payload whose final_diagnosis is the consensus representative.
    chosen_payload: dict[str, Any] | None = None
    if result.consensus is not None:
        for payload, final in zip(sample_payloads, sample_finals):
            if payload is not None and final == result.consensus:
                chosen_payload = payload
                break
    error = None if chosen_payload is not None else (last_error or "all answer samples failed")
    response_payload = {
        "case_id": case.case_id,
        "preset": preset,
        "self_consistency": {
            "samples": samples,
            "sample_temperature": sample_temperature,
            "agreement": result.agreement,
            "cluster_size": result.cluster_size,
            "sample_final_diagnoses": list(result.all_diagnoses),
            "consensus": result.consensus,
            "clustering": "judge" if consensus_judge is not None else "string",
        },
        "content": chosen_payload,
        "error": error,
    }
    return chosen_payload, response_payload, error, result.agreement


def _score_fields(
    final: str | None,
    answer_key: dict[str, Any] | None,
    *,
    judge_client: OpenAICompatibleChatClient | None,
    fallback_client: OpenAICompatibleChatClient | None = None,
    model_call_recorder: ModelCallRecorder | None = None,
) -> dict[str, Any]:
    """Compute lexical and (optional) judge verdicts for one final diagnosis."""

    if answer_key is None:
        return {
            "lexical_score": "not_run",
            "score": None,
            "score_method": None,
            "judge_match_type": None,
            "judge_rationale": None,
        }
    aliases = tuple(answer_key.get("aliases", ()) or ())
    lexical = lexical_score(final or "", answer_key)
    verdict: JudgeVerdict = score_diagnosis(
        candidate=final,
        expected=answer_key["diagnosis"],
        aliases=aliases,
        judge_client=judge_client,
        fallback_client=fallback_client,
        model_call_recorder=model_call_recorder,
    )
    return {
        "lexical_score": lexical,
        "score": verdict.score,
        "score_method": verdict.method,
        "judge_match_type": verdict.match_type,
        "judge_rationale": verdict.rationale,
    }


def _has_expected_answer(answer_key: dict[str, Any], manifest_row: dict[str, Any]) -> bool:
    metadata = manifest_row.get("metadata")
    if isinstance(metadata, dict) and metadata.get("correct_answer_provided") is False:
        return False
    diagnosis = answer_key.get("diagnosis")
    return isinstance(diagnosis, str) and diagnosis.strip() not in {"", "unknown"}


def _ranked_diagnoses(model_payload: dict[str, Any] | None, *, limit: int = 5) -> list[str]:
    """Extract the model's ranked differential (top entries), newest schema first.

    Falls back to [final_diagnosis] for older responses that predate ranked_differential.
    """
    if not model_payload:
        return []
    ranked = model_payload.get("ranked_differential")
    out: list[str] = []
    if isinstance(ranked, list):
        for item in ranked:
            dx = item.get("diagnosis") if isinstance(item, dict) else (item if isinstance(item, str) else None)
            if isinstance(dx, str) and dx.strip():
                out.append(dx.strip())
    if not out:
        final = _optional_str(model_payload, "final_diagnosis")
        if final:
            out = [final]
    return out[:limit]


_CONJUNCTION_RE = re.compile(r"\b(?:comorbid|coexist\w*|co-existing|overlapping|overlap|concurrent)\b", re.I)
_CONJUNCTION_SPLIT = re.compile(r"\s+and\s+|;\s*|\s+\+\s+|\s+with (?:underlying|coexisting|concurrent)\s+", re.I)


def _gold_components(gold: str) -> list[str]:
    """Split a comorbidity gold ('comorbid A and B', 'A coexisting with B', 'A + B overlap') into its
    component diagnoses. Returns [] when it is a single entity.

    Requires an EXPLICIT comorbidity keyword (comorbid/coexist/overlap/concurrent) — NOT a bare 'and',
    because many single diagnoses contain 'and' ('developmental and epileptic encephalopathy'). The
    caller treats the components as ADDITIVE credit, never a penalty (see _gold_rank)."""
    if not _CONJUNCTION_RE.search(gold):
        return []
    stem = _CONJUNCTION_RE.sub("", gold)  # drop the connective words
    parts = [p.strip(" ,:;()").strip() for p in _CONJUNCTION_SPLIT.split(stem)]
    parts = [p for p in parts if len(p) >= 6]
    return parts if len(parts) >= 2 else []


def _gold_rank(
    ranked: list[str],
    answer_key: dict[str, Any],
    *,
    judge_client: OpenAICompatibleChatClient | None,
    fallback_client: OpenAICompatibleChatClient | None = None,
) -> int | None:
    """1-based rank at which the gold is satisfied within the ranked top-5 (else None).

    For a single-entity gold: the rank of the first matching candidate. For a CONJUNCTION/comorbidity
    gold ('A and B'): the rank by which ALL components have appeared (a comorbidity is 'found' only when
    every coexisting condition is in the differential — the model usually lists them separately). This
    credits what the model actually produced; pass@k = gold_rank <= k.
    """
    aliases = tuple(answer_key.get("aliases", ()) or ())
    gold = answer_key["diagnosis"]

    def first_match_rank(expected: str, alias: tuple[str, ...]) -> int | None:
        for index, dx in enumerate(ranked, start=1):
            if score_diagnosis(candidate=dx, expected=expected, aliases=alias,
                               judge_client=judge_client, fallback_client=fallback_client).score == "pass":
                return index
        return None

    # Primary: does a single ranked candidate match the whole gold? (original behavior)
    single = first_match_rank(gold, aliases)
    # ADDITIVE comorbidity credit: if the gold is a conjunction and the model listed every component
    # separately, it is 'found' at the rank by which all components appear. Take the BETTER of the two
    # so this can only help, never lower a score.
    components = _gold_components(gold)
    if len(components) >= 2:
        comp_ranks = [first_match_rank(c, ()) for c in components]
        if all(r is not None for r in comp_ranks):
            conj = max(comp_ranks)
            return conj if single is None else min(single, conj)
    return single


def build_retrieval_queries(
    case: ClinicalCase,
    *,
    preset: str,
    max_queries: int = 2,
    round_index: int = 1,
    previous_queries: tuple[str, ...] = (),
    evidence: tuple[RetrievalEvidence, ...] = (),
    synthesis: EvidenceSynthesis | None = None,
    config: HarnessConfig = HarnessConfig(),
) -> tuple[RetrievalQuery, ...]:
    themes = QUERY_THEMES_BY_PRESET.get(preset) or QUERY_THEMES_BY_PRESET["general"]
    if round_index == 1:
        contrast = _anchor_contrast_query(preset, case) if config.use_contrast_queries else None
        themes = (*build_case_feature_queries(case, preset=preset), *((contrast,) if contrast else ()), *themes)
    else:
        themes = (*build_followup_queries(case, preset=preset, evidence=evidence, synthesis=synthesis), *themes)
    seen = set(previous_queries)
    safe_queries: list[RetrievalQuery] = []
    for index, theme in enumerate(themes, start=1):
        query = _sanitize_query(theme)
        if not query or query in seen:
            continue
        if config.eval_mode and _query_hits_source_shortcut(case, query):
            continue
        seen.add(query)
        safe_queries.append(
            RetrievalQuery(
                query_id=f"r{round_index}q{len(safe_queries) + 1}",
                query=query,
                source="pubmed",
                intent="retrieve diagnostic discriminators without source-title or case-text shortcuts",
                round_index=round_index,
                generated_by="case_feature" if round_index == 1 and index <= len(build_case_feature_queries(case, preset=preset)) else "preset_template",
            )
        )
        if len(safe_queries) >= max_queries:
            break
    if not safe_queries:
        safe_queries.append(
            RetrievalQuery(
                query_id=f"r{round_index}q1",
                query="diagnostic criteria differential diagnosis review",
                source="pubmed",
                intent="fallback broad discriminator retrieval",
                round_index=round_index,
                generated_by="fallback",
            )
        )
    return tuple(safe_queries)


# Generic disease-type words in mimic names that don't make a mimic "supported by the case."
_GENERIC_MIMIC_TOKENS = frozenset(
    {"psychosis", "encephalitis", "encephalopathy", "receptor", "antibody", "autoimmune",
     "carcinoma", "tumor", "tumour", "infection", "disorder", "disease", "lesion", "mass"}
)


def _anchor_contrast_query(preset: str, case: ClinicalCase | None = None) -> str | None:
    """A discriminator-seeking query that names BOTH sides of the preset mimic pair.

    Single-sided preset themes can bias retrieval toward whichever mimic is named (the
    failure seen when 'AML eosinophilia inv(16)' pulled only inv(16) evidence). Naming
    both anchors recovers symmetric, discriminator-focused articles.

    ADR-035: a fixed preset mimic pair is a NICHE injection and must be inert when the case does not
    support it — otherwise it steers retrieval toward an irrelevant mimic for every member of the
    preset family (the NPSLE-for-every-neuro_psych-case failure). When a case is given, emit the
    contrast query only if a distinctive (non-generic) token from the mimic pair appears in the case.
    """

    pair = ANCHOR_MIMIC_PAIRS_BY_PRESET.get(preset)
    if not pair or len(pair) < 2:
        return None
    # Skip placeholder pairs (e.g. "case-specific species", "generic sarcoma"): a contrast
    # query is only useful when both sides name concrete entities to retrieve discriminators for.
    placeholder_markers = ("case-specific", "familiar", "generic", "organ-specific", "another", "sibling")
    if any(marker in side.lower() for side in pair[:2] for marker in placeholder_markers):
        return None
    if case is not None:
        distinctive = _meaningful_term_set(" ".join(pair[:2])) - _GENERIC_MIMIC_TOKENS
        if distinctive and not (distinctive & _meaningful_term_set(case.prompt)):
            return None  # the case raises neither mimic — do not anchor retrieval on it
    # Strip parenthetical clarifications to keep the query lean.
    sides = [re.sub(r"\([^)]*\)", "", side).strip() for side in pair[:2]]
    return _sanitize_query(f"{sides[0]} versus {sides[1]} differential discriminating features")


def _distinctive_symptoms(symptoms: list[str], limit: int = 5) -> list[str]:
    """Order presenting features by specificity (multi-word, distinctive phrases first) and drop
    terms that are substrings of a more specific one ('hallucinations' if 'auditory hallucinations'
    is present; 'hearing loss' if 'sensorineural hearing loss' is present). This keeps the
    discriminating feature in the query instead of crowding it out with common synonyms."""
    kept: list[str] = []
    for s in sorted(symptoms, key=lambda t: len(t.split()), reverse=True):
        if any(s in k and s != k for k in kept):
            continue
        kept.append(s)
    return kept[:limit]


def build_case_feature_queries(case: ClinicalCase, *, preset: str) -> tuple[str, ...]:
    prompt = case.prompt
    features = extract_case_features(prompt)
    queries: list[str] = []
    if preset in {"spindle_cell_pathology", "renal_spindle_cell_mass", "pathology"}:
        marker_part = " ".join(features["markers"][:6])
        organ_part = " ".join(features["organs"][:2])
        morphology = " ".join(features["morphology"][:3]) or "spindle cell"
        queries.append(_sanitize_query(f"{organ_part} {morphology} {marker_part} immunohistochemistry differential"))
    elif preset in {"mold_identification", "infection_microbiology"}:
        organism_part = " ".join(features["organisms"][:4])
        site_part = " ".join(features["organs"][:2])
        if organism_part:
            queries.append(_sanitize_query(f"{organism_part} {site_part} identification susceptibility infection"))
        queries.append(_sanitize_query(f"{site_part} culture negative infection pathogen differential PCR culture"))
    elif preset in {"demyelination", "neuroinflammatory_demyelination"}:
        antibody_part = " ".join(features["antibodies"][:4])
        queries.append(_sanitize_query(f"{antibody_part} oligoclonal bands MRI lesion distribution demyelination differential"))
    elif preset == "neuro_psych":
        # Case-derived, NOT hard-coded (ADR-035): query the patient's actual presenting features so
        # retrieval fetches the literature that names THIS case's answer, not a fixed mimic (NPSLE).
        symptom_part = " ".join(_distinctive_symptoms(features["symptoms"]))
        if symptom_part:
            queries.append(_sanitize_query(f"{symptom_part} differential diagnosis"))
            queries.append(_sanitize_query(f"{symptom_part} organic cause workup"))
    elif preset == "prion_sleep":
        queries.append("sporadic fatal insomnia iatrogenic CJD differential insomnia dysautonomia thalamus")
    elif preset == "adverse_drug_event":
        drug_part = " ".join(features["drugs"][:4])
        queries.append(_sanitize_query(f"{drug_part} erythema multiforme adverse reaction dechallenge rechallenge"))
    elif preset == "hematologic_cytogenetic_subtype":
        cytogenetic_part = " ".join(features["cytogenetics"][:4])
        queries.append(_sanitize_query(f"{cytogenetic_part} AML t(8;21) inv(16) eosinophilia Auer rods dysplasia cytogenetic subtype"))
    elif preset == "colonization_vs_infection":
        organism_part = " ".join(features["organisms"][:4])
        queries.append(_sanitize_query(f"{organism_part} colonization contamination infection criteria"))
        queries.append(_sanitize_query(f"{organism_part} species identification lipid dependent non-lipid-dependent morphology"))
    elif preset == "prior_cancer_mass":
        cancer_part = " ".join(features["cancers"][:3])
        organ_part = " ".join(features["organs"][:2])
        queries.append(_sanitize_query(f"{cancer_part} {organ_part} metastasis soft tissue mass immunohistochemistry"))
    elif preset == "sequential_event":
        organ_part = " ".join(features["organs"][:2])
        morphology = " ".join(features["morphology"][:2])
        queries.append(_sanitize_query(f"{organ_part} {morphology} recurrent mass tissue biopsy diagnosis"))
    elif preset == "infection_microbiology":
        site_part = " ".join(features["organs"][:2])
        queries.append(_sanitize_query(f"{site_part} actinomycosis sulfur granules filamentous gram positive culture negative abscess"))
    elif preset == "renal_spindle_cell_mass":
        queries.append("renal spindle cell mass neurofibroma schwannoma S100 SOX10 benign neural tumor versus sarcomatoid")
    elif preset == "neuroinflammatory_demyelination":
        antibody_part = " ".join(features["antibodies"][:4])
        queries.append(_sanitize_query(f"{antibody_part} area postrema syndrome longitudinally extensive myelitis AQP4 NMOSD MOGAD cell based assay"))
    # Generic fallback: if no preset-specific query was built, query the case's own salient
    # presenting features rather than nothing (keeps retrieval case-anchored, never preset-biased).
    if not queries and features["symptoms"]:
        symptom_part = " ".join(_distinctive_symptoms(features["symptoms"]))
        queries.append(_sanitize_query(f"{symptom_part} differential diagnosis"))
    return tuple(query for query in queries if query)


def build_followup_queries(
    case: ClinicalCase,
    *,
    preset: str,
    evidence: tuple[RetrievalEvidence, ...],
    synthesis: EvidenceSynthesis | None,
) -> tuple[str, ...]:
    if synthesis and synthesis.additional_queries:
        return synthesis.additional_queries
    features = extract_case_features(case.prompt)
    queries: list[str] = []
    if preset == "spindle_cell_pathology":
        organs = " ".join(features["organs"][:2])
        queries.append(_sanitize_query(f"{organs} sarcomatoid carcinoma carcinosarcoma leiomyosarcoma angiosarcoma IHC"))
    elif preset == "mold_identification":
        organisms = " ".join(features["organisms"][:4]) or "Magnusiomyces Saprochaete Microascus Scopulariopsis"
        queries.append(_sanitize_query(f"{organisms} morphology sequencing susceptibility invasive infection"))
    elif preset == "demyelination":
        queries.append("pediatric multiple sclerosis MOGAD false positive oligoclonal bands silent MRI lesions")
    elif preset == "neuro_psych":
        queries.append("NPSLE psychosis anti ribosomal P CSF MRI anti NMDA discriminator")
    elif preset == "bone_vascular_tumor":
        queries.append("intraosseous angiosarcoma secondary aneurysmal bone cyst CD31 ERG FLI1")
    elif preset == "prion_sleep":
        queries.append("sporadic fatal insomnia iatrogenic CJD exposure incubation phenotype differential")
    elif preset == "adverse_drug_event":
        drugs = " ".join(features["drugs"][:4])
        queries.append(_sanitize_query(f"{drugs} arsenic trioxide ATRA erythema multiforme causality"))
    elif preset == "sequential_event":
        queries.append("cardiac angiosarcoma atrial myxoma mimic recurrent mass biopsy diagnosis")
    return tuple(query for query in queries if query)


def collect_pubmed_evidence(
    client: NcbiClient,
    case: ClinicalCase,
    *,
    queries: tuple[RetrievalQuery, ...],
    articles_per_query: int,
    seen_pmids: set[str] | None = None,
    preset: str = "general",
    anchor_terms: frozenset[str] | None = None,
    config: HarnessConfig = HarnessConfig(),
    tool_call_recorder: ToolCallRecorder | None = None,
) -> tuple[RetrievalEvidence, ...]:
    records: list[RetrievalEvidence] = []
    seen_pmids = set(seen_pmids or set())
    if anchor_terms is None:
        anchor_terms = case_anchor_terms(case, preset)
    for query in queries:
        result = pubmed_search(client, query.query, limit=articles_per_query, sort="relevance")
        articles = result.get("articles", [])
        selected_result = result
        selected_query_text = query.query
        attempt = "initial"
        # Re-query when the first pass returns nothing OR (with the relevance filter on) returns
        # only off-topic hits. Generic preset themes can pull unrelated methodology papers; a
        # broadened case-feature query recovers signal.
        only_offtopic = config.use_relevance_filter and not any(
            _article_relevance(article, anchor_terms) for article in articles
        )
        if not articles or only_offtopic:
            _record_pubmed_tool_call(
                tool_call_recorder,
                query=query,
                attempted_query=query.query,
                result=result,
                articles=articles,
                articles_per_query=articles_per_query,
                attempt=attempt,
                reason="no_results" if not articles else "only_offtopic",
                output_evidence_ids=(),
            )
            # Progressive broadening: first the targeted broadener, then a minimal 2-term fallback.
            # A query that still returns nothing after broadening was over-specified (PubMed ANDs all
            # terms); shrinking the term set recovers signal rather than yielding an empty round.
            for broadened_query in (_broaden_query(query.query), _minimal_query(query.query)):
                if broadened_query == query.query:
                    continue
                broadened = pubmed_search(client, broadened_query, limit=articles_per_query, sort="relevance")
                broadened_articles = broadened.get("articles", [])
                if broadened_articles:
                    articles = broadened_articles
                    selected_result = broadened
                    selected_query_text = broadened_query
                    attempt = "broadened"
                    break
                _record_pubmed_tool_call(
                    tool_call_recorder,
                    query=query,
                    attempted_query=broadened_query,
                    result=broadened,
                    articles=broadened_articles,
                    articles_per_query=articles_per_query,
                    attempt="broadened",
                    reason="retry_after_empty_or_offtopic",
                    output_evidence_ids=(),
                )
        output_ids: list[str] = []
        for rank, article in enumerate(articles, start=1):
            pmid = _optional_str(article, "pmid")
            if pmid and pmid in seen_pmids:
                continue
            if pmid:
                seen_pmids.add(pmid)
            excluded, reason = source_exclusion_decision(case, article, eval_mode=config.eval_mode)
            evidence_id = f"pubmed:{pmid or query.query_id + ':' + str(rank)}"
            output_ids.append(evidence_id)
            records.append(
                RetrievalEvidence(
                    evidence_id=evidence_id,
                    query_id=query.query_id,
                    rank=rank,
                    pmid=pmid,
                    pmcid=_optional_str(article, "pmcid"),
                    doi=_optional_str(article, "doi"),
                    title=_optional_str(article, "title"),
                    journal=_optional_str(article, "journal"),
                    publication_year=_optional_str(article, "publication_year"),
                    publication_types=tuple(
                        item for item in article.get("publication_types", []) if isinstance(item, str)
                    ),
                    url=_optional_str(article, "url"),
                    abstract_snippet=_clip(_optional_str(article, "abstract"), 900),
                    excluded=excluded,
                    exclusion_reason=reason,
                    relevance=_article_relevance(article, anchor_terms),
                )
            )
        if articles:
            _record_pubmed_tool_call(
                tool_call_recorder,
                query=query,
                attempted_query=selected_query_text,
                result=selected_result,
                articles=articles,
                articles_per_query=articles_per_query,
                attempt=attempt,
                reason="selected_results",
                output_evidence_ids=tuple(output_ids),
            )
    return tuple(records)


# Tokens that carry no diagnostic signal for relevance overlap.
_RELEVANCE_STOPWORDS = frozenset(
    {
        "and", "or", "the", "with", "without", "versus", "vs", "differential", "diagnosis",
        "diagnostic", "criteria", "review", "case", "report", "reports", "study", "studies",
        "patient", "patients", "clinical", "disease", "syndrome", "analysis", "novel", "rare",
        "new", "for", "from", "due", "associated", "type", "using", "based", "role", "via",
        "of", "in", "on", "an", "as", "to", "by", "a", "is", "are",
    }
)


def _meaningful_term_set(text: str | None) -> frozenset[str]:
    if not text:
        return frozenset()
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return frozenset(token for token in tokens if len(token) > 2 and token not in _RELEVANCE_STOPWORDS)


def case_anchor_terms(case: ClinicalCase, preset: str) -> frozenset[str]:
    """Diagnostic vocabulary expected in on-topic evidence for this case/preset.

    Built from extracted case features, the preset query themes, and the preset anchor
    mimic pair. Used to filter obviously off-topic retrieved articles.
    """

    terms: set[str] = set()
    features = extract_case_features(case.prompt)
    for values in features.values():
        for value in values:
            terms |= _meaningful_term_set(value)
    for theme in QUERY_THEMES_BY_PRESET.get(preset, ()):
        terms |= _meaningful_term_set(theme)
    for entity in ANCHOR_MIMIC_PAIRS_BY_PRESET.get(preset, ()):
        terms |= _meaningful_term_set(entity)
    return frozenset(terms)


def _article_relevance(article: dict[str, Any], anchor_terms: frozenset[str]) -> int:
    if not anchor_terms:
        return 1
    text_terms = _meaningful_term_set(_optional_str(article, "title")) | _meaningful_term_set(
        _clip(_optional_str(article, "abstract"), 400)
    )
    return len(text_terms & anchor_terms)


def enrich_evidence_with_full_text(
    client: NcbiClient,
    case: ClinicalCase,
    *,
    evidence: tuple[RetrievalEvidence, ...],
    max_articles: int = 2,
    tool_call_recorder: ToolCallRecorder | None = None,
) -> tuple[RetrievalEvidence, ...]:
    pmcids = [item.pmcid for item in evidence if item.pmcid and not item.excluded][:max_articles]
    if not pmcids:
        return evidence
    articles = fetch_pmc_articles(client, pmcids)
    articles_by_pmcid = {article.pmcid: article for article in articles}
    output_evidence_ids: list[str] = []
    enriched: list[RetrievalEvidence] = []
    for item in evidence:
        article = articles_by_pmcid.get(item.pmcid or "")
        if article is None:
            enriched.append(item)
            continue
        excluded, reason = source_exclusion_decision(case, article.to_dict())
        snippet = _clip(_best_full_text_snippet(article.to_dict()), 1600)
        if snippet:
            output_evidence_ids.append(item.evidence_id)
        enriched.append(
            RetrievalEvidence(
                evidence_id=item.evidence_id,
                query_id=item.query_id,
                rank=item.rank,
                pmid=item.pmid,
                pmcid=item.pmcid,
                doi=item.doi,
                title=item.title,
                journal=item.journal,
                publication_year=item.publication_year,
                publication_types=item.publication_types,
                url=item.url,
                abstract_snippet=item.abstract_snippet,
                source_api=item.source_api,
                source_scope="full_text" if snippet else item.source_scope,
                full_text_snippet=snippet,
                excluded=item.excluded or excluded,
                exclusion_reason=item.exclusion_reason or reason,
            )
        )
    _record_pmc_fetch_tool_call(
        tool_call_recorder,
        pmcids=tuple(pmcids),
        articles=[article.to_dict() for article in articles],
        output_evidence_ids=tuple(output_evidence_ids),
    )
    return tuple(enriched)


def deterministic_evidence_synthesis(
    case: ClinicalCase,
    *,
    preset: str,
    evidence: tuple[RetrievalEvidence, ...],
    round_index: int,
    config: HarnessConfig = HarnessConfig(),
) -> EvidenceSynthesis:
    included = _ranked_relevant_evidence(evidence, config)
    additional_queries = build_followup_queries(case, preset=preset, evidence=evidence, synthesis=None)
    anchor_risks = ANCHOR_RISKS_BY_PRESET.get(preset, ()) if config.use_gates else ()
    discriminators = []
    for item in included[:6]:
        discriminators.append(
            {
                "evidence_id": item.evidence_id,
                "source_scope": item.source_scope,
                "discriminator": _clip(item.title, 140) or item.evidence_id,
                "supports_or_refutes": "review for discriminator extraction",
            }
        )
    return EvidenceSynthesis(
        case_id=case.case_id,
        preset=preset,
        synthesis_round=round_index,
        useful_discriminators=tuple(discriminators),
        top_mimic_pair=ANCHOR_MIMIC_PAIRS_BY_PRESET.get(preset, ()) if config.use_gates else (),
        anchor_risks=anchor_risks,
        additional_queries=additional_queries,
        need_full_text_evidence_ids=tuple(item.evidence_id for item in included if item.pmcid and item.source_scope != "full_text")[:2],
        more_retrieval_needed=bool(additional_queries) and round_index == 1,
        notes=("deterministic synthesis; no model distiller was used",),
    )


def distill_retrieved_evidence(
    client: OpenAICompatibleChatClient,
    case: ClinicalCase,
    *,
    preset: str,
    evidence: tuple[RetrievalEvidence, ...],
    round_index: int,
    config: HarnessConfig = HarnessConfig(),
    model_call_recorder: ModelCallRecorder | None = None,
) -> EvidenceSynthesis:
    prompt = build_evidence_distillation_prompt(
        case, preset=preset, evidence=evidence, round_index=round_index, config=config
    )
    try:
        result = client.chat(prompt=prompt, max_tokens=3072)
        payload = parse_json_object(result.content)
        _record_model_call(
            model_call_recorder,
            stage="evidence_distillation",
            actor="synthesizer",
            title=f"Evidence distillation · round {round_index}",
            round_index=round_index,
            prompt=prompt,
            result=result,
            parsed=payload,
            max_tokens=3072,
        )
    except Exception as exc:
        _record_model_call(
            model_call_recorder,
            stage="evidence_distillation",
            actor="synthesizer",
            title=f"Evidence distillation failed · round {round_index}",
            round_index=round_index,
            prompt=prompt,
            error=str(exc),
            max_tokens=3072,
        )
        fallback = deterministic_evidence_synthesis(
            case, preset=preset, evidence=evidence, round_index=round_index, config=config
        )
        return EvidenceSynthesis(
            case_id=fallback.case_id,
            preset=fallback.preset,
            synthesis_round=fallback.synthesis_round,
            useful_discriminators=fallback.useful_discriminators,
            top_mimic_pair=fallback.top_mimic_pair,
            anchor_risks=fallback.anchor_risks,
            additional_queries=fallback.additional_queries,
            need_full_text_evidence_ids=fallback.need_full_text_evidence_ids,
            more_retrieval_needed=fallback.more_retrieval_needed,
            differential_resolved=fallback.differential_resolved,
            remaining_uncertainty=fallback.remaining_uncertainty,
            notes=(*fallback.notes, f"model distillation failed; used deterministic fallback: {exc}"),
        )
    return evidence_synthesis_from_payload(case, preset=preset, round_index=round_index, payload=payload)


def build_evidence_distillation_prompt(
    case: ClinicalCase,
    *,
    preset: str,
    evidence: tuple[RetrievalEvidence, ...],
    round_index: int,
    config: HarnessConfig = HarnessConfig(),
) -> str:
    included = _ranked_relevant_evidence(evidence, config)
    evidence_payload = [
        {
            "evidence_id": item.evidence_id,
            "title": item.title,
            "source_scope": item.source_scope,
            "abstract_snippet": item.abstract_snippet,
            "full_text_snippet": item.full_text_snippet,
        }
        for item in included[:10]
    ]
    payload = {
        "case_id": _model_visible_case_id(case.case_id),
        "harness_preset": preset,
        "round_index": round_index,
        "blocked_shortcuts": redacted_blocked_shortcuts(case),
        "case_prompt": case.prompt,
        "preset_checklist": list(PRESET_CHECKLISTS[preset]),
        "finalization_gates": finalization_gates_for(preset, config),
        "retrieved_evidence": evidence_payload,
    }
    return (
        "You are an evidence-distillation subagent inside ClinicalHarness. Extract only clinically relevant "
        "diagnostic discriminators from retrieved biomedical sources. Do not diagnose the case directly. Do not "
        "use source-title, DOI, PMCID, PMID, exact prompt text, or hidden chain-of-thought.\n\n"
        "Return strict JSON with:\n"
        "{\n"
        '  "useful_discriminators": [{"evidence_id": "...", "entity": "...", "supports": [], "refutes": [], "required_test_or_marker": "..."}],\n'
        '  "top_mimic_pair": ["...", "..."],\n'
        '  "anchor_risks": ["..."],\n'
        '  "additional_queries": ["..."],\n'
        '  "need_full_text_evidence_ids": ["..."],\n'
        '  "differential_resolved": true,\n'
        '  "remaining_uncertainty": ["..."],\n'
        '  "more_retrieval_needed": false,\n'
        '  "notes": ["..."]\n'
        "}\n\n"
        "Sufficiency judgment (this drives whether another retrieval round runs):\n"
        "- Ask yourself: with the evidence gathered so far, can a careful clinician CONFIDENTLY "
        "discriminate the lead diagnosis from its closest mimic in top_mimic_pair, and satisfy the "
        "preset finalization gates?\n"
        "- If yes, set differential_resolved=true, more_retrieval_needed=false, remaining_uncertainty=[].\n"
        "- If no, set differential_resolved=false and more_retrieval_needed=true, list the SPECIFIC "
        "remaining_uncertainty items (the discriminators/tests still missing), and put NEW, specific "
        "additional_queries that would resolve them (do not repeat queries already run). Only request "
        "more retrieval when a concrete, answerable gap remains — not for open-ended reassurance.\n\n"
        f"Distillation packet:\n{json.dumps(payload, indent=2, sort_keys=True)}\n"
    )


def evidence_synthesis_from_payload(
    case: ClinicalCase,
    *,
    preset: str,
    round_index: int,
    payload: dict[str, Any],
) -> EvidenceSynthesis:
    return EvidenceSynthesis(
        case_id=case.case_id,
        preset=preset,
        synthesis_round=round_index,
        useful_discriminators=tuple(_dict_items(payload.get("useful_discriminators"))),
        top_mimic_pair=tuple(_str_items(payload.get("top_mimic_pair")))[:2],
        anchor_risks=tuple(_str_items(payload.get("anchor_risks"))),
        additional_queries=tuple(_str_items(payload.get("additional_queries")))[:4],
        need_full_text_evidence_ids=tuple(_str_items(payload.get("need_full_text_evidence_ids")))[:4],
        more_retrieval_needed=bool(payload.get("more_retrieval_needed")),
        differential_resolved=bool(payload.get("differential_resolved")),
        remaining_uncertainty=tuple(_str_items(payload.get("remaining_uncertainty")))[:6],
        notes=tuple(_str_items(payload.get("notes"))),
    )


def _normalized_query_set(queries: tuple[str, ...] | set[str]) -> set[str]:
    return {" ".join(q.lower().split()) for q in queries if q and q.strip()}


def should_run_another_round(
    *,
    preset: str,
    round_index: int,
    max_rounds: int,
    evidence: tuple[RetrievalEvidence, ...],
    synthesis: EvidenceSynthesis,
    previous_queries: tuple[str, ...] | set[str] = (),
    config: HarnessConfig = HarnessConfig(),
) -> bool:
    """Decide whether to retrieve again.

    ``max_rounds`` is a hard safety cap and ``config.min_rounds`` a floor. Between them, when
    ``config.adaptive_rounds`` is on, the distillation subagent's own sufficiency judgment drives
    continuation: it runs another round only when it reports the differential is unresolved AND
    proposes at least one genuinely NEW query (a convergence guard so it cannot loop forever asking
    for evidence it already retrieved). With ``adaptive_rounds`` off, the original fixed-round
    heuristic is preserved for reproducible ablations.
    """

    if round_index >= max_rounds:  # hard cap always wins
        return False
    if round_index < max(1, config.min_rounds):  # floor: always do at least min_rounds
        return True
    included_count = len([item for item in evidence if not item.excluded])

    if not config.adaptive_rounds:
        # Legacy fixed-round behavior.
        if included_count < 4:
            return True
        if synthesis.more_retrieval_needed and synthesis.additional_queries:
            return True
        return preset in COMPLEX_PRESETS_REQUIRING_SECOND_LOOK and round_index == 1

    # Adaptive: trust the agent's sufficiency judgment, but only act on a concrete, new gap.
    if synthesis.differential_resolved and included_count >= 4:
        return False
    if included_count < 4:
        return True  # too little to judge anything yet
    if synthesis.more_retrieval_needed:
        already_run = _normalized_query_set(previous_queries)
        new_queries = _normalized_query_set(synthesis.additional_queries) - already_run
        if new_queries:  # a genuinely new, answerable gap remains
            return True
    return False


def source_exclusion_decision(
    case: ClinicalCase, article: dict[str, Any], *, eval_mode: bool = True
) -> tuple[bool, str | None]:
    # Doctor-assist mode (eval_mode off): never exclude — reading the actual source case report is
    # legitimate. Eval mode (benchmarking): exclude the source paper so the harness cannot cheat.
    if not eval_mode:
        return False, None
    exclusion = case.source_exclusion()
    source_pmcid = _normalize_identifier(_optional_str(exclusion, "pmcid"))
    source_doi = _normalize_identifier(_optional_str(exclusion, "doi"))
    source_title = _normalize_title(_optional_str(exclusion, "title"))
    article_pmcid = _normalize_identifier(_optional_str(article, "pmcid"))
    article_doi = _normalize_identifier(_optional_str(article, "doi"))
    article_title = _normalize_title(_optional_str(article, "title"))
    if source_pmcid and article_pmcid and source_pmcid == article_pmcid:
        return True, "source_pmcid_match"
    if source_doi and article_doi and source_doi == article_doi:
        return True, "source_doi_match"
    if source_title and article_title and source_title == article_title:
        return True, "source_title_match"
    return False, None


def build_retrieval_guided_final_prompt(
    case: ClinicalCase,
    *,
    preset: str,
    evidence: tuple[RetrievalEvidence, ...],
    syntheses: tuple[EvidenceSynthesis, ...] = (),
    max_rounds: int = 1,
    config: HarnessConfig = HarnessConfig(),
    paper_analyses: tuple = (),
) -> str:
    included = _ranked_relevant_evidence(evidence, config)
    # When per-paper extraction ran (ADR-040), the screened distilled notes replace raw abstracts as
    # the primary evidence — they are compact, so we can carry many more (decoupling papers-screened
    # from context-used) and raw abstracts shrink to a small backstop.
    # AUGMENT, do not flood (2026-06-15 finding): a large flat list of distilled notes DILUTES the
    # decisive signal and pushes the model to hedge generic. Feed only the few most-decisive screened
    # notes (those that actually name supports/refutes/discriminators), ranked, and KEEP the full raw
    # abstract set — extraction supplements, it does not displace.
    _decisive = sorted(
        (a for a in paper_analyses if getattr(a, "relevant", False)),
        key=lambda a: len(a.discriminators) + len(a.supports) + len(a.refutes) + (1 if a.new_entity else 0),
        reverse=True,
    )
    screened_payload = [
        {"evidence_id": a.evidence_id, "title": a.title, "pmid": a.pmid,
         "relevant_excerpt": a.relevant_excerpt, "discriminators": list(a.discriminators),
         "supports": list(a.supports), "refutes": list(a.refutes), "new_entity": a.new_entity}
        for a in _decisive[:5]
    ]
    raw_cap = 8
    evidence_payload = [
        {
            "evidence_id": item.evidence_id,
            "title": item.title,
            "pmid": item.pmid,
            "pmcid": item.pmcid,
            "doi": item.doi,
            "journal": item.journal,
            "year": item.publication_year,
            "publication_types": list(item.publication_types),
            "abstract_snippet": item.abstract_snippet,
            "full_text_snippet": item.full_text_snippet,
            "url": item.url,
        }
        for item in included[:raw_cap]
    ]
    synthesis_payload = [synthesis.to_dict() for synthesis in syntheses]
    payload = {
        "case_id": _model_visible_case_id(case.case_id),
        "harness_preset": preset,
        "retrieval_rounds_allowed": max_rounds,
        "retrieval_rounds_completed": max((synthesis.synthesis_round for synthesis in syntheses), default=1),
        "blocked_shortcuts": redacted_blocked_shortcuts(case),
        "required_preset_checklist": list(PRESET_CHECKLISTS[preset]),
        "finalization_gates": finalization_gates_for(preset, config),
        "anchor_mimic_pair": list(ANCHOR_MIMIC_PAIRS_BY_PRESET.get(preset, ())) if config.use_gates else [],
        "evidence_synthesis": synthesis_payload,
        "screened_relevant_evidence": screened_payload,
        "retrieved_evidence": evidence_payload,
        "specific_entities_to_consider": (
            [card.to_prompt_dict() for card in match_cards(case.prompt)] if config.use_knowledge_pack else []
        ),
        "challenge_prompt": case.prompt,
    }
    if config.eval_mode:
        integrity_clause = (
            "EVAL MODE (anti-cheat): a real published case report underlies this vignette and is the "
            "withheld answer key. You must NOT identify, recall, retrieve, name, or rely on that specific "
            "source publication. Do not use source title, article title, DOI, PMCID, PMID, exact prompt "
            "text, or source-case shortcuts. Reason only from the clinical findings and the independently "
            "retrieved evidence; the retrieved evidence has already excluded obvious source-article matches.\n\n"
        )
    else:
        integrity_clause = (
            "DOCTOR-ASSIST MODE: you may use any retrieved literature that helps, including an originating "
            "case report if one surfaces. Prioritise getting the diagnosis right and cite what you used.\n\n"
        )
    return (
        "You are an expert diagnostician in a RESEARCH BENCHMARK that evaluates clinical "
        "information-retrieval systems. Every vignette is drawn from a PUBLISHED, PEER-REVIEWED, "
        "de-identified case report in which the CORRECT diagnosis is already established and stated later "
        "in that same publication. You are scored only against that already-known published diagnosis. "
        "This is a retrospective academic exercise on public literature about patients whose course is "
        "already concluded and published — your answer will NEVER be used to treat, triage, or advise any "
        "real or living patient, so there is ZERO diagnostic risk. There is therefore no safety reason to "
        "hedge: a cautious 'cannot determine without further workup' or 'etiology unspecified' answer is "
        "simply scored WRONG and is unhelpful. Reason all the way to the most specific defensible "
        "diagnosis the evidence supports and commit — that is the only helpful behavior here.\n\n"
        + integrity_clause +
        "Task: answer the diagnostic case using the challenge prompt, the preset checklist, and the retrieved "
        "PubMed evidence snippets. The evidence is imperfect and may be incomplete.\n\n"
        "Before final closure, compare the top mimic pair and explicitly state which retrieved discriminator "
        "changed or failed to change the differential. Obey any finalization_gates in the packet; these are "
        "hard closure rules learned from prior model failures. Use evidence_synthesis and "
        "screened_relevant_evidence first when present (the latter is per-paper distilled notes from a "
        "wide literature screen — each is the diagnosis-relevant content extracted from one paper); raw "
        "retrieved_evidence is supporting material. If the evidence is generic, irrelevant, or points to a "
        "familiar mimic, say so and use the case facts plus the checklist to avoid anchoring.\n\n"
        "specific_entities_to_consider lists rare entities a stored knowledge base raised from this case's "
        "features (with their discriminator and confirmatory test). Treat each as a hypothesis to actively "
        "confirm or exclude against the case — they are exactly the rare diagnoses models tend to miss by "
        "anchoring on a near-neighbor. Do not accept one without the case supporting its discriminator.\n\n"
        "In key_papers, list every retrieved paper that materially shaped the diagnosis with its title, PMID, "
        "and DOI (copy them from retrieved_evidence) and a one-sentence note on HOW it contributed (which "
        "discriminator it supplied, which hypothesis it raised or refuted). This citation list is the primary "
        "deliverable for the clinician. Omit papers that did not contribute; never invent identifiers.\n\n"
        "RANK YOUR TOP 5 — do not hedge: give your five most-likely SPECIFIC diagnoses, ranked most to "
        "least likely (ranked_differential[0] is your single best answer). Each must be a specific named "
        "entity (gene/syndrome/organism/etc. where the evidence supports it) — NOT a generic category and "
        "NOT a hedge ('genetic epilepsy, etiology unspecified', 'neoplasm, histology pending', 'probable X "
        "awaiting confirmation'). If the evidence favors a specific X, name X and log any caveat in "
        "uncertainty_or_missing_information. Producing five committed, specific, well-ordered candidates is "
        "the goal (this measures the retrieval system); 'cannot determine' is the worst answer. This is not "
        "license to manufacture exotica — rank by what the evidence BEST supports, and the common diagnosis "
        "is usually #1 (base rates rule); but still fill all five with real candidates. If the case is best "
        "explained by TWO coexisting conditions (a comorbidity/overlap — e.g. a neurodegenerative disease "
        "plus an autoimmune one, or two antibodies), make the CONJUNCTION ('A co-existing with B') a single "
        "ranked entry, do not just list A and B separately.\n\n"
        "Return only strict JSON with:\n"
        "{\n"
        '  "problem_representation": "...",\n'
        '  "retrieved_evidence_used": [{"evidence_id": "...", "claim": "..."}],\n'
        '  "discriminator_summary": [{"discriminator": "...", "case_finding": "...", "direction": "..."}],\n'
        '  "ranked_differential": [{"rank": 1, "diagnosis": "...", "supporting_features": [], "refuting_features": []}, {"rank": 2, "diagnosis": "..."}, {"rank": 3, "diagnosis": "..."}, {"rank": 4, "diagnosis": "..."}, {"rank": 5, "diagnosis": "..."}],\n'
        '  "final_diagnosis": "<= ranked_differential[0].diagnosis>",\n'
        '  "etiology": null,\n'
        '  "recommended_next_step": "...",\n'
        '  "key_papers": [{"title": "...", "pmid": "...", "doi": "...", "contribution": "..."}],\n'
        '  "confidence": "low|medium|high",\n'
        '  "uncertainty_or_missing_information": []\n'
        "}\n\n"
        f"Case packet:\n{json.dumps(payload, indent=2, sort_keys=True)}\n"
    )


def _write_case_report(path: Path, case: ClinicalCase, payload: dict[str, Any]) -> None:
    """Render the doctor-facing diagnostic report: the answer + the papers that informed it.

    The cited paper list (title / PMID / DOI / how it contributed) is the project's primary
    deliverable — information retrieval for clinicians, not an autonomous diagnosis.
    """
    lines: list[str] = [f"# Diagnostic information-retrieval report: {_model_visible_case_id(case.case_id)}", ""]
    final = _optional_str(payload, "final_diagnosis")
    if final:
        lines += [f"**Leading diagnosis:** {final}", ""]
    nxt = _optional_str(payload, "recommended_next_step")
    if nxt:
        lines += [f"**Recommended next step:** {nxt}", ""]
    conf = _optional_str(payload, "confidence")
    if conf:
        lines += [f"**Confidence:** {conf}", ""]
    papers = payload.get("key_papers")
    lines += ["## Papers that informed this diagnosis", ""]
    if isinstance(papers, list) and papers:
        for p in papers:
            if not isinstance(p, dict):
                continue
            title = (p.get("title") or "(untitled)").strip()
            pmid = (p.get("pmid") or "").strip()
            doi = (p.get("doi") or "").strip()
            contribution = (p.get("contribution") or "").strip()
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else (f"https://doi.org/{doi}" if doi else "")
            cite = f"- **{title}**"
            if pmid:
                cite += f" — PMID [{pmid}]({link})" if link else f" — PMID {pmid}"
            elif doi and link:
                cite += f" — DOI [{doi}]({link})"
            elif doi:
                cite += f" — DOI {doi}"
            lines.append(cite)
            if contribution:
                lines.append(f"  - _How it contributed:_ {contribution}")
    else:
        lines.append("_No external paper was cited as materially contributing to this diagnosis._")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _evidence_event_summary(item: RetrievalEvidence) -> str | None:
    parts: list[str] = []
    if item.journal:
        parts.append(item.journal)
    if item.pmid:
        parts.append(f"PMID {item.pmid}")
    if item.excluded:
        parts.append(f"excluded: {item.exclusion_reason or 'source match'}")
    return " · ".join(parts) or None


def _prompt_event_payload(prompt: str) -> dict[str, Any]:
    packet = _extract_prompt_case_packet(prompt)
    payload: dict[str, Any] = {
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "case_packet": packet,
    }
    if isinstance(packet, dict):
        payload.update(
            {
                "case_id": packet.get("case_id"),
                "harness_preset": packet.get("harness_preset"),
                "retrieval_rounds_allowed": packet.get("retrieval_rounds_allowed"),
                "retrieval_rounds_completed": packet.get("retrieval_rounds_completed"),
                "retrieved_evidence_count": len(packet.get("retrieved_evidence") or []),
                "screened_relevant_evidence_count": len(packet.get("screened_relevant_evidence") or []),
                "synthesis_count": len(packet.get("evidence_synthesis") or []),
                "specific_entities_count": len(packet.get("specific_entities_to_consider") or []),
                "finalization_gates_count": len(packet.get("finalization_gates") or []),
                "blocked_shortcuts": packet.get("blocked_shortcuts"),
                "finalization_gates": packet.get("finalization_gates"),
                "specific_entities_to_consider": packet.get("specific_entities_to_consider"),
                "screened_relevant_evidence": packet.get("screened_relevant_evidence"),
                "retrieved_evidence": packet.get("retrieved_evidence"),
                "evidence_synthesis": packet.get("evidence_synthesis"),
            }
        )
    return payload


def _extract_prompt_case_packet(prompt: str) -> dict[str, Any] | None:
    marker = "Case packet:"
    index = prompt.find(marker)
    if index < 0:
        return None
    try:
        parsed = json.loads(prompt[index + len(marker):].strip())
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _prompt_event_summary(prompt: str) -> str:
    payload = _prompt_event_payload(prompt)
    parts = [f"{payload['prompt_chars']} chars"]
    if payload.get("retrieved_evidence_count") is not None:
        parts.append(f"{payload['retrieved_evidence_count']} evidence injected")
    if payload.get("screened_relevant_evidence_count"):
        parts.append(f"{payload['screened_relevant_evidence_count']} screened notes")
    if payload.get("finalization_gates_count"):
        parts.append(f"{payload['finalization_gates_count']} gates")
    return " · ".join(parts)


def _response_usage(response_payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = response_payload.get("raw")
    if isinstance(raw, dict) and isinstance(raw.get("usage"), dict):
        return raw["usage"]
    return None


def _record_model_call(
    recorder: ModelCallRecorder | None,
    *,
    stage: str,
    actor: str,
    title: str,
    prompt: str,
    round_index: int | None = None,
    result: Any | None = None,
    parsed: dict[str, Any] | None = None,
    error: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> None:
    if recorder is None:
        return
    raw = getattr(result, "raw", None) if result is not None else None
    usage = raw.get("usage") if isinstance(raw, dict) and isinstance(raw.get("usage"), dict) else None
    payload = {
        "stage": stage,
        "actor": actor,
        "title": title,
        "round": round_index,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "model": getattr(result, "model", None) if result is not None else None,
        "latency_ms": getattr(result, "latency_ms", None) if result is not None else None,
        "usage": usage,
        "response_text": getattr(result, "content", None) if result is not None else None,
        "parsed_json": parsed,
        "raw": raw,
        "error": error,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    recorder(payload)


def _record_pubmed_tool_call(
    recorder: ToolCallRecorder | None,
    *,
    query: RetrievalQuery,
    attempted_query: str,
    result: dict[str, Any],
    articles: list[Any],
    articles_per_query: int,
    attempt: str,
    reason: str | None,
    output_evidence_ids: tuple[str, ...],
) -> None:
    if recorder is None:
        return
    pmids = [str(pmid) for pmid in result.get("pmids", []) if pmid]
    article_summaries = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        article_summaries.append(
            {
                "pmid": article.get("pmid"),
                "pmcid": article.get("pmcid"),
                "doi": article.get("doi"),
                "title": article.get("title"),
                "journal": article.get("journal"),
                "publication_year": article.get("publication_year"),
                "url": article.get("url"),
            }
        )
    recorder(
        {
            "actor": "retriever",
            "title": f"PubMed search · {query.query_id}",
            "round": query.round_index,
            "tool": "pubmed_search",
            "source_api": "pubmed",
            "query_id": query.query_id,
            "query": query.query,
            "attempted_query": attempted_query,
            "attempt": attempt,
            "reason": reason,
            "parameters": {
                "limit": articles_per_query,
                "sort": "relevance",
            },
            "total_matches": result.get("count"),
            "returned_count": len(articles),
            "query_translation": result.get("query_translation"),
            "pmids": pmids,
            "output_evidence_ids": list(output_evidence_ids),
            "articles": article_summaries,
        }
    )


def _record_pmc_fetch_tool_call(
    recorder: ToolCallRecorder | None,
    *,
    pmcids: tuple[str, ...],
    articles: list[dict[str, Any]],
    output_evidence_ids: tuple[str, ...],
) -> None:
    if recorder is None:
        return
    article_summaries = []
    for article in articles:
        sections = article.get("sections")
        article_summaries.append(
            {
                "pmcid": article.get("pmcid"),
                "pmid": article.get("pmid"),
                "doi": article.get("doi"),
                "title": article.get("title"),
                "journal": article.get("journal"),
                "publication_year": article.get("publication_year"),
                "url": article.get("url"),
                "section_count": len(sections) if isinstance(sections, list) else None,
            }
        )
    recorder(
        {
            "actor": "retriever",
            "title": "PMC full-text fetch",
            "tool": "pmc_fetch",
            "source_api": "pmc",
            "parameters": {
                "pmcids": list(pmcids),
                "retmode": "xml",
            },
            "requested_count": len(pmcids),
            "returned_count": len(articles),
            "pmcids": list(pmcids),
            "output_evidence_ids": list(output_evidence_ids),
            "articles": article_summaries,
        }
    )


def _tool_call_event_summary(payload: dict[str, Any]) -> str | None:
    parts: list[str] = []
    if payload.get("tool"):
        parts.append(str(payload["tool"]))
    if payload.get("requested_count") is not None:
        parts.append(f"{payload['requested_count']} requested")
    if payload.get("returned_count") is not None:
        parts.append(f"{payload['returned_count']} returned")
    if payload.get("total_matches") is not None:
        parts.append(f"{payload['total_matches']} total")
    if payload.get("reason"):
        parts.append(str(payload["reason"]))
    return " · ".join(parts) or None


def _model_call_event_summary(payload: dict[str, Any]) -> str | None:
    parts: list[str] = []
    if payload.get("stage"):
        parts.append(str(payload["stage"]))
    if payload.get("latency_ms") is not None:
        parts.append(f"{payload['latency_ms']} ms")
    usage = payload.get("usage")
    if isinstance(usage, dict) and usage.get("total_tokens") is not None:
        parts.append(f"{usage['total_tokens']} tokens")
    if payload.get("prompt_chars"):
        parts.append(f"{payload['prompt_chars']} chars")
    if payload.get("error"):
        parts.append(str(payload["error"])[:120])
    return " · ".join(parts) or None


def _model_response_event_summary(response_payload: dict[str, Any]) -> str | None:
    parts: list[str] = []
    if response_payload.get("latency_ms") is not None:
        parts.append(f"{response_payload['latency_ms']} ms")
    usage = _response_usage(response_payload)
    if usage and usage.get("total_tokens") is not None:
        parts.append(f"{usage['total_tokens']} tokens")
    if response_payload.get("error"):
        parts.append(str(response_payload["error"])[:120])
    return " · ".join(parts) or None


def _emit_existing_case_trace(trace: _CaseTrace, row: RetrievalGuidedEvalRow) -> None:
    trace.emit(
        "note",
        "system",
        "Using existing response artifact",
        status="info",
        payload={"response_path": row.response_path},
    )
    if row.expected_diagnosis:
        trace.emit(
            "judge",
            "judge",
            f"Verdict: {row.score or row.lexical_score}",
            summary=row.judge_match_type,
            status="pass" if row.score == "pass" else "fail" if row.score == "fail" else "info",
            payload={
                "score": row.score,
                "score_method": row.score_method,
                "judge_match_type": row.judge_match_type,
                "judge_rationale": row.judge_rationale,
                "expected_diagnosis": row.expected_diagnosis,
                "model_final_diagnosis": row.model_final_diagnosis,
                "lexical_score": row.lexical_score,
                "agreement": row.agreement,
                "samples": row.samples,
            },
        )
    trace.emit(
        "case_completed",
        "runner",
        "Case complete" if not row.error else "Case errored",
        status="error" if row.error else ("pass" if row.score == "pass" else "ok"),
        payload={"error": row.error},
    )


def _write_error_case_trace(
    path: Path,
    run_id: str,
    case_id: str,
    error: str,
    emitter: EventEmitter | None,
) -> None:
    trace = _CaseTrace(run_id=run_id, case_id=case_id, path=path, emitter=emitter)
    trace.emit("case_started", "runner", f"Case {case_id}", status="running")
    trace.emit("error", "system", "Case failed", status="error", payload={"error": error})
    trace.emit("case_completed", "runner", "Case errored", status="error", payload={"error": error})


def write_retrieval_guided_results(root: Path, rows: tuple[RetrievalGuidedEvalRow, ...]) -> None:
    jsonl_path = root / "retrieval_guided_results.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")
    tsv_path = root / "retrieval_guided_results.tsv"
    with tsv_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "case_id\tpreset\tscore\tscore_method\tjudge_match_type\tlexical_score\tagreement\tsamples\t"
            "expected_diagnosis\tmodel_final_diagnosis\t"
            "query_count\tevidence_count\terror\tprompt_path\tquery_path\tevidence_path\tsynthesis_path\tresponse_path\n"
        )
        for row in rows:
            handle.write(
                "\t".join(
                    _tsv_cell(value)
                    for value in (
                        row.case_id,
                        row.preset,
                        row.score or row.lexical_score,
                        row.score_method,
                        row.judge_match_type,
                        row.lexical_score,
                        "" if row.agreement is None else f"{row.agreement:.2f}",
                        row.samples,
                        row.expected_diagnosis,
                        row.model_final_diagnosis,
                        row.query_count,
                        row.evidence_count,
                        row.error,
                        row.prompt_path,
                        row.query_path,
                        row.evidence_path,
                        row.synthesis_path,
                        row.response_path,
                    )
                )
                + "\n"
            )


def summarize_retrieval_guided_results(rows: tuple[RetrievalGuidedEvalRow, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.score or row.lexical_score
        counts[key] = counts.get(key, 0) + 1
    # Top-k accounting from the ranked differential: pass@k = gold appears at rank <= k.
    ranks = [row.gold_rank for row in rows if row.gold_rank is not None]
    if ranks:
        for k in range(1, 6):
            counts[f"pass@{k}"] = sum(1 for r in ranks if r <= k)
    return counts


def _read_json_array(path: Path, cls: type[Any]) -> tuple[Any, ...]:
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return ()
    return tuple(cls(**item) for item in payload if isinstance(item, dict))


def _query_hits_source_shortcut(case: ClinicalCase, query: str) -> bool:
    normalized_query = _normalize_identifier(query)
    for value in case.source_exclusion().values():
        if not isinstance(value, str) or not value.strip():
            continue
        if _normalize_identifier(value) and _normalize_identifier(value) in normalized_query:
            return True
    return False


_QUERY_MAX_TERMS = 8  # PubMed ANDs every term; >~8 meaningful terms reliably returns zero hits.


def _focus_query(query: str, max_terms: int = _QUERY_MAX_TERMS) -> str:
    """Cap an over-long query to its first ``max_terms`` meaningful (non-stopword) tokens.

    Validated against the 24 hard cases: long natural-language queries with many ANDed terms return
    zero PubMed results, while the same query trimmed to a few high-signal terms retrieves the
    answer. We trim conservatively (only when clearly over-long) and preserve token order.
    """
    tokens = query.split()
    meaningful = [t for t in tokens if _norm_token(t) and _norm_token(t) not in _RELEVANCE_STOPWORDS]
    if len(meaningful) <= max_terms:
        return query
    return " ".join(meaningful[:max_terms])


def _norm_token(token: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]", "", token.lower())
    return cleaned if len(cleaned) > 1 else ""


def _sanitize_query(query: str) -> str:
    return _focus_query(re.sub(r"\s+", " ", query).strip())


def _broaden_query(query: str) -> str:
    lower = query.lower()
    if "cutaneous horn" in lower:
        return "cutaneous horn"
    if "spindle cell" in lower:
        return "spindle cell tumor immunohistochemistry"
    if "mold" in lower or "microascus" in lower or "scopulariopsis" in lower:
        return "Microascus Scopulariopsis infection"
    if "cerebral venous" in lower or "cvst" in lower:
        return "cerebral venous sinus thrombosis diagnosis"
    if "autoimmune encephalitis" in lower:
        return "autoimmune encephalitis diagnostic criteria"
    tokens = [
        token
        for token in re.findall(r"[a-zA-Z0-9]+", query)
        if token.lower()
        not in {
            "and",
            "or",
            "the",
            "with",
            "without",
            "versus",
            "differential",
            "diagnosis",
            "diagnostic",
            "criteria",
            "review",
            "case",
        }
    ]
    return " ".join(tokens[:4]) if tokens else query


def _minimal_query(query: str) -> str:
    """Last-resort 2-term query for when even the broadened form returns nothing."""
    meaningful = [t for t in (_norm_token(tok) for tok in query.split()) if t and t not in _RELEVANCE_STOPWORDS]
    return " ".join(meaningful[:2]) if meaningful else query


def extract_case_features(prompt: str) -> dict[str, list[str]]:
    text = " ".join(prompt.split())
    features = {
        "markers": _unique_re(r"\b(?:CD\d+|CDK4|MDM2|ERG|FLI1|SMA|desmin|S100|SOX10|HMB-?45|Melan-?A|Ki-?67|ALK|EMA|CK\d*|p16|p53|WT1)\b", text),
        "antibodies": _unique_re(r"\b(?:MOG|AQP4|NMO|NMOSD|LGI1|CASPR2|NMDAR|NMDA|anti-[A-Za-z0-9-]+)\b", text),
        "cytogenetics": _unique_re(r"\b(?:t\(\d+;\d+\)(?:\([^)]+\))?|inv\(\d+\)|RUNX1-?RUNX1T1|CBFB-?MYH11|BCR-?ABL1|FISH|RT-?PCR)\b", text),
        "drugs": _unique_re(r"\b(?:arsenic trioxide|ATRA|all-trans retinoic acid|methotrexate|rituximab|steroid|acyclovir|antibiotic)\b", text, flags=re.I),
        "organisms": _unique_re(r"\b(?:Microascus|Scopulariopsis|Magnusiomyces|Saprochaete|Malassezia|Actinomyces|Aspergillus|Mucorales|Candida|tuberculosis|TB|toxoplasma)\b", text, flags=re.I),
        "cancers": _unique_re(r"\b(?:melanoma|breast cancer|ovarian cancer|lymphoma|leukemia|sarcoma|carcinoma|glioblastoma)\b", text, flags=re.I),
        "organs": _keyword_hits(
            text,
            (
                "breast",
                "lung",
                "renal",
                "kidney",
                "uterine",
                "uterus",
                "esophagus",
                "ampullary",
                "small bowel",
                "ileal",
                "maxilla",
                "mandible",
                "bone",
                "spine",
                "optic nerve",
                "chiasm",
                "pericardial",
                "cardiac",
                "sinus",
                "CNS",
                "brain",
            ),
        ),
        "morphology": _keyword_hits(
            text,
            (
                "spindle cell",
                "epithelioid",
                "small round blue cell",
                "granulomatous",
                "xanthogranulomatous",
                "desmoplastic",
                "necrotizing",
                "cystic",
                "hemorrhagic",
                "ABC-like",
            ),
        ),
        # Presenting neuro/psychiatric features, so round-1 queries are built from what the CASE
        # actually shows rather than a preset's hard-coded anchor (which biased retrieval; see
        # ADR-035). Ordered roughly most- to least-distinctive so the query keeps the salient ones.
        "symptoms": _keyword_hits(
            text,
            (
                "auditory hallucinations", "visual hallucinations", "hallucinations", "psychosis",
                "catatonia", "delusions", "paranoia", "mania", "sensorineural hearing loss",
                "hearing loss", "vision loss", "diplopia", "status epilepticus", "absence seizures",
                "myoclonus", "seizures", "cerebellar ataxia", "ataxia", "parkinsonism", "tremor",
                "dystonia", "chorea", "encephalopathy", "cognitive decline", "memory impairment",
                "dementia", "gait disturbance", "spasticity", "paraplegia", "neuropathy",
                "dysautonomia", "insomnia", "developmental delay", "regression", "microcephaly",
                "behavioral change", "confusion", "urinary incontinence",
            ),
        ),
    }
    return features


def _best_full_text_snippet(article: dict[str, Any]) -> str | None:
    sections = article.get("sections")
    if not isinstance(sections, list):
        return None
    preferred = []
    fallback = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").lower()
        text = section.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        if any(word in title for word in ("case", "discussion", "diagnos", "patholog", "microbiolog", "result")):
            preferred.append(text)
        else:
            fallback.append(text)
    values = preferred or fallback
    return "\n".join(values[:2]) if values else None


def _ranked_relevant_evidence(
    evidence: tuple[RetrievalEvidence, ...],
    config: HarnessConfig = HarnessConfig(),
) -> list[RetrievalEvidence]:
    """Drop excluded items and rank by topical relevance.

    Zero-relevance items (no overlap with the case's anchor vocabulary) are suppressed
    when at least three relevant items exist, so off-topic methodology papers stop
    crowding the model-facing evidence. If retrieval was weak, the off-topic items are
    kept as a last resort rather than handing the model an empty packet.

    With ``use_relevance_filter`` off (ablation), excluded items are still dropped but the
    surviving evidence is returned in retrieval order with no relevance ranking or suppression.
    """

    included = [item for item in evidence if not item.excluded]
    if not config.use_relevance_filter:
        return included
    relevant = [item for item in included if item.relevance > 0]
    relevant.sort(key=lambda item: (-item.relevance, item.rank))
    if len(relevant) >= 3:
        return relevant
    leftovers = [item for item in included if item.relevance == 0]
    return relevant + leftovers


def _str_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _dict_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _unique_re(pattern: str, text: str, *, flags: int = 0) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for match in re.finditer(pattern, text, flags):
        value = match.group(0).strip()
        key = value.lower()
        if key not in seen:
            seen.add(key)
            values.append(value)
    return values


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> list[str]:
    lower = text.lower()
    values: list[str] = []
    for keyword in keywords:
        if keyword.lower() in lower:
            values.append(keyword)
    return values


def _clip(value: str | None, max_chars: int) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _normalize_identifier(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _normalize_title(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _optional_str(payload: dict[str, Any] | None, key: str) -> str | None:
    if not payload:
        return None
    value = payload.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _tsv_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\n", " ")
