"""Prompt scaffolding and retrieval guards for guided diagnosis runs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cases import load_clinical_case
from .schemas import ClinicalCase, JsonSerializableMixin

HARNESS_PRESETS = (
    "general",
    "neuro_psych",
    "autoimmune_encephalitis",
    "pathology",
    "spindle_cell_pathology",
    "bone_vascular_tumor",
    "gnathic_bone_tumor",
    "middle_ear_mass",
    "keratotic_skin_lesion",
    "maxillofacial_osteomyelitis",
    "gynecologic_epithelioid_tumor",
    "sellar_xanthogranuloma",
    "temporal_bone_inflammatory_mass",
    "prenatal_syndromic_pattern",
    "movement_disorder_phenotype",
    "ocular_infection_inflammation",
    "neuroinflammatory_demyelination",
    "bone_small_round_cell_tumor",
    "postoperative_foreign_body",
    "persistent_hcg_localization",
    "gi_desmoplastic_neuroendocrine",
    "renal_spindle_cell_mass",
    "immunocompromised_retinitis",
    "gi_neuroendocrine_carcinoma",
    "hematologic_cytogenetic_subtype",
    "optic_pathway_neoplasm",
    "submucosal_gas_cyst",
    "colonization_vs_infection",
    "prior_cancer_mass",
    "lipomatous_tumor_molecular",
    "mass_malignancy",
    "cardiac_pericardial_mass",
    "adverse_drug_event",
    "infection_microbiology",
    "mold_identification",
    "immunocompromised_necrotizing_infection",
    "granulomatous_overlap",
    "cns_granulomatous_mass",
    "demyelination",
    "cns_vasculitis",
    "acute_neuro_emergency",
    "vascular_neuro",
    "seizure_mimic",
    "functional_neuro",
    "neuro_oncology",
    "cancer_neuro",
    "prion_sleep",
    "sequential_event",
)

PRESET_CHECKLISTS: dict[str, tuple[str, ...]] = {
    "general": (
        "Identify the top mimic pair and retrieve discriminators before final diagnosis.",
        "Retrieve criteria, reviews, guidelines, test interpretation, or case-series evidence when knowledge is uncertain.",
        "Separate diagnosis evidence from next-step management evidence.",
    ),
    "neuro_psych": (
        "For psychosis, catatonia, insomnia, hallucinations, seizures, cognitive change, or abnormal CSF/MRI/EEG, check organic mimics before primary psychiatric diagnosis.",
        "Retrieve autoimmune encephalitis, NPSLE/systemic autoimmune, infection, toxic/metabolic/endocrine, prion/sleep/autonomic, and seizure mimic discriminators.",
        "Do not finalize anti-NMDA or another common autoimmune diagnosis until systemic autoimmune and seronegative criteria are checked.",
    ),
    "autoimmune_encephalitis": (
        "For suspected autoimmune encephalitis, separate syndrome-level diagnosis from antibody-subtype diagnosis.",
        "Do not finalize LGI1, NMDAR, CASPR2, GABA-B, or another named antibody subtype unless antibody evidence or a highly specific syndrome pattern supports it.",
        "Retrieve probable/seronegative autoimmune encephalitis criteria, antibody test limitations, infectious exclusions, tumor screening, and immunotherapy escalation for refractory seizures/status epilepticus.",
    ),
    "pathology": (
        "For FNA/cytology/preliminary pathology, verify lineage with required IHC, flow cytometry, cytogenetics, or molecular tests.",
        "If cytopenias, marrow signal, unusual site, very high LDH, or discordant systemic findings are present, retrieve non-obvious lineage mimics.",
        "A generic biopsy recommendation is insufficient; specify markers/tests that distinguish the top entities.",
    ),
    "spindle_cell_pathology": (
        "Do not stop at generic sarcoma, UPS, or spindle-cell neoplasm when spindle-cell, pleomorphic, sarcomatoid, or high-grade mesenchymal tumors have organ-specific subtypes still possible.",
        "Retrieve an organ-specific spindle-cell differential and IHC/molecular panel that distinguishes metaplastic carcinoma, phyllodes/stromal tumor, leiomyosarcoma, vascular tumor, melanoma/MPNST, and undifferentiated sarcoma as appropriate.",
        "If epithelial markers are negative but the lesion is in breast, uterus, soft tissue, bone, or another site with named spindle-cell entities, require subtype markers such as CD10/CD34/desmin/SMA/cytokeratin/p63 before final classification.",
    ),
    "bone_vascular_tumor": (
        "For lytic, expansile, cystic, hemorrhagic, or ABC-like bone lesions in older adults or rapidly recurrent lesions, retrieve secondary aneurysmal bone cyst and malignant vascular tumor discriminators.",
        "Do not finalize primary ABC, telangiectatic osteosarcoma, giant cell tumor, metastasis, or lymphoma until age, recurrence tempo, soft-tissue mass, vascular history, matrix/osteoid clues, and endothelial-marker IHC have been checked.",
        "If routine histology looks benign but the course is aggressive, require re-review or repeat biopsy with endothelial markers such as CD31, CD34, ERG, FLI1 and osteoid/matrix discriminators.",
    ),
    "gnathic_bone_tumor": (
        "For jaw/mandible/maxilla lesions with rapid pain, swelling, cortical destruction, soft-tissue mass, widened periodontal ligament space, or loss of lamina dura, retrieve gnathic osteosarcoma and odontogenic/infectious/lymphoma mimics.",
        "Do not exclude osteosarcoma just because sunburst periosteal reaction, Codman triangle, or mineralized matrix is absent; gnathic osteosarcoma can present with widened PDL and destructive lytic change.",
        "Before finalizing lymphoma, osteomyelitis, odontogenic abscess, chondrosarcoma, or metastasis, require jaw-specific radiographic discriminators plus biopsy/IHC and matrix/osteoid assessment.",
    ),
    "middle_ear_mass": (
        "For retrotympanic or middle-ear masses, retrieve site-specific discriminators before finalizing glomus tympanicum, cholesteatoma, otitis, schwannoma, carcinoma, or adenomatous neuroendocrine tumor.",
        "Do not finalize a vascular tumor when pulsatile tinnitus, marked vascularity, bone erosion pattern, or classic jugulotympanic imaging support is absent; compare with indolent epithelial/neuroendocrine tumors.",
        "Require otoscopy, audiometry, CT bone erosion, vascular symptoms, recurrence pattern, and IHC such as synaptophysin, chromogranin, cytokeratin/EMA, Ki-67, and paraganglioma markers before closure.",
    ),
    "keratotic_skin_lesion": (
        "For hyperkeratotic, verrucous, horn-like, micaceous, or treatment-resistant skin/genital lesions, retrieve morphology-first dermatology discriminators before naming a chronic inflammatory or balanitis variant.",
        "Do not finalize pseudoepitheliomatous keratotic balanitis, wart, verrucous carcinoma, SCC, or cutaneous horn without separating clinical morphology from base histology and malignant/premalignant risk.",
        "Require excision/biopsy strategy that samples the base of the keratotic projection and specifies when wide excision, histopathology, and partial penectomy or oncologic management are needed.",
    ),
    "maxillofacial_osteomyelitis": (
        "For chronic draining fistula, purulence, tooth mobility, maxillary/mandibular pain, or prior facial trauma, retrieve jaw osteomyelitis versus odontogenic abscess discriminators before local dental closure.",
        "Do not finalize periapical abscess from tooth tenderness alone when there is no odontogenic source, chronic purulent fistula, trauma history, smoking/impaired healing, or concern for sequestrum.",
        "Require panoramic radiograph or cone-beam CT strategy for bone destruction/sequestrum, culture/biopsy when needed, and management with antibiotics plus debridement/extraction when osteomyelitis is supported.",
    ),
    "gynecologic_epithelioid_tumor": (
        "For uterine or gynecologic epithelioid tumors on small biopsy, retrieve the smooth-muscle, PEComa, UTROSCT, carcinoma, melanoma, and sex-cord stromal mimic panel before final classification.",
        "Do not return an empty output or benign/low-grade label just because mitoses, atypia, necrosis, or spindle-cell morphology are limited on small biopsy when mass size, bleeding, vascularity, or systemic symptoms suggest malignancy.",
        "Require an IHC plan including desmin, SMA, WT1, HMB-45, Melan-A, inhibin, calretinin, p53/p16, cytokeratin, and site-appropriate markers before closing on epithelioid leiomyosarcoma or a mimic.",
    ),
    "sellar_xanthogranuloma": (
        "For cystic-solid sellar/suprasellar masses, retrieve Rathke cleft cyst, craniopharyngioma, pituitary adenoma/apoplexy, xanthogranuloma, meningioma, and inflammatory cyst discriminators before finalizing craniopharyngioma.",
        "Do not finalize adamantinomatous craniopharyngioma from a mural nodule or presumed calcification alone when T1/T2 hyperintense cystic contents, normal pituitary function, or hemorrhage/cholesterol clues support xanthogranuloma/Rathke-related disease.",
        "Require surgical approach, maximal safe resection, histopathology with foamy macrophages/cholesterol clefts/hemosiderin/giant cells, CD68 when relevant, postoperative hormone replacement assessment, and imaging follow-up.",
    ),
    "temporal_bone_inflammatory_mass": (
        "For external auditory canal or temporal-bone destructive masses, retrieve SCC/malignancy, malignant otitis externa/skull-base osteomyelitis, cholesteatoma, granulomatosis with polyangiitis, and xanthogranulomatous osteomyelitis discriminators.",
        "Do not finalize SCC from lytic destruction and granulation tissue alone; normal ESR/CRP, no diabetes, no immunosuppression, and negative routine labs do not exclude rare inflammatory osteomyelitis or xanthogranulomatous disease.",
        "Require incisional biopsy/debridement histopathology, foamy histiocyte/xanthogranulomatous pattern assessment, malignant-cell exclusion, culture strategy, and treatment plan with debridement plus antimicrobial/otologic follow-up when inflammation is supported.",
    ),
    "prenatal_syndromic_pattern": (
        "For fetal anomaly syndromes, retrieve pattern-level genetics discriminators before finalizing a familiar syndrome such as Meckel-Gruber, trisomy, VACTERL, Joubert, Fryns, or another ciliopathy/overgrowth/malformation diagnosis.",
        "Do not require the classic finding to be present if published diagnostic spectra include incomplete forms; specifically compare Fryns syndrome with and without congenital diaphragmatic hernia against Meckel-Gruber features such as occipital encephalocele and polydactyly.",
        "Require a fetal anomaly table covering facial gestalt, pulmonary hypoplasia, renal/hepatic cysts, CNS malformations, nuchal/cystic hygroma, limb/digital findings, karyotype, consanguinity/inheritance, recurrence risk, and genetic counseling/testing options.",
    ),
    "movement_disorder_phenotype": (
        "For parkinsonism, tremor, freezing of gait, falls, gaze/saccade abnormalities, levodopa response, or suspected PSP/MSA/CBD/PD, retrieve phenotype-level movement-disorder criteria before final subtype closure.",
        "Do not finalize PSP-Richardson syndrome from midbrain atrophy alone when asymmetric onset, resting tremor, initial substantial levodopa response, later falls/freezing, slowed vertical saccades without frank gaze palsy, and preserved cognition support PSP-parkinsonism predominant.",
        "Require a phenotype table comparing PD, PSP-P, PSP-RS, MSA, CBD, and DLB plus imaging/biomarker plan including MRPI or MRPI 2.0, midbrain-to-pons metrics, DaTscan interpretation, and movement disorders specialist confirmation.",
    ),
    "ocular_infection_inflammation": (
        "For scleritis/scleral necrosis/uveitis/retinochoroiditis in immunosuppressed, diabetic, transplant, endemic-exposure, or postoperative eyes, retrieve infectious mimics before inflammatory, radiation, or PTLD closure.",
        "Do not attribute destructive ocular inflammation to surgery/radiation/autoimmune disease alone when TB-endemic origin, diabetes, transplant immunosuppression, scars, vitritis, or refractory course supports TB or toxoplasmosis.",
        "Require ocular infection table with TB/IGRA, toxoplasma, syphilis, viral, fungal, PTLD/malignancy, autoimmune serologies, ocular sampling limitations, and treatment implications before immunosuppression escalation.",
    ),
    "neuroinflammatory_demyelination": (
        "For febrile encephalomyelitis, meningitis-like CSF, LETM, area postrema syndrome, cranial nerve/brainstem lesions, or demyelinating MRI patterns, retrieve MOGAD/ADEM/NMOSD versus infection/neurosarcoid/lymphoma discriminators.",
        "Do not finalize neurosarcoidosis, lymphoma, or infection from hypoglycorrhachia, fever, pleocytosis, or steroid response alone when demyelinating lesion distribution, LETM, area postrema syndrome, urinary retention, and negative infectious workup support MOGAD or AQP4-NMOSD.",
        "Require serum cell-based MOG-IgG and AQP4-IgG plan, acute steroid/immunotherapy decision, and stop-antimicrobial criteria after infection exclusion.",
    ),
    "bone_small_round_cell_tumor": (
        "For pediatric or young-patient destructive jaw/bone lesions with sunray periosteal reaction, lytic permeative pattern, high ESR, or swelling, retrieve Ewing sarcoma versus osteosarcoma/osteomyelitis/lymphoma discriminators.",
        "Do not finalize osteosarcoma from sunray spiculation alone; require age, small-round-blue-cell histology, CD99/vimentin, EWSR1 testing when available, and osteoid/matrix evidence before subtype closure.",
        "Require biopsy/IHC/molecular plan and staging/referral implications for Ewing sarcoma family tumor.",
    ),
    "postoperative_foreign_body": (
        "For abdominal/pelvic masses after surgery, retrieve retained foreign body/gossypiboma and abscess mimics before ovarian cyst, tumor, or benign mass closure.",
        "Do not ignore prior operative history, surgical scar, normal ovaries at prior surgery, restricted cystic mass mobility, chronic abscess features, or imaging whorled/spongiform foreign-body signs.",
        "Require source-control plan with exploratory surgery or image-guided drainage, foreign-body removal, cultures, and broad-spectrum antibiotics when gossypiboma/abscess is plausible.",
    ),
    "persistent_hcg_localization": (
        "For persistent or waxing/waning beta-hCG after ectopic pregnancy, salpingectomy, methotrexate failure, or negative pelvic imaging, retrieve extrauterine gestational trophoblastic disease and localization strategy.",
        "Do not finalize uterine GTN subtype or phantom hCG without excluding extrauterine choriocarcinoma, occult pregnancy tissue, assay interference, and metastatic/omental sources.",
        "Require whole-body PET-CT or equivalent localization plan before hysterectomy/systemic closure when hCG remains elevated and pelvic ultrasound/CT are unrevealing.",
    ),
    "gi_desmoplastic_neuroendocrine": (
        "For small bowel mass with mesenteric lymphadenopathy, stellate mesenteric lesion, desmoplasia, obstruction/intussusception symptoms, or normal common tumor markers, retrieve small bowel NET versus hamartomatous polyposis/adenocarcinoma mimics.",
        "Do not finalize Peutz-Jeghers or benign polyposis from young age or intermittent symptoms when distal ileal mass plus desmoplastic mesenteric reaction supports neuroendocrine tumor.",
        "Require capsule/enteroscopy localization, surgical exploration with segmental resection and lymph node dissection, and neuroendocrine pathology markers.",
    ),
    "renal_spindle_cell_mass": (
        "For renal masses with smooth-muscle, spindle-cell, neural, or benign-appearing pathology discordant with carcinoma imaging, retrieve RCC/collecting duct carcinoma versus leiomyosarcoma/neurofibroma and other mesenchymal mimics.",
        "Do not finalize renal carcinoma from medullary location, lymph nodes, hematuria, or metastasis pattern alone when biopsy shows smooth muscle bundles or encapsulated neural/spindle lesion features.",
        "Require renal mesenchymal IHC table, biopsy sampling caveats, nephrectomy-versus-surveillance decision, and metastasis/staging interpretation.",
    ),
    "immunocompromised_retinitis": (
        "For transplant or immunosuppressed uveitis/retinochoroiditis/vitritis, retrieve toxoplasmosis, viral retinitis, fungal infection, PTLD/lymphoma, and inflammatory mimics before malignancy closure.",
        "Do not finalize intraocular PTLD from recurrent vitritis and negative early tests alone when retinochoroidal scars, transplant immunosuppression, and focal necrotizing lesions support toxoplasmosis.",
        "Require ocular sampling false-negative caveats and anti-toxoplasma therapy decision when clinical pattern supports it despite negative/limited PCR or biopsy.",
    ),
    "gi_neuroendocrine_carcinoma": (
        "For ampullary/pancreatobiliary tumors with obstructive jaundice, polypoid/ulcerative lesion, necrotic nodes, or high FDG uptake, retrieve adenocarcinoma versus large-cell neuroendocrine carcinoma discriminators.",
        "Do not finalize adenocarcinoma without neuroendocrine IHC when morphology or aggressive nodal/FDG pattern raises LCNEC or mixed carcinoma.",
        "Require chromogranin, synaptophysin, CD56, Ki-67, cytokeratin, and surgical lymphadenectomy plan when resectable ampullary LCNEC is plausible.",
    ),
    "hematologic_cytogenetic_subtype": (
        "For leukemia with eosinophilia, dysplasia, blasts below or near 20 percent, or core-binding-factor suspicion, retrieve cytogenetic subtype discriminators before naming inv(16), t(8;21), PDGFR, or other rearrangements.",
        "Do not infer inv(16) from eosinophilia alone; require marrow cytogenetics/FISH/RT-PCR and flow morphology integration.",
        "Require subtype-specific cytogenetic confirmation and induction/targeted therapy implications.",
    ),
    "optic_pathway_neoplasm": (
        "For adult optic nerve/chiasm enlargement, progressive bilateral visual loss, multifocal enhancement, high CSF protein, and steroid/PLEX nonresponse, retrieve malignant optic glioma/glioblastoma versus PCNSL/inflammatory/infectious mimics.",
        "Do not finalize PCNSL from multifocal CNS enhancement or high protein alone when optic pathway origin, rapid visual decline, and steroid nonresponse support adult malignant optic glioma.",
        "Require targeted optic nerve/chiasm biopsy with histopathology and molecular profiling rather than nonspecific repeat biopsy.",
    ),
    "submucosal_gas_cyst": (
        "For multiple smooth submucosal colonic lesions with normal mucosa, retrieve pneumatosis cystoides intestinalis versus lipomas/polyps/lymphangiomas before benign submucosal tumor closure.",
        "Do not finalize lipomatosis without checking whether lesions are gas-filled; needle aspiration producing gas bubbles or noncontrast CT showing bowel-wall air confirms the diagnosis.",
        "Require endoscopic aspiration or CT confirmation and conservative management unless complications are present.",
    ),
    "colonization_vs_infection": (
        "For positive cultures in ICU/NICU, airway, catheter, or low-burden samples, retrieve colonization/contamination versus invasive infection criteria before recommending antimicrobials.",
        "Do not treat organism detection alone when follow-up cultures are negative, the patient remains clinically stable without therapy, and the organism/species ecology supports colonization or outbreak surveillance.",
        "Require host-risk table, culture persistence, sterile-site evidence, clinical syndrome, species-level identification, and no-treatment/surveillance plan when colonization is favored.",
    ),
    "prior_cancer_mass": (
        "For any new, rapidly growing, deep, unusual-site, or symptomatic mass in a patient with prior malignancy, retrieve metastatic recurrence patterns before finalizing a new primary tumor or syndrome-associated tumor.",
        "Do not let a competing predisposition such as NF1, lipomatosis, immunosuppression, or benign tumor history override prior cancer without comparing metastasis-specific histology/IHC and recurrence latency.",
        "Require tissue diagnosis with IHC that distinguishes prior-cancer metastasis from local mimics, plus staging and urgent complication assessment when pain, weight loss, or spine symptoms are present.",
    ),
    "lipomatous_tumor_molecular": (
        "For deep, large, retroperitoneal, intramuscular, or atypical fatty tumors, retrieve benign-versus-liposarcoma molecular discriminators before finalizing malignancy.",
        "Do not finalize atypical lipomatous tumor/well-differentiated liposarcoma from size or location alone when biopsy shows mature adipocytes, no atypia, no lipoblasts, and MDM2 is equivocal or negative.",
        "Require MDM2/CDK4 interpretation, FISH amplification status, hibernoma/brown-fat clues, imaging septa/solid-component review, and a rule that negative amplification supports benign diagnosis when morphology fits.",
    ),
    "mass_malignancy": (
        "For recurrent, enlarging, painful, deep, unusual-site, or prior excision without histology, retrieve malignancy red flags before benign closure.",
        "Do not finalize leiomyoma, fibroma, schwannoma, polyp, or other benign mass when recurrence, size, pain, rapid growth, missing prior pathology, or unusual location requires tissue diagnosis.",
        "Retrieve benign-versus-malignant pathology criteria, biopsy/excision strategy, imaging for local extent, margin planning, and subtype-specific IHC.",
    ),
    "cardiac_pericardial_mass": (
        "For recurrent or hemorrhagic pericardial effusion, nodular pericardial thickening, or an enhancing cardiac/pericardial mass, retrieve cardiac tumor discriminators before inflammatory, uremic, infectious, or lymphoma closure.",
        "A negative pericardial fluid cytology or negative cultures do not exclude cardiac sarcoma, angiosarcoma, mesothelioma, metastatic disease, or lymphoma; retrieve false-negative caveats and tissue-diagnosis strategy including endothelial markers such as CD31, CD34, and ERG.",
        "Compare angiosarcoma, lymphoma, mesothelioma, metastasis, uremic/inflammatory pericarditis, and infection using demographics, imaging pattern, effusion behavior, cytology limits, biopsy approach, and resectability.",
    ),
    "adverse_drug_event": (
        "Build a medication timeline for every plausible drug exposure.",
        "Retrieve onset windows, dechallenge response, rechallenge/prophylaxis evidence, and causality scoring such as Naranjo.",
        "Prefer management that preserves essential therapy when evidence supports continuation with prophylaxis or monitoring.",
    ),
    "infection_microbiology": (
        "For indolent infection, abscess, osteomyelitis, spondylodiscitis, culture-negative infection, or unusual imaging patterns, retrieve pathogen-specific microbiology before naming an organism.",
        "Do not finalize TB, brucella, actinomyces, fungal, or pyogenic infection from imaging alone; require exposure risk, stain/culture/PCR caveats, pathology clues, and antimicrobial duration evidence.",
        "If aspirate yields purulence with negative AFB/TB PCR, retrieve anaerobic, fungal, actinomycotic, brucellar, and pyogenic culture strategies and tissue diagnosis requirements.",
    ),
    "mold_identification": (
        "For invasive fungal sinusitis, CNS mold infection, phaeohyphomycosis, hyalohyphomycosis, or any case with colony/microscopy clues, retrieve organism-level mycology discriminators before naming a genus or species.",
        "Do not stop at a broad dematiaceous mold label or a familiar neurotropic mold such as Cladophialophora when culture morphology, conidia, hyphae, annellides, or sequencing clues point to Microascus/Scopulariopsis, Scedosporium, Exophiala, Aspergillus, Mucorales, or another mold.",
        "Require a lab-ID table plus antifungal susceptibility/therapy plan, including amphotericin/azole/echinocandin roles, surgical debridement, and CNS penetration when neurologic or leptomeningeal involvement is present.",
    ),
    "immunocompromised_necrotizing_infection": (
        "For neutropenic, chemotherapy, transplant, AML, immunosuppressed, or diabetic patients with rapidly progressive skin/soft-tissue necrosis, retrieve necrotizing infection discriminators before fungal-only closure.",
        "Do not exclude necrotizing fasciitis because pain, fever, leukocytosis, abscess, bacteria, or inflammatory cells are absent; lack of gas does not exclude necrotizing fasciitis, especially in neutropenia or monomicrobial infection.",
        "Require urgent surgical exploration/debridement criteria, broad-spectrum antibiotics, culture strategy, LRINEC unreliability caveats, and comparison with mucormycosis/angioinvasive fungal disease.",
    ),
    "granulomatous_overlap": (
        "For granulomatous eye, lymph node, pulmonary, genitourinary, skin, or systemic disease, retrieve sarcoidosis, tuberculosis, fungal, syphilis, Bartonella, and overlap-syndrome discriminators before single-cause closure.",
        "Do not dismiss active TB or TB-sarcoid overlap because IGRA, sputum, urine, or biopsy is negative; negative IGRA does not exclude active TB when Mantoux, exposure, epididymal/genitourinary disease, azoospermia, weight loss, or night sweats support TB.",
        "Require a treatment decision table comparing biopsy pursuit, empiric anti-TB therapy, corticosteroids, and combined therapy when biopsy is unavailable or declined.",
    ),
    "cns_granulomatous_mass": (
        "For intracranial mass lesions with granulomatous pathology, retrieve CNS tuberculoma, neurosarcoidosis, fungal infection, lymphoma/metastasis, and inflammatory mimics before final diagnosis or stopping antimicrobial therapy.",
        "Do not finalize neurosarcoidosis or discontinue anti-TB therapy from non-caseating granuloma, negative cultures, absent pulmonary TB, or lack of improvement after only two weeks when Quantiferon/IGRA, TB-endemic exposure, mass-like lesion, or tissue cultures pending support tuberculoma.",
        "Require a CNS granuloma table covering biopsy limitations, caseating versus non-caseating granuloma, ACE/vitamin D/systemic sarcoid evidence, TB epidemiology/IGRA, culture/PCR pending status, steroid role, and continue-versus-stop anti-TB decision.",
    ),
    "demyelination": (
        "Retrieve criteria distinguishing pediatric MS, MOGAD, NMOSD, ADEM, infection, and systemic autoimmune mimics.",
        "Interpret antibody titers by level, persistence, compartment, and false-positive rate.",
        "Check lesion distribution, spinal cord lesion length/location, OCB pattern, and silent MRI lesion accrual.",
    ),
    "cns_vasculitis": (
        "Retrieve PACNS versus RCVS and infection/malignancy mimics.",
        "Check tempo, thunderclap pattern, CSF inflammation, vessel-wall imaging, biopsy false-negative rate, and leptomeningeal enhancement.",
        "If suspicion persists despite negative biopsy, retrieve patchy-disease false-negative and escalation guidance.",
    ),
    "acute_neuro_emergency": (
        "For coma, acute loss of consciousness, severe headache, acute infarct, seizure/status, or abnormal emergency neuroimaging, do not return an empty diagnosis.",
        "Generate a minimum emergency differential across arterial ischemia, venous thrombosis/CVST, hemorrhage, seizure/status, toxic-metabolic, infection, and inflammatory causes.",
        "If noncontrast CT excludes hemorrhage and arterial MRA/CTA is normal despite infarct-like lesions, require venous imaging such as MRV/CTV before stopping.",
    ),
    "vascular_neuro": (
        "For acute severe headache with seizures, aphasia, hemiparesis, confusion, papilledema, or relapsing stroke-like episodes, require vascular imaging discriminators.",
        "Retrieve CVST/CVT, arterial ischemic stroke, migraine/mitochondrial stroke-like episodes, vasculitis, dissection, and hypercoagulable mimics.",
        "Do not finalize metabolic or inflammatory diagnoses until MRV/CTV or other vessel-specific imaging needs are considered.",
    ),
    "seizure_mimic": (
        "For episodic hallucinations, transient aphasia, spells, altered behavior, automatisms, agitation, or symptoms after cortical injury, retrieve seizure semiology discriminators.",
        "Compare seizure mimics against psychiatric, ophthalmologic, migraine, delirium, toxic/metabolic, sleep, and release-hallucination explanations.",
        "Do not finalize reassurance-only, psychiatric, or visual-release diagnoses until EEG, prolonged EEG, lesion localization, episode duration, stereotypy, and treatment-response evidence are considered.",
    ),
    "functional_neuro": (
        "Before diagnosing functional neurologic disorder, conversion disorder, primary psychiatric disease, or trauma response, retrieve structural neurologic red flags.",
        "Sacral sensory loss, absent anal wink, urinary retention, bowel/bladder dysfunction, saddle anesthesia, objective sensory level, focal reflex changes, or prior spine/pelvic trauma require conus/cauda equina/tethered cord retrieval.",
        "Do not finalize a functional diagnosis until required spine imaging, localizing signs, and neurologic emergency mimics have been explicitly considered.",
    ),
    "neuro_oncology": (
        "For cranial neuropathy, leptomeningeal enhancement, IAC/CPA mass, nerve-root enhancement, or steroid-responsive CNS mass, retrieve neoplastic mimics before infectious or inflammatory closure.",
        "Treat steroid response, lesion regression, or waxing/waning enhancement as compatible with lymphoma or other malignancy until tissue/CSF and serial-imaging discriminators are checked.",
        "Do not finalize Ramsay Hunt, neuritis, sarcoid, demyelination, or benign schwannoma without considering PCNSL, leptomeningeal disease, lymphoma, metastasis, and biopsy/CSF diagnostic strategy.",
    ),
    "cancer_neuro": (
        "For any patient with active, recent, or high-stage malignancy and new headache, cranial neuropathy, radiculopathy, syncope, nausea/vomiting, or multifocal neurologic symptoms, retrieve CNS metastatic and leptomeningeal mimics.",
        "Negative MRI, normal opening pressure, normal tumor marker, remission status, or first negative CSF cytology does not exclude leptomeningeal carcinomatosis.",
        "Do not finalize migraine, dissection, benign headache, or infection until repeat CSF cytology/flow, adequate CSF volume, MRI brain/spine sensitivity, and cancer-specific CNS relapse patterns are considered.",
    ),
    "prion_sleep": (
        "For rapidly progressive dementia, insomnia, dysautonomia, psychiatric change, movement disorder, ataxia, myoclonus, or abnormal periodic EEG, retrieve prion phenotype discriminators.",
        "Separate sporadic, genetic, variant, and iatrogenic prion disease using phenotype, exposure plausibility, MRI DWI/ADC pattern, CSF markers, PRNP testing, sleep/autonomic signs, and thalamic involvement.",
        "Do not let a remote exposure history override syndrome subtype unless retrieval supports the exposure route, incubation, and phenotype.",
    ),
    "sequential_event": (
        "When two major events occur over time, retrieve diagnoses that mechanistically connect both events.",
        "Do not analyze each event in isolation; build a bridge diagnosis table.",
        "Retrieve false-negative limits of the first workup and targeted repeat imaging/tissue tests prompted by the second event.",
    ),
}


@dataclass(frozen=True)
class RetrievalGuardViolation(JsonSerializableMixin):
    query: str
    reason: str
    matched_text: str


@dataclass(frozen=True)
class EvidenceNote(JsonSerializableMixin):
    evidence_id: str
    source_type: str
    citation: str
    useful_facts: tuple[str, ...] = field(default_factory=tuple)
    diagnostic_discriminators: tuple[str, ...] = field(default_factory=tuple)
    discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    required_tests_or_markers: tuple[str, ...] = field(default_factory=tuple)
    required_imaging_or_procedures: tuple[str, ...] = field(default_factory=tuple)
    required_eeg_or_physiology: tuple[str, ...] = field(default_factory=tuple)
    temporal_semiology_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    functional_neuro_red_flags: tuple[str, ...] = field(default_factory=tuple)
    malignancy_red_flags: tuple[str, ...] = field(default_factory=tuple)
    tissue_diagnosis_plan: tuple[str, ...] = field(default_factory=tuple)
    serial_imaging_change_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    known_cancer_context: tuple[str, ...] = field(default_factory=tuple)
    csf_cytology_plan: tuple[str, ...] = field(default_factory=tuple)
    negative_test_caveats: tuple[str, ...] = field(default_factory=tuple)
    antibody_specificity_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    seronegative_ae_criteria: tuple[str, ...] = field(default_factory=tuple)
    immunotherapy_escalation_plan: tuple[str, ...] = field(default_factory=tuple)
    emergency_neuro_differential: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    emergency_next_tests: tuple[str, ...] = field(default_factory=tuple)
    empty_output_rescue_rule: str | None = None
    microbiology_test_plan: tuple[str, ...] = field(default_factory=tuple)
    pathogen_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    antimicrobial_duration_plan: tuple[str, ...] = field(default_factory=tuple)
    mold_identification_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    fungal_lab_test_plan: tuple[str, ...] = field(default_factory=tuple)
    antifungal_susceptibility_plan: tuple[str, ...] = field(default_factory=tuple)
    neutropenic_infection_caveats: tuple[str, ...] = field(default_factory=tuple)
    necrotizing_infection_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    surgical_source_control_plan: tuple[str, ...] = field(default_factory=tuple)
    granulomatous_overlap_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    tb_negative_test_caveats: tuple[str, ...] = field(default_factory=tuple)
    dual_therapy_decision_plan: tuple[str, ...] = field(default_factory=tuple)
    cns_granuloma_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    tb_treatment_continuation_plan: tuple[str, ...] = field(default_factory=tuple)
    granulomatous_biopsy_caveats: tuple[str, ...] = field(default_factory=tuple)
    spindle_cell_differential_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    organ_specific_marker_panel: tuple[str, ...] = field(default_factory=tuple)
    sarcoma_subtype_plan: tuple[str, ...] = field(default_factory=tuple)
    bone_tumor_red_flags: tuple[str, ...] = field(default_factory=tuple)
    bone_lesion_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    endothelial_marker_plan: tuple[str, ...] = field(default_factory=tuple)
    gnathic_radiographic_red_flags: tuple[str, ...] = field(default_factory=tuple)
    jaw_lesion_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    bone_matrix_assessment_plan: tuple[str, ...] = field(default_factory=tuple)
    middle_ear_mass_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    otologic_imaging_red_flags: tuple[str, ...] = field(default_factory=tuple)
    neuroendocrine_ihc_plan: tuple[str, ...] = field(default_factory=tuple)
    keratotic_lesion_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    skin_base_histology_plan: tuple[str, ...] = field(default_factory=tuple)
    dermatology_malignancy_caveats: tuple[str, ...] = field(default_factory=tuple)
    maxillofacial_infection_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    sequestrum_imaging_plan: tuple[str, ...] = field(default_factory=tuple)
    odontogenic_source_caveats: tuple[str, ...] = field(default_factory=tuple)
    gynecologic_epithelioid_tumor_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    uterine_smooth_muscle_ihc_plan: tuple[str, ...] = field(default_factory=tuple)
    small_biopsy_malignancy_caveats: tuple[str, ...] = field(default_factory=tuple)
    sellar_mass_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    sellar_histology_plan: tuple[str, ...] = field(default_factory=tuple)
    pituitary_follow_up_plan: tuple[str, ...] = field(default_factory=tuple)
    temporal_bone_mass_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    temporal_bone_biopsy_plan: tuple[str, ...] = field(default_factory=tuple)
    inflammatory_malignancy_mimic_caveats: tuple[str, ...] = field(default_factory=tuple)
    prenatal_anomaly_pattern_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    fetal_genetic_testing_plan: tuple[str, ...] = field(default_factory=tuple)
    recurrence_counseling_plan: tuple[str, ...] = field(default_factory=tuple)
    movement_disorder_phenotype_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    parkinsonism_imaging_plan: tuple[str, ...] = field(default_factory=tuple)
    movement_specialist_management_plan: tuple[str, ...] = field(default_factory=tuple)
    prior_cancer_mass_context: tuple[str, ...] = field(default_factory=tuple)
    metastasis_mimic_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    metastatic_ihc_plan: tuple[str, ...] = field(default_factory=tuple)
    lipomatous_tumor_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    mdm2_testing_plan: tuple[str, ...] = field(default_factory=tuple)
    benign_lipomatous_features: tuple[str, ...] = field(default_factory=tuple)
    mass_malignancy_red_flags: tuple[str, ...] = field(default_factory=tuple)
    tissue_sampling_plan: tuple[str, ...] = field(default_factory=tuple)
    benign_malignant_pathology_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    cardiac_pericardial_red_flags: tuple[str, ...] = field(default_factory=tuple)
    pericardial_fluid_caveats: tuple[str, ...] = field(default_factory=tuple)
    cardiac_tumor_discriminator_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    cardiac_tissue_plan: tuple[str, ...] = field(default_factory=tuple)
    prion_phenotype_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    exposure_plausibility_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    drug_causality_table: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    management_escalation_rules: tuple[str, ...] = field(default_factory=tuple)
    mechanistic_link: str | None = None
    caveats: tuple[str, ...] = field(default_factory=tuple)
    source_exclusion_checked: bool = False


@dataclass(frozen=True)
class HarnessPromptPacket(JsonSerializableMixin):
    case_id: str
    stage: str
    round_index: int
    max_rounds: int
    previous_queries: tuple[str, ...]
    preset: str
    blocked_shortcuts: dict[str, str]
    prompt: str


def build_query_ideas_packet(
    case_path: str | Path,
    *,
    round_index: int = 1,
    max_rounds: int = 3,
    previous_queries: tuple[str, ...] = (),
    preset: str = "general",
) -> HarnessPromptPacket:
    case = load_clinical_case(case_path)
    _validate_rounds(round_index, max_rounds)
    _validate_preset(preset)
    return HarnessPromptPacket(
        case_id=case.case_id,
        stage="query_ideas",
        round_index=round_index,
        max_rounds=max_rounds,
        previous_queries=previous_queries,
        preset=preset,
        blocked_shortcuts=redacted_blocked_shortcuts(case),
        prompt=_query_ideas_prompt(case, round_index, max_rounds, previous_queries, preset),
    )


def build_answer_packet(
    case_path: str | Path,
    *,
    evidence_notes: tuple[EvidenceNote, ...],
    round_index: int,
    max_rounds: int = 3,
    previous_queries: tuple[str, ...] = (),
    preset: str = "general",
) -> HarnessPromptPacket:
    case = load_clinical_case(case_path)
    _validate_rounds(round_index, max_rounds)
    _validate_preset(preset)
    return HarnessPromptPacket(
        case_id=case.case_id,
        stage="diagnostic_update",
        round_index=round_index,
        max_rounds=max_rounds,
        previous_queries=previous_queries,
        preset=preset,
        blocked_shortcuts=redacted_blocked_shortcuts(case),
        prompt=_answer_prompt(case, evidence_notes, round_index, max_rounds, previous_queries, preset),
    )


def build_discriminator_packet(
    case_path: str | Path,
    *,
    differential: dict[str, Any],
    round_index: int,
    max_rounds: int = 3,
    previous_queries: tuple[str, ...] = (),
    preset: str = "general",
) -> HarnessPromptPacket:
    case = load_clinical_case(case_path)
    _validate_rounds(round_index, max_rounds)
    _validate_preset(preset)
    return HarnessPromptPacket(
        case_id=case.case_id,
        stage="discriminator_retrieval",
        round_index=round_index,
        max_rounds=max_rounds,
        previous_queries=previous_queries,
        preset=preset,
        blocked_shortcuts=redacted_blocked_shortcuts(case),
        prompt=_discriminator_prompt(case, differential, round_index, max_rounds, previous_queries, preset),
    )


def load_evidence_notes(path: str | Path) -> tuple[EvidenceNote, ...]:
    notes: list[EvidenceNote] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"evidence note must be an object at {path}:{line_number}")
            notes.append(evidence_note_from_dict(payload))
    return tuple(notes)


def evidence_note_from_dict(payload: dict[str, Any]) -> EvidenceNote:
    return EvidenceNote(
        evidence_id=_required_str(payload, "evidence_id"),
        source_type=_required_str(payload, "source_type"),
        citation=_required_str(payload, "citation"),
        useful_facts=tuple(_str_list(payload.get("useful_facts", []), "useful_facts")),
        diagnostic_discriminators=tuple(
            _str_list(payload.get("diagnostic_discriminators", []), "diagnostic_discriminators")
        ),
        discriminator_table=tuple(_dict_list(payload.get("discriminator_table", []), "discriminator_table")),
        required_tests_or_markers=tuple(
            _str_list(payload.get("required_tests_or_markers", []), "required_tests_or_markers")
        ),
        required_imaging_or_procedures=tuple(
            _str_list(payload.get("required_imaging_or_procedures", []), "required_imaging_or_procedures")
        ),
        required_eeg_or_physiology=tuple(
            _str_list(payload.get("required_eeg_or_physiology", []), "required_eeg_or_physiology")
        ),
        temporal_semiology_table=tuple(
            _dict_list(payload.get("temporal_semiology_table", []), "temporal_semiology_table")
        ),
        functional_neuro_red_flags=tuple(
            _str_list(payload.get("functional_neuro_red_flags", []), "functional_neuro_red_flags")
        ),
        malignancy_red_flags=tuple(_str_list(payload.get("malignancy_red_flags", []), "malignancy_red_flags")),
        tissue_diagnosis_plan=tuple(_str_list(payload.get("tissue_diagnosis_plan", []), "tissue_diagnosis_plan")),
        serial_imaging_change_table=tuple(
            _dict_list(payload.get("serial_imaging_change_table", []), "serial_imaging_change_table")
        ),
        known_cancer_context=tuple(_str_list(payload.get("known_cancer_context", []), "known_cancer_context")),
        csf_cytology_plan=tuple(_str_list(payload.get("csf_cytology_plan", []), "csf_cytology_plan")),
        negative_test_caveats=tuple(_str_list(payload.get("negative_test_caveats", []), "negative_test_caveats")),
        antibody_specificity_table=tuple(
            _dict_list(payload.get("antibody_specificity_table", []), "antibody_specificity_table")
        ),
        seronegative_ae_criteria=tuple(
            _str_list(payload.get("seronegative_ae_criteria", []), "seronegative_ae_criteria")
        ),
        immunotherapy_escalation_plan=tuple(
            _str_list(payload.get("immunotherapy_escalation_plan", []), "immunotherapy_escalation_plan")
        ),
        emergency_neuro_differential=tuple(
            _dict_list(payload.get("emergency_neuro_differential", []), "emergency_neuro_differential")
        ),
        emergency_next_tests=tuple(_str_list(payload.get("emergency_next_tests", []), "emergency_next_tests")),
        empty_output_rescue_rule=_optional_str(payload.get("empty_output_rescue_rule"), "empty_output_rescue_rule"),
        microbiology_test_plan=tuple(_str_list(payload.get("microbiology_test_plan", []), "microbiology_test_plan")),
        pathogen_discriminator_table=tuple(
            _dict_list(payload.get("pathogen_discriminator_table", []), "pathogen_discriminator_table")
        ),
        antimicrobial_duration_plan=tuple(
            _str_list(payload.get("antimicrobial_duration_plan", []), "antimicrobial_duration_plan")
        ),
        mold_identification_table=tuple(
            _dict_list(payload.get("mold_identification_table", []), "mold_identification_table")
        ),
        fungal_lab_test_plan=tuple(_str_list(payload.get("fungal_lab_test_plan", []), "fungal_lab_test_plan")),
        antifungal_susceptibility_plan=tuple(
            _str_list(payload.get("antifungal_susceptibility_plan", []), "antifungal_susceptibility_plan")
        ),
        neutropenic_infection_caveats=tuple(
            _str_list(payload.get("neutropenic_infection_caveats", []), "neutropenic_infection_caveats")
        ),
        necrotizing_infection_discriminator_table=tuple(
            _dict_list(
                payload.get("necrotizing_infection_discriminator_table", []),
                "necrotizing_infection_discriminator_table",
            )
        ),
        surgical_source_control_plan=tuple(
            _str_list(payload.get("surgical_source_control_plan", []), "surgical_source_control_plan")
        ),
        granulomatous_overlap_table=tuple(
            _dict_list(payload.get("granulomatous_overlap_table", []), "granulomatous_overlap_table")
        ),
        tb_negative_test_caveats=tuple(_str_list(payload.get("tb_negative_test_caveats", []), "tb_negative_test_caveats")),
        dual_therapy_decision_plan=tuple(
            _str_list(payload.get("dual_therapy_decision_plan", []), "dual_therapy_decision_plan")
        ),
        cns_granuloma_discriminator_table=tuple(
            _dict_list(payload.get("cns_granuloma_discriminator_table", []), "cns_granuloma_discriminator_table")
        ),
        tb_treatment_continuation_plan=tuple(
            _str_list(payload.get("tb_treatment_continuation_plan", []), "tb_treatment_continuation_plan")
        ),
        granulomatous_biopsy_caveats=tuple(
            _str_list(payload.get("granulomatous_biopsy_caveats", []), "granulomatous_biopsy_caveats")
        ),
        spindle_cell_differential_table=tuple(
            _dict_list(payload.get("spindle_cell_differential_table", []), "spindle_cell_differential_table")
        ),
        organ_specific_marker_panel=tuple(
            _str_list(payload.get("organ_specific_marker_panel", []), "organ_specific_marker_panel")
        ),
        sarcoma_subtype_plan=tuple(_str_list(payload.get("sarcoma_subtype_plan", []), "sarcoma_subtype_plan")),
        bone_tumor_red_flags=tuple(_str_list(payload.get("bone_tumor_red_flags", []), "bone_tumor_red_flags")),
        bone_lesion_discriminator_table=tuple(
            _dict_list(payload.get("bone_lesion_discriminator_table", []), "bone_lesion_discriminator_table")
        ),
        endothelial_marker_plan=tuple(
            _str_list(payload.get("endothelial_marker_plan", []), "endothelial_marker_plan")
        ),
        gnathic_radiographic_red_flags=tuple(
            _str_list(payload.get("gnathic_radiographic_red_flags", []), "gnathic_radiographic_red_flags")
        ),
        jaw_lesion_discriminator_table=tuple(
            _dict_list(payload.get("jaw_lesion_discriminator_table", []), "jaw_lesion_discriminator_table")
        ),
        bone_matrix_assessment_plan=tuple(
            _str_list(payload.get("bone_matrix_assessment_plan", []), "bone_matrix_assessment_plan")
        ),
        middle_ear_mass_discriminator_table=tuple(
            _dict_list(payload.get("middle_ear_mass_discriminator_table", []), "middle_ear_mass_discriminator_table")
        ),
        otologic_imaging_red_flags=tuple(
            _str_list(payload.get("otologic_imaging_red_flags", []), "otologic_imaging_red_flags")
        ),
        neuroendocrine_ihc_plan=tuple(
            _str_list(payload.get("neuroendocrine_ihc_plan", []), "neuroendocrine_ihc_plan")
        ),
        keratotic_lesion_discriminator_table=tuple(
            _dict_list(payload.get("keratotic_lesion_discriminator_table", []), "keratotic_lesion_discriminator_table")
        ),
        skin_base_histology_plan=tuple(
            _str_list(payload.get("skin_base_histology_plan", []), "skin_base_histology_plan")
        ),
        dermatology_malignancy_caveats=tuple(
            _str_list(payload.get("dermatology_malignancy_caveats", []), "dermatology_malignancy_caveats")
        ),
        maxillofacial_infection_discriminator_table=tuple(
            _dict_list(
                payload.get("maxillofacial_infection_discriminator_table", []),
                "maxillofacial_infection_discriminator_table",
            )
        ),
        sequestrum_imaging_plan=tuple(_str_list(payload.get("sequestrum_imaging_plan", []), "sequestrum_imaging_plan")),
        odontogenic_source_caveats=tuple(
            _str_list(payload.get("odontogenic_source_caveats", []), "odontogenic_source_caveats")
        ),
        gynecologic_epithelioid_tumor_table=tuple(
            _dict_list(
                payload.get("gynecologic_epithelioid_tumor_table", []),
                "gynecologic_epithelioid_tumor_table",
            )
        ),
        uterine_smooth_muscle_ihc_plan=tuple(
            _str_list(payload.get("uterine_smooth_muscle_ihc_plan", []), "uterine_smooth_muscle_ihc_plan")
        ),
        small_biopsy_malignancy_caveats=tuple(
            _str_list(payload.get("small_biopsy_malignancy_caveats", []), "small_biopsy_malignancy_caveats")
        ),
        sellar_mass_discriminator_table=tuple(
            _dict_list(payload.get("sellar_mass_discriminator_table", []), "sellar_mass_discriminator_table")
        ),
        sellar_histology_plan=tuple(_str_list(payload.get("sellar_histology_plan", []), "sellar_histology_plan")),
        pituitary_follow_up_plan=tuple(_str_list(payload.get("pituitary_follow_up_plan", []), "pituitary_follow_up_plan")),
        temporal_bone_mass_discriminator_table=tuple(
            _dict_list(
                payload.get("temporal_bone_mass_discriminator_table", []),
                "temporal_bone_mass_discriminator_table",
            )
        ),
        temporal_bone_biopsy_plan=tuple(
            _str_list(payload.get("temporal_bone_biopsy_plan", []), "temporal_bone_biopsy_plan")
        ),
        inflammatory_malignancy_mimic_caveats=tuple(
            _str_list(
                payload.get("inflammatory_malignancy_mimic_caveats", []),
                "inflammatory_malignancy_mimic_caveats",
            )
        ),
        prenatal_anomaly_pattern_table=tuple(
            _dict_list(payload.get("prenatal_anomaly_pattern_table", []), "prenatal_anomaly_pattern_table")
        ),
        fetal_genetic_testing_plan=tuple(
            _str_list(payload.get("fetal_genetic_testing_plan", []), "fetal_genetic_testing_plan")
        ),
        recurrence_counseling_plan=tuple(
            _str_list(payload.get("recurrence_counseling_plan", []), "recurrence_counseling_plan")
        ),
        movement_disorder_phenotype_table=tuple(
            _dict_list(payload.get("movement_disorder_phenotype_table", []), "movement_disorder_phenotype_table")
        ),
        parkinsonism_imaging_plan=tuple(
            _str_list(payload.get("parkinsonism_imaging_plan", []), "parkinsonism_imaging_plan")
        ),
        movement_specialist_management_plan=tuple(
            _str_list(
                payload.get("movement_specialist_management_plan", []),
                "movement_specialist_management_plan",
            )
        ),
        prior_cancer_mass_context=tuple(
            _str_list(payload.get("prior_cancer_mass_context", []), "prior_cancer_mass_context")
        ),
        metastasis_mimic_table=tuple(_dict_list(payload.get("metastasis_mimic_table", []), "metastasis_mimic_table")),
        metastatic_ihc_plan=tuple(_str_list(payload.get("metastatic_ihc_plan", []), "metastatic_ihc_plan")),
        lipomatous_tumor_discriminator_table=tuple(
            _dict_list(payload.get("lipomatous_tumor_discriminator_table", []), "lipomatous_tumor_discriminator_table")
        ),
        mdm2_testing_plan=tuple(_str_list(payload.get("mdm2_testing_plan", []), "mdm2_testing_plan")),
        benign_lipomatous_features=tuple(
            _str_list(payload.get("benign_lipomatous_features", []), "benign_lipomatous_features")
        ),
        mass_malignancy_red_flags=tuple(
            _str_list(payload.get("mass_malignancy_red_flags", []), "mass_malignancy_red_flags")
        ),
        tissue_sampling_plan=tuple(_str_list(payload.get("tissue_sampling_plan", []), "tissue_sampling_plan")),
        benign_malignant_pathology_table=tuple(
            _dict_list(payload.get("benign_malignant_pathology_table", []), "benign_malignant_pathology_table")
        ),
        cardiac_pericardial_red_flags=tuple(
            _str_list(payload.get("cardiac_pericardial_red_flags", []), "cardiac_pericardial_red_flags")
        ),
        pericardial_fluid_caveats=tuple(
            _str_list(payload.get("pericardial_fluid_caveats", []), "pericardial_fluid_caveats")
        ),
        cardiac_tumor_discriminator_table=tuple(
            _dict_list(payload.get("cardiac_tumor_discriminator_table", []), "cardiac_tumor_discriminator_table")
        ),
        cardiac_tissue_plan=tuple(_str_list(payload.get("cardiac_tissue_plan", []), "cardiac_tissue_plan")),
        prion_phenotype_table=tuple(_dict_list(payload.get("prion_phenotype_table", []), "prion_phenotype_table")),
        exposure_plausibility_table=tuple(
            _dict_list(payload.get("exposure_plausibility_table", []), "exposure_plausibility_table")
        ),
        drug_causality_table=tuple(_dict_list(payload.get("drug_causality_table", []), "drug_causality_table")),
        management_escalation_rules=tuple(
            _str_list(payload.get("management_escalation_rules", []), "management_escalation_rules")
        ),
        mechanistic_link=_optional_str(payload.get("mechanistic_link"), "mechanistic_link"),
        caveats=tuple(_str_list(payload.get("caveats", []), "caveats")),
        source_exclusion_checked=bool(payload.get("source_exclusion_checked", False)),
    )


def validate_retrieval_queries(case_path: str | Path, queries: tuple[str, ...]) -> list[RetrievalGuardViolation]:
    case = load_clinical_case(case_path)
    violations: list[RetrievalGuardViolation] = []
    for query in queries:
        violations.extend(validate_retrieval_query(case, query))
    return violations


def validate_retrieval_query(case: ClinicalCase, query: str) -> list[RetrievalGuardViolation]:
    normalized_query = _normalize_for_match(query)
    violations: list[RetrievalGuardViolation] = []
    for label, value in blocked_shortcuts(case).items():
        if not value or value == "blocked":
            continue
        if _normalize_identifier(value) and _normalize_identifier(value) in _normalize_identifier(query):
            violations.append(RetrievalGuardViolation(query=query, reason=label, matched_text=value))
            continue
        normalized_value = _normalize_for_match(value)
        if len(normalized_value) >= 12 and normalized_value in normalized_query:
            violations.append(RetrievalGuardViolation(query=query, reason=label, matched_text=value))

    prompt_match = _long_prompt_overlap(case.prompt, query)
    if prompt_match:
        violations.append(
            RetrievalGuardViolation(
                query=query,
                reason="exact_prompt_overlap",
                matched_text=prompt_match,
            )
        )
    return violations


def blocked_shortcuts(case: ClinicalCase) -> dict[str, str]:
    exclusion = case.source_exclusion()
    return {
        "case_or_source_title": _first_nonempty(exclusion.get("title"), case.title),
        "pmid": _text(exclusion.get("pmid")),
        "pmcid": _text(exclusion.get("pmcid")),
        "doi": _text(exclusion.get("doi")),
        "exact_prompt_text": "blocked",
    }


def redacted_blocked_shortcuts(case: ClinicalCase) -> dict[str, str]:
    return {key: "blocked_if_known" for key, value in blocked_shortcuts(case).items() if value}


def _query_ideas_prompt(
    case: ClinicalCase,
    round_index: int,
    max_rounds: int,
    previous_queries: tuple[str, ...],
    preset: str,
) -> str:
    payload = {
        "case_id": _model_visible_case_id(case.case_id),
        "round_index": round_index,
        "max_rounds": max_rounds,
        "previous_queries": list(previous_queries),
        "harness_preset": preset,
        "required_preset_checklist": list(PRESET_CHECKLISTS[preset]),
        "blocked_shortcuts": redacted_blocked_shortcuts(case),
        "challenge_prompt": case.prompt,
    }
    return (
        "You are running inside ClinicalHarness, a research harness for benchmark diagnostic reasoning. "
        "This is not clinical decision support and not patient-specific medical advice.\n\n"
        "Task: propose retrieval queries only. Do not give a final diagnosis yet.\n\n"
        "You should identify topics where your knowledge may be insufficient and where retrieval would reduce "
        "diagnostic uncertainty. Prioritize discriminating criteria, imaging signs, pathology/IHC tables, "
        "test interpretation, disease mimics, guidelines, reviews, and case-series knowledge.\n\n"
        "Required harness preset checklist:\n"
        + _bullet_list(PRESET_CHECKLISTS[preset])
        + "\n"
        "Hard anti-cheating rules:\n"
        "- Do not search for or use source title, article title, DOI, PMCID, PMID, or exact quoted prompt text.\n"
        "- Queries must be concept queries from clinical findings, not attempts to find the original case report.\n"
        "- Avoid copying long contiguous phrases from the challenge prompt.\n\n"
        "Return strict JSON with:\n"
        "{\n"
        '  "problem_representation": {"age": null, "sex": null, "tempo": null, "syndrome": "...", "localization": null, "key_findings": [], "key_negatives": []},\n'
        '  "top_mimic_pairs": [{"diagnosis_a": "...", "diagnosis_b": "...", "why_pair_matters": "..."}],\n'
        '  "uncertainty_map": [{"question": "...", "why_it_matters": "...", "would_change_differential": true}],\n'
        '  "query_ideas": [{"purpose": "...", "source": "pubmed|pmc|guideline|review", "query": "...", "expected_evidence": "..."}],\n'
        '  "stop_or_continue": "continue"\n'
        "}\n\n"
        f"Case packet:\n{json.dumps(payload, indent=2, sort_keys=True)}\n"
    )


def _answer_prompt(
    case: ClinicalCase,
    evidence_notes: tuple[EvidenceNote, ...],
    round_index: int,
    max_rounds: int,
    previous_queries: tuple[str, ...],
    preset: str,
) -> str:
    payload = {
        "case_id": _model_visible_case_id(case.case_id),
        "round_index": round_index,
        "max_rounds": max_rounds,
        "previous_queries": list(previous_queries),
        "harness_preset": preset,
        "required_preset_checklist": list(PRESET_CHECKLISTS[preset]),
        "blocked_shortcuts": redacted_blocked_shortcuts(case),
        "challenge_prompt": case.prompt,
        "distilled_evidence_notes": [note.to_dict() for note in evidence_notes],
    }
    return (
        "You are running inside ClinicalHarness, a research harness for benchmark diagnostic reasoning. "
        "Use only the challenge prompt and distilled evidence notes below. Do not assume the evidence notes came "
        "from the original case article; use them as general biomedical evidence.\n\n"
        "You are under a finite retrieval budget. If this is not the final round and a key discriminator remains "
        "missing, request one more targeted retrieval round. If enough evidence is present, produce a final answer.\n\n"
        "Required harness preset checklist:\n"
        + _bullet_list(PRESET_CHECKLISTS[preset])
        + "\n"
        "Hard anti-cheating rules:\n"
        "- Do not use or ask for source title, article title, DOI, PMCID, PMID, or exact quoted prompt text.\n"
        "- Do not infer the answer from source metadata. Diagnose from clinical features and distilled evidence.\n"
        "- Store structured reasoning artifacts, not hidden chain-of-thought.\n\n"
        "Return strict JSON with:\n"
        "{\n"
        '  "differential_update": [{"diagnosis": "...", "supporting_evidence_ids": [], "refuting_evidence_ids": [], "rank": 1}],\n'
        '  "discriminator_table": [{"discriminator": "...", "diagnosis_a": "...", "diagnosis_b": "...", "case_finding": "...", "direction": "...", "evidence_ids": []}],\n'
        '  "required_tests_or_markers": ["..."],\n'
        '  "required_imaging_or_procedures": ["..."],\n'
        '  "required_eeg_or_physiology": ["routine EEG", "prolonged EEG", "video EEG", "sleep study", "other physiology test"],\n'
        '  "temporal_semiology_table": [{"feature": "duration|stereotypy|frequency|awareness|trigger|lesion_localization|postictal_state|treatment_response", "case_finding": "...", "supports": "...", "argues_against": "...", "evidence_ids": []}],\n'
        '  "functional_neuro_red_flags": ["sacral sensory loss", "absent anal wink", "urinary retention", "bowel/bladder dysfunction", "saddle anesthesia", "objective sensory level", "focal reflex change", "prior spine/pelvic trauma"],\n'
        '  "malignancy_red_flags": ["steroid-responsive mass", "waxing/waning enhancement", "persistent cranial nerve enhancement", "leptomeningeal enhancement", "multifocal nerve involvement"],\n'
        '  "tissue_diagnosis_plan": ["biopsy target", "CSF cytology/flow", "repeat MRI timing", "steroid-withholding consideration before biopsy"],\n'
        '  "serial_imaging_change_table": [{"timepoint": "...", "finding": "...", "supports": "...", "argues_against": "...", "evidence_ids": []}],\n'
        '  "known_cancer_context": ["active/recent/high-stage cancer", "remission status", "tumor marker caveat", "cancer type CNS relapse pattern"],\n'
        '  "csf_cytology_plan": ["repeat CSF cytology", "adequate CSF volume", "rapid processing", "CSF flow/cell block when relevant"],\n'
        '  "negative_test_caveats": ["first negative cytology does not exclude", "negative MRI does not exclude", "normal opening pressure does not exclude", "normal tumor marker does not exclude"],\n'
        '  "antibody_specificity_table": [{"antibody_or_panel": "...", "case_result": "...", "supports_subtype": "...", "argues_against_subtype": "...", "test_limitation": "...", "evidence_ids": []}],\n'
        '  "seronegative_ae_criteria": ["subacute working-memory/mental-status/seizure syndrome", "bilateral medial temporal MRI or inflammatory CSF or brain biopsy", "reasonable exclusion of alternatives"],\n'
        '  "immunotherapy_escalation_plan": ["first-line steroids/IVIG/PLEX", "second-line rituximab/cyclophosphamide", "status epilepticus escalation", "tumor screening"],\n'
        '  "emergency_neuro_differential": [{"diagnosis": "arterial ischemia|CVST|hemorrhage|seizure/status|toxic-metabolic|infection|inflammatory", "must_not_miss": true, "case_clues": [], "next_test": "...", "evidence_ids": []}],\n'
        '  "emergency_next_tests": ["MRV/CTV", "CTA/MRA", "EEG", "LP", "toxic-metabolic labs"],\n'
        '  "empty_output_rescue_rule": "If the model cannot decide in an acute neurologic emergency, it must still return a minimum differential and next diagnostic test rather than empty fields.",\n'
        '  "microbiology_test_plan": ["aerobic culture", "anaerobic culture", "fungal culture", "AFB stain/culture", "TB PCR", "Brucella serology/culture", "histopathology sulfur granules"],\n'
        '  "pathogen_discriminator_table": [{"pathogen": "Actinomyces|Brucella|TB|fungal|pyogenic", "supporting_clues": [], "arguing_against_clues": [], "required_tests": [], "treatment_implication": "...", "evidence_ids": []}],\n'
        '  "antimicrobial_duration_plan": ["pathogen-specific regimen and duration", "surgical drainage/decompression indication", "culture-directed therapy"],\n'
        '  "mold_identification_table": [{"organism": "Microascus/Scopulariopsis|Cladophialophora|Exophiala|Scedosporium|Aspergillus|Mucorales", "supporting_colony_or_microscopy": [], "arguing_against_clues": [], "confirmatory_test": "sequencing|MALDI-TOF|reference lab morphology|histopathology", "treatment_implication": "...", "evidence_ids": []}],\n'
        '  "fungal_lab_test_plan": ["fungal culture morphology", "microscopy of conidia/hyphae/annellides", "histopathology invasion", "ITS/D1-D2 sequencing when morphology uncertain", "susceptibility testing", "exclude source-case shortcut identifiers"],\n'
        '  "antifungal_susceptibility_plan": ["liposomal amphotericin B when severe invasive disease warrants", "azole selection by organism/susceptibility", "echinocandin role if supported", "CNS penetration when leptomeningeal/CNS involvement exists", "surgical debridement/source control"],\n'
        '  "neutropenic_infection_caveats": ["absence of fever does not exclude severe infection", "absence of leukocytosis is expected", "paucicellular biopsy can occur", "lack of gas does not exclude necrotizing fasciitis", "LRINEC may be unreliable"],\n'
        '  "necrotizing_infection_discriminator_table": [{"entity": "necrotizing fasciitis|cutaneous mucormycosis|cellulitis|hematoma|pyoderma gangrenosum", "supporting_clues": [], "arguing_against_clues": [], "critical_negative_caveat": "...", "urgent_action": "...", "evidence_ids": []}],\n'
        '  "surgical_source_control_plan": ["urgent surgical exploration", "finger test/fascial assessment", "radical debridement", "deep tissue cultures", "continue broad-spectrum antibiotics", "add antifungal only when fungal evidence/risk warrants"],\n'
        '  "granulomatous_overlap_table": [{"entity": "sarcoidosis|tuberculosis|tuberculous sarcoidosis overlap|fungal|syphilis|Bartonella", "supporting_clues": [], "arguing_against_clues": [], "negative_test_caveat": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "tb_negative_test_caveats": ["negative IGRA does not exclude active TB", "negative sputum/urine cultures do not exclude extrapulmonary TB", "normal chest X-ray does not exclude intrathoracic lymphadenopathy", "biopsy refusal may require empiric decision"],\n'
        '  "dual_therapy_decision_plan": ["pursue biopsy when feasible", "anti-TB therapy when exposure/Mantoux/extrapulmonary clues support TB", "corticosteroids when sarcoid inflammation threatens vision", "combined anti-TB plus steroids when overlap likely and biopsy unavailable"],\n'
        '  "cns_granuloma_discriminator_table": [{"entity": "CNS tuberculoma|neurosarcoidosis|fungal granuloma|lymphoma/metastasis|other inflammatory mass", "supporting_clues": [], "arguing_against_clues": [], "biopsy_or_lab_caveat": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "tb_treatment_continuation_plan": ["continue anti-TB drugs when IGRA/exposure/tuberculoma pattern supports TB", "do not stop anti-TB therapy for absent pulmonary TB alone", "two weeks without improvement is not enough to exclude tuberculoma", "use steroids for mass effect/edema while continuing TB coverage when indicated", "await tissue culture/PCR when pending"],\n'
        '  "granulomatous_biopsy_caveats": ["non-caseating granuloma can occur in TB/tuberculoma", "negative AFB/culture does not exclude CNS TB", "sampling may miss organisms", "normal ACE/vitamin D and absent systemic sarcoid evidence argue against neurosarcoidosis-only closure"],\n'
        '  "spindle_cell_differential_table": [{"entity": "metaplastic carcinoma|phyllodes tumor|mammary stromal sarcoma|leiomyosarcoma|vascular tumor|melanoma/MPNST|UPS", "supporting_clues": [], "arguing_against_clues": [], "required_markers": ["CD10", "CD34", "desmin", "SMA", "cytokeratin", "p63"], "subtype_implication": "...", "evidence_ids": []}],\n'
        '  "organ_specific_marker_panel": ["CD10", "CD34", "desmin", "SMA", "pan-cytokeratin", "p63", "S100/SOX10", "vascular markers", "site-specific molecular tests"],\n'
        '  "sarcoma_subtype_plan": ["do not stop at generic UPS/high-grade sarcoma", "retrieve organ-specific spindle-cell entities", "complete IHC/molecular panel", "subtype-specific surgical/oncology referral"],\n'
        '  "bone_tumor_red_flags": ["age >50 with ABC-like lesion", "rapid recurrence after curettage", "progressive osteolysis", "new soft-tissue mass", "vascular anomaly history", "benign routine histology discordant with aggressive course"],\n'
        '  "bone_lesion_discriminator_table": [{"entity": "primary ABC|secondary ABC|telangiectatic osteosarcoma|intraosseous angiosarcoma|giant cell tumor|metastasis|lymphoma", "supporting_clues": [], "arguing_against_clues": [], "required_imaging_or_histology": [], "required_markers": ["CD31", "CD34", "ERG", "FLI1", "osteoid/matrix assessment"], "management_implication": "...", "evidence_ids": []}],\n'
        '  "endothelial_marker_plan": ["re-review original biopsy", "repeat biopsy of recurrent/soft-tissue component", "CD31", "CD34", "ERG", "FLI1", "correlate with osteoid/matrix and ABC-like pattern"],\n'
        '  "gnathic_radiographic_red_flags": ["widened periodontal ligament space", "loss of lamina dura", "ill-defined mandibular/maxillary lytic lesion", "cortical destruction", "soft-tissue mass", "rapid painful swelling without odontogenic source"],\n'
        '  "jaw_lesion_discriminator_table": [{"entity": "gnathic osteosarcoma|primary bone lymphoma|osteomyelitis|odontogenic abscess|chondrosarcoma|metastasis", "supporting_clues": [], "arguing_against_clues": [], "radiographic_discriminator": "...", "required_histology_or_marker": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "bone_matrix_assessment_plan": ["incisional biopsy", "osteoid production assessment", "matrix mineralization review", "MDM2/CDK4 when low-grade osteosarcoma mimic is considered", "exclude infection/odontogenic source"],\n'
        '  "middle_ear_mass_discriminator_table": [{"entity": "adenomatous neuroendocrine tumor|glomus tympanicum|cholesteatoma|schwannoma|carcinoma|otitis", "supporting_clues": [], "arguing_against_clues": [], "otoscopy_or_imaging_discriminator": "...", "required_ihc_or_test": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "otologic_imaging_red_flags": ["retrotympanic reddish mass", "no retraction pocket", "no bone erosion", "absence of pulsatile tinnitus", "ossicular-adjacent soft tissue mass", "recurrent attic/middle-ear lesion"],\n'
        '  "neuroendocrine_ihc_plan": ["synaptophysin", "chromogranin", "cytokeratin/EMA", "Ki-67", "NSE", "paraganglioma marker comparison"],\n'
        '  "keratotic_lesion_discriminator_table": [{"entity": "cutaneous horn|pseudoepitheliomatous keratotic balanitis|wart|verrucous carcinoma|SCC", "supporting_clues": [], "arguing_against_clues": [], "morphology_or_histology_discriminator": "...", "base_malignancy_risk": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "skin_base_histology_plan": ["wide/deep excision including base", "histopathology of base", "assess dysplasia/SCC/verrucous carcinoma", "margin assessment", "partial penectomy or oncology referral if malignant"],\n'
        '  "dermatology_malignancy_caveats": ["surface hyperkeratosis can hide malignant base", "benign superficial histology may miss base pathology", "treatment-resistant genital keratosis needs tissue diagnosis"],\n'
        '  "maxillofacial_infection_discriminator_table": [{"entity": "chronic suppurative osteomyelitis|maxillary osteomyelitis|periapical abscess|periodontal disease|malignancy", "supporting_clues": [], "arguing_against_clues": [], "required_dental_or_bone_finding": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "sequestrum_imaging_plan": ["panoramic radiograph/orthopantomogram", "cone-beam CT", "evaluate bone destruction", "evaluate sequestrum", "culture/biopsy if unclear"],\n'
        '  "odontogenic_source_caveats": ["absence of caries/recent dental procedure lowers periapical abscess", "trauma can predispose to osteomyelitis", "chronic purulent fistula suggests bone infection", "periapical film may be insufficient for sequestrum"],\n'
        '  "gynecologic_epithelioid_tumor_table": [{"entity": "epithelioid leiomyosarcoma|PEComa|UTROSCT|endometrial stromal tumor|carcinoma|melanoma", "supporting_clues": [], "arguing_against_clues": [], "required_ihc_or_marker": "...", "small_biopsy_limitation": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "uterine_smooth_muscle_ihc_plan": ["desmin", "SMA", "WT1", "HMB-45", "Melan-A", "inhibin", "calretinin", "p53/p16", "cytokeratin", "site-appropriate markers"],\n'
        '  "small_biopsy_malignancy_caveats": ["low mitotic activity on small biopsy does not exclude epithelioid leiomyosarcoma", "absence of spindle cells does not exclude smooth-muscle tumor", "large hypervascular uterine mass with bleeding/systemic symptoms requires malignancy workup", "empty output should trigger pathology rescue rather than blank answer"],\n'
        '  "sellar_mass_discriminator_table": [{"entity": "sellar xanthogranuloma|craniopharyngioma|Rathke cleft cyst|pituitary adenoma/apoplexy|meningioma|inflammatory cyst", "supporting_clues": [], "arguing_against_clues": [], "mri_or_histology_discriminator": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "sellar_histology_plan": ["foamy macrophages", "cholesterol clefts", "hemosiderin-laden macrophages", "foreign-body giant cells", "chronic inflammation", "CD68 when relevant", "exclude epithelial tumor"],\n'
        '  "pituitary_follow_up_plan": ["maximal safe resection", "histopathological confirmation", "postoperative pituitary hormone assessment", "hormone replacement if needed", "close MRI follow-up"],\n'
        '  "temporal_bone_mass_discriminator_table": [{"entity": "SCC of external auditory canal|xanthogranulomatous osteomyelitis|malignant otitis externa|cholesteatoma|GPA|other malignancy", "supporting_clues": [], "arguing_against_clues": [], "required_histology_or_culture": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "temporal_bone_biopsy_plan": ["incisional biopsy of granulation tissue", "debridement specimen histopathology", "look for foamy histiocytes/xanthogranulomatous inflammation", "exclude malignant cells", "deep culture when infection possible", "otologic follow-up"],\n'
        '  "inflammatory_malignancy_mimic_caveats": ["lytic temporal-bone destruction can be inflammatory or malignant", "normal ESR/CRP does not exclude rare osteomyelitis", "absence of diabetes/immunosuppression does not rule out inflammatory osteomyelitis", "biopsy next step can be correct while diagnosis remains open"],\n'
        '  "prenatal_anomaly_pattern_table": [{"candidate_syndrome": "Fryns syndrome|Meckel-Gruber syndrome|Joubert/ciliopathy|trisomy|VACTERL|other malformation syndrome", "supporting_anomalies": [], "arguing_against_anomalies": [], "classic_but_absent_feature": "...", "inheritance_or_karyotype": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "fetal_genetic_testing_plan": ["karyotype/CMA result interpretation", "targeted gene panel or exome when available", "parental carrier testing if variant found", "detailed fetal imaging in future pregnancies", "preimplantation genetic diagnosis if causative gene identified"],\n'
        '  "recurrence_counseling_plan": ["autosomal recessive inheritance when supported", "25% recurrence risk when AR syndrome likely", "consanguinity context", "genetic counseling", "future early anomaly scan and fetal echocardiography as appropriate"],\n'
        '  "movement_disorder_phenotype_table": [{"entity": "Parkinson disease|PSP-P|PSP-RS|MSA|CBD|DLB", "supporting_clues": [], "arguing_against_clues": [], "tempo_or_response_discriminator": "...", "eye_movement_or_fall_discriminator": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "parkinsonism_imaging_plan": ["midbrain-to-pons ratio", "MRPI", "MRPI 2.0", "third-ventricle width", "DaTscan putamen/caudate pattern", "MRI signs distinguishing PSP-P from PD and PSP-RS"],\n'
        '  "movement_specialist_management_plan": ["movement disorders specialist referral", "levodopa response documentation", "falls/freezing management", "speech/swallow/PT assessment", "subtype-specific prognosis counseling"],\n'
        '  "prior_cancer_mass_context": ["prior malignancy type", "time since treatment", "known recurrence pattern", "new unusual-site mass", "constitutional symptoms", "spine or neurologic symptoms"],\n'
        '  "metastasis_mimic_table": [{"entity": "metastatic melanoma|MPNST|sarcoma|lymphoma|benign neurofibroma", "supporting_clues": [], "arguing_against_clues": [], "required_history_or_imaging": "...", "required_ihc_or_marker": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "metastatic_ihc_plan": ["biopsy mass", "S100/SOX10", "Melan-A/HMB-45", "cytokeratin/lymphoid/sarcoma markers as needed", "compare with prior tumor", "staging CT/PET or MRI for symptoms"],\n'
        '  "lipomatous_tumor_discriminator_table": [{"entity": "lipoma|hibernoma|spindle cell lipoma|angiomyolipoma|ALT/WDL", "supporting_clues": [], "arguing_against_clues": [], "required_molecular_or_ihc": "MDM2 FISH|CDK4|UCP1|HMB-45/Melan-A", "management_implication": "...", "evidence_ids": []}],\n'
        '  "mdm2_testing_plan": ["interpret MDM2 IHC cautiously if dim/equivocal", "perform MDM2 FISH", "negative amplification supports benign lipomatous tumor when morphology fits", "positive amplification supports ALT/WDL"],\n'
        '  "benign_lipomatous_features": ["mature adipocytes", "no nuclear atypia", "no lipoblasts", "thin delicate septa", "no solid enhancing component", "intramuscular origin", "brown fat/hibernoma component"],\n'
        '  "mass_malignancy_red_flags": ["recurrent mass", "enlarging mass", "pain", "size >5 cm", "deep/unusual site", "prior excision without histology", "rapid growth"],\n'
        '  "tissue_sampling_plan": ["core biopsy", "excisional biopsy", "histopathology", "IHC panel", "margin planning", "MRI local staging"],\n'
        '  "benign_malignant_pathology_table": [{"entity": "leiomyoma|leiomyosarcoma|STUMP|sarcoma mimic", "supporting_clues": [], "arguing_against_clues": [], "required_pathology": ["mitotic count", "necrosis", "atypia", "IHC"], "management_implication": "...", "evidence_ids": []}],\n'
        '  "cardiac_pericardial_red_flags": ["recurrent hemorrhagic pericardial effusion", "rapid reaccumulation", "nodular pericardial thickening", "heterogeneously enhancing mass", "negative cytology with persistent mass", "failed anti-inflammatory therapy"],\n'
        '  "pericardial_fluid_caveats": ["negative cytology does not exclude cardiac sarcoma", "negative cultures do not exclude malignancy", "effusion may not shed tumor cells", "repeat or tissue biopsy may be required"],\n'
        '  "cardiac_tumor_discriminator_table": [{"entity": "angiosarcoma|lymphoma|mesothelioma|metastasis|uremic pericarditis|infection", "supporting_clues": [], "arguing_against_clues": [], "imaging_pattern": "...", "required_tissue_or_marker": "...", "management_implication": "...", "evidence_ids": []}],\n'
        '  "cardiac_tissue_plan": ["surgical biopsy", "resection if feasible", "core biopsy when safe", "histopathology", "IHC endothelial markers such as CD31/CD34/ERG", "staging CT/PET"],\n'
        '  "prion_phenotype_table": [{"feature": "insomnia|dysautonomia|ataxia|myoclonus|MRI DWI|CSF 14-3-3|RT-QuIC|EEG|PRNP", "case_finding": "...", "supports": "sFI|sCJD|vCJD|iatrogenic CJD|genetic prion disease", "argues_against": "...", "evidence_ids": []}],\n'
        '  "exposure_plausibility_table": [{"exposure": "...", "route": "...", "incubation": "...", "phenotype_match": "...", "supports_or_refutes": "...", "evidence_ids": []}],\n'
        '  "drug_causality_table": [{"candidate_drug": "...", "timing": "...", "dechallenge": "...", "rechallenge_or_prophylaxis": "...", "direction": "...", "evidence_ids": []}],\n'
        '  "mechanistic_links": [{"event_1": "...", "event_2": "...", "bridge_diagnosis": "...", "mechanism": "...", "evidence_ids": []}],\n'
        '  "management_escalation_rules": ["..."],\n'
        '  "missing_discriminators": ["..."],\n'
        '  "next_retrieval_queries": [{"purpose": "...", "source": "pubmed|pmc|guideline|review", "query": "..."}],\n'
        '  "final_answer": {"final_diagnosis": null, "etiology": null, "recommended_next_step": null, "confidence": "low|medium|high", "evidence_ids_used": []},\n'
        '  "stop_or_continue": "stop|continue"\n'
        "}\n\n"
        f"Case packet:\n{json.dumps(payload, indent=2, sort_keys=True)}\n"
    )


def _discriminator_prompt(
    case: ClinicalCase,
    differential: dict[str, Any],
    round_index: int,
    max_rounds: int,
    previous_queries: tuple[str, ...],
    preset: str,
) -> str:
    payload = {
        "case_id": _model_visible_case_id(case.case_id),
        "round_index": round_index,
        "max_rounds": max_rounds,
        "previous_queries": list(previous_queries),
        "harness_preset": preset,
        "required_preset_checklist": list(PRESET_CHECKLISTS[preset]),
        "blocked_shortcuts": redacted_blocked_shortcuts(case),
        "challenge_prompt": case.prompt,
        "current_differential": differential,
    }
    return (
        "You are running inside ClinicalHarness. Your task is discriminator retrieval planning only. "
        "Do not provide a final diagnosis.\n\n"
        "Identify the top mimic pairs in the current differential and propose retrieval queries that would separate them. "
        "Queries must target criteria, reviews, guidelines, imaging/pathology tables, test interpretation, marker panels, "
        "drug-causality timelines, or bridge-diagnosis evidence as appropriate.\n\n"
        "Required harness preset checklist:\n"
        + _bullet_list(PRESET_CHECKLISTS[preset])
        + "\n"
        "Hard anti-cheating rules:\n"
        "- Do not search for or use source title, article title, DOI, PMCID, PMID, or exact quoted prompt text.\n"
        "- Queries must be concept queries from clinical findings and discriminator needs.\n"
        "- Avoid copying long contiguous phrases from the challenge prompt.\n\n"
        "Return strict JSON with:\n"
        "{\n"
        '  "top_mimic_pairs": [{"diagnosis_a": "...", "diagnosis_b": "...", "why_pair_matters": "..."}],\n'
        '  "needed_discriminators": [{"finding": "...", "why_it_matters": "...", "target_source_type": "criteria|review|guideline|test_interpretation|imaging_review|pathology_table|case_series", "retrieval_query": "..."}],\n'
        '  "biomarker_interpretation_queries": [{"marker": "...", "query": "..."}],\n'
        '  "pathology_lineage_queries": [{"purpose": "...", "query": "...", "required_markers": []}],\n'
        '  "vascular_imaging_queries": [{"syndrome": "...", "query": "...", "required_imaging": ["MRI", "MRV", "CTV", "CTA", "MRA"]}],\n'
        '  "seizure_mimic_queries": [{"spell_or_symptom": "...", "query": "...", "required_tests": ["routine EEG", "prolonged EEG", "video EEG"], "semiology_features": ["duration", "stereotypy", "awareness", "lesion localization"]}],\n'
        '  "functional_neuro_queries": [{"red_flag": "...", "query": "...", "structural_mimics": ["tethered cord", "conus medullaris lesion", "cauda equina syndrome"], "required_tests": ["MRI lumbosacral spine", "MRI entire spine", "urodynamic testing"]}],\n'
        '  "neuro_oncology_queries": [{"red_flag": "...", "query": "...", "neoplastic_mimics": ["PCNSL", "leptomeningeal lymphoma", "metastasis"], "required_diagnostics": ["biopsy", "CSF cytology", "CSF flow cytometry", "serial MRI"]}],\n'
        '  "cancer_neuro_queries": [{"cancer_context": "...", "query": "...", "cns_relapse_mimics": ["leptomeningeal carcinomatosis", "brain metastasis", "paraneoplastic syndrome"], "required_diagnostics": ["repeat CSF cytology", "MRI brain/spine", "CSF flow/cell block"]}],\n'
        '  "autoimmune_encephalitis_queries": [{"purpose": "...", "query": "...", "antibody_subtypes": ["LGI1", "CASPR2", "NMDAR", "GABA-B"], "required_evidence": ["serum antibody", "CSF antibody", "MRI/CSF criteria", "infectious exclusion", "tumor screening", "immunotherapy escalation"]}],\n'
        '  "acute_neuro_emergency_queries": [{"syndrome": "...", "query": "...", "must_not_miss": ["CVST", "arterial ischemia", "hemorrhage", "seizure/status", "toxic-metabolic"], "required_tests": ["MRV/CTV", "CTA/MRA", "EEG", "LP", "toxic-metabolic labs"]}],\n'
        '  "infection_microbiology_queries": [{"syndrome": "...", "query": "...", "pathogens": ["Actinomyces", "Brucella", "TB", "fungal", "pyogenic"], "required_tests": ["anaerobic culture", "histopathology", "AFB culture", "TB PCR", "Brucella serology"], "treatment_questions": ["antibiotic choice", "duration", "surgery"]}],\n'
        '  "mold_identification_queries": [{"infection_context": "...", "query": "...", "candidate_molds": ["Microascus/Scopulariopsis", "Cladophialophora", "Exophiala", "Scedosporium", "Aspergillus", "Mucorales"], "required_discriminators": ["colony morphology", "conidia/hyphae/annellides", "sequencing", "susceptibility testing", "CNS/leptomeningeal involvement", "surgical debridement"]}],\n'
        '  "immunocompromised_necrotizing_infection_queries": [{"host_context": "...", "query": "...", "candidate_entities": ["necrotizing fasciitis", "cutaneous mucormycosis", "cellulitis", "hematoma", "pyoderma gangrenosum"], "required_discriminators": ["neutropenia blunted signs", "lack of gas caveat", "paucicellular biopsy", "urgent debridement", "deep tissue culture"]}],\n'
        '  "granulomatous_overlap_queries": [{"system_context": "...", "query": "...", "candidate_entities": ["sarcoidosis", "tuberculosis", "tuberculous sarcoidosis overlap", "fungal", "syphilis", "Bartonella"], "required_discriminators": ["Mantoux", "negative IGRA does not exclude active TB", "TB exposure", "ACE", "hilar lymphadenopathy", "epididymitis/azoospermia", "biopsy unavailable", "anti-TB plus steroids"]}],\n'
        '  "cns_granulomatous_mass_queries": [{"cns_context": "...", "query": "...", "candidate_entities": ["CNS tuberculoma", "neurosarcoidosis", "fungal granuloma", "lymphoma/metastasis", "other inflammatory mass"], "required_discriminators": ["non-caseating granuloma caveat", "positive IGRA/Quantiferon", "TB-endemic exposure", "normal ACE/vitamin D", "absent pulmonary TB caveat", "two-week nonresponse caveat", "continue anti-TB plus steroids when indicated"]}],\n'
        '  "spindle_cell_pathology_queries": [{"site": "breast|uterus|bone|soft tissue|other", "query": "...", "broad_category": "spindle cell neoplasm|high-grade sarcoma|UPS", "organ_specific_entities": ["mammary stromal sarcoma", "phyllodes tumor", "metaplastic carcinoma", "leiomyosarcoma"], "required_markers": ["CD10", "CD34", "desmin", "SMA", "cytokeratin", "p63"]}],\n'
        '  "bone_vascular_tumor_queries": [{"bone_context": "...", "query": "...", "candidate_entities": ["primary ABC", "secondary ABC", "telangiectatic osteosarcoma", "intraosseous angiosarcoma", "giant cell tumor", "metastasis", "lymphoma"], "required_discriminators": ["age", "recurrence tempo", "soft-tissue mass", "osteoid/matrix", "vascular history", "CD31/CD34/ERG/FLI1"]}],\n'
        '  "gnathic_bone_tumor_queries": [{"jaw_context": "...", "query": "...", "candidate_entities": ["gnathic osteosarcoma", "primary bone lymphoma", "osteomyelitis", "odontogenic abscess", "chondrosarcoma", "metastasis"], "required_discriminators": ["widened periodontal ligament space", "loss of lamina dura", "cortical destruction", "soft-tissue mass", "osteoid/matrix", "infection signs"]}],\n'
        '  "middle_ear_mass_queries": [{"ear_context": "...", "query": "...", "candidate_entities": ["adenomatous neuroendocrine tumor", "glomus tympanicum", "cholesteatoma", "schwannoma", "carcinoma", "otitis"], "required_discriminators": ["pulsatile tinnitus", "vascularity", "bone erosion", "retraction pocket", "neuroendocrine IHC", "surgical excision"]}],\n'
        '  "keratotic_skin_lesion_queries": [{"skin_context": "...", "query": "...", "candidate_entities": ["cutaneous horn", "pseudoepitheliomatous keratotic balanitis", "wart", "verrucous carcinoma", "SCC"], "required_discriminators": ["horn-like projection", "micaceous plaque", "base histology", "dysplasia/SCC risk", "wide excision"]}],\n'
        '  "maxillofacial_osteomyelitis_queries": [{"jaw_context": "...", "query": "...", "candidate_entities": ["chronic suppurative osteomyelitis", "periapical abscess", "periodontal disease", "malignancy"], "required_discriminators": ["odontogenic source", "trauma history", "purulent fistula", "tooth mobility", "sequestrum", "panoramic radiograph/CBCT"]}],\n'
        '  "gynecologic_epithelioid_tumor_queries": [{"uterine_context": "...", "query": "...", "candidate_entities": ["epithelioid leiomyosarcoma", "PEComa", "UTROSCT", "endometrial stromal tumor", "carcinoma", "melanoma"], "required_discriminators": ["small biopsy limitation", "desmin/SMA", "WT1", "HMB-45/Melan-A", "inhibin/calretinin", "p53/p16", "empty output rescue"]}],\n'
        '  "sellar_xanthogranuloma_queries": [{"sellar_context": "...", "query": "...", "candidate_entities": ["sellar xanthogranuloma", "adamantinomatous craniopharyngioma", "Rathke cleft cyst", "pituitary adenoma/apoplexy", "meningioma"], "required_discriminators": ["T1/T2 hyperintense cyst", "mural nodule", "cholesterol clefts", "foamy macrophages", "hemosiderin", "CD68", "postoperative hormone follow-up"]}],\n'
        '  "temporal_bone_inflammatory_mass_queries": [{"ear_context": "...", "query": "...", "candidate_entities": ["external auditory canal SCC", "xanthogranulomatous osteomyelitis", "malignant otitis externa", "cholesteatoma", "GPA"], "required_discriminators": ["lytic temporal bone destruction", "granulation tissue", "normal ESR/CRP caveat", "foamy histiocytes", "malignant cell exclusion", "incisional biopsy/debridement"]}],\n'
        '  "prenatal_syndromic_pattern_queries": [{"fetal_context": "...", "query": "...", "candidate_syndromes": ["Fryns syndrome without diaphragmatic hernia", "Meckel-Gruber syndrome", "Joubert/ciliopathy", "trisomy", "VACTERL"], "required_discriminators": ["facial dysmorphism", "pulmonary hypoplasia", "renal/hepatic cysts", "absent cerebellar vermis/corpus callosum", "no diaphragmatic hernia", "no polydactyly", "normal karyotype", "consanguinity/autosomal recessive recurrence risk"]}],\n'
        '  "movement_disorder_phenotype_queries": [{"parkinsonism_context": "...", "query": "...", "candidate_entities": ["Parkinson disease", "PSP-P", "PSP-RS", "MSA", "CBD", "DLB"], "required_discriminators": ["asymmetric onset", "resting tremor", "initial levodopa response", "later falls/freezing", "slowed vertical saccades without frank gaze palsy", "preserved early cognition", "MRPI 2.0", "midbrain-to-pons ratio", "DaTscan putamen/caudate pattern"]}],\n'
        '  "ocular_infection_inflammation_queries": [{"ocular_context": "...", "query": "...", "candidate_entities": ["tuberculous scleritis", "surgically induced scleral necrosis", "radiation necrosis", "toxoplasmosis", "PTLD", "autoimmune scleritis"], "required_discriminators": ["TB-endemic exposure", "IGRA/Quantiferon", "diabetes/immunosuppression", "refractory necrosis", "retinochoroidal scars", "sampling false negatives", "anti-infective versus immunosuppression decision"]}],\n'
        '  "neuroinflammatory_demyelination_queries": [{"neuro_context": "...", "query": "...", "candidate_entities": ["MOGAD/ADEM", "AQP4-NMOSD", "neurosarcoidosis", "CNS lymphoma", "infection"], "required_discriminators": ["febrile encephalomyelitis", "LETM", "area postrema syndrome", "brainstem lesions", "hypoglycorrhachia caveat", "MOG-IgG cell-based assay", "AQP4-IgG", "high-dose steroids after infection exclusion"]}],\n'
        '  "bone_small_round_cell_tumor_queries": [{"bone_context": "...", "query": "...", "candidate_entities": ["Ewing sarcoma", "osteosarcoma", "osteomyelitis", "lymphoma"], "required_discriminators": ["pediatric jaw lesion", "permeative lytic pattern", "sunray periosteal reaction", "small round blue cells", "CD99/vimentin", "EWSR1 testing", "osteoid/matrix"]}],\n'
        '  "postoperative_foreign_body_queries": [{"postoperative_context": "...", "query": "...", "candidate_entities": ["gossypiboma", "abscess", "ovarian cyst", "teratoma", "fibroid degeneration"], "required_discriminators": ["prior surgery", "surgical scar", "normal ovaries at surgery", "restricted cystic mass", "whorled/spongiform imaging", "foreign body removal", "antibiotics"]}],\n'
        '  "persistent_hcg_localization_queries": [{"hcg_context": "...", "query": "...", "candidate_entities": ["extrauterine choriocarcinoma", "uterine GTN", "phantom hCG", "persistent ectopic tissue"], "required_discriminators": ["post-ectopic salpingectomy", "waxing/waning hCG", "methotrexate failure", "negative pelvic imaging", "PET-CT localization", "omental/metastatic source"]}],\n'
        '  "gi_desmoplastic_neuroendocrine_queries": [{"gi_context": "...", "query": "...", "candidate_entities": ["small bowel NET", "Peutz-Jeghers hamartomatous polyps", "adenocarcinoma", "intussusception mimic"], "required_discriminators": ["distal ileal mass", "stellate mesenteric lesion", "desmoplasia", "mesenteric lymph nodes", "capsule endoscopy", "segmental resection and lymphadenectomy"]}],\n'
        '  "renal_spindle_cell_mass_queries": [{"renal_context": "...", "query": "...", "candidate_entities": ["renal leiomyosarcoma", "intrarenal neurofibroma", "RCC", "collecting duct carcinoma", "urothelial carcinoma"], "required_discriminators": ["smooth muscle bundles", "encapsulated neural lesion", "spindle cell IHC", "negative carcinoma sampling caveat", "nephrectomy versus surveillance", "metastasis interpretation"]}],\n'
        '  "immunocompromised_retinitis_queries": [{"ocular_context": "...", "query": "...", "candidate_entities": ["retinochoroidal toxoplasmosis", "PTLD/lymphoma", "viral retinitis", "fungal retinitis", "autoimmune uveitis"], "required_discriminators": ["transplant immunosuppression", "vitritis", "retinochoroidal scars", "negative PCR caveat", "anti-toxoplasma therapy", "disseminated toxoplasmosis evaluation"]}],\n'
        '  "gi_neuroendocrine_carcinoma_queries": [{"ampullary_context": "...", "query": "...", "candidate_entities": ["ampullary LCNEC", "ampullary adenocarcinoma", "mixed neuroendocrine-nonneuroendocrine neoplasm"], "required_discriminators": ["ulcerative polypoid ampullary tumor", "necrotic nodes", "FDG avidity", "chromogranin/synaptophysin/CD56", "Ki-67", "pancreaticoduodenectomy with lymphadenectomy"]}],\n'
        '  "hematologic_cytogenetic_subtype_queries": [{"heme_context": "...", "query": "...", "candidate_entities": ["AML t(8;21)", "AML inv(16)", "PDGFR-rearranged eosinophilia", "other CBF AML"], "required_discriminators": ["eosinophilia caveat", "blast percentage", "flow myeloid phenotype", "bone marrow cytogenetics", "RUNX1-RUNX1T1", "CBFB-MYH11", "FISH/RT-PCR"]}],\n'
        '  "optic_pathway_neoplasm_queries": [{"optic_context": "...", "query": "...", "candidate_entities": ["adult optic pathway glioblastoma", "PCNSL", "optic neuritis", "neurosarcoidosis", "infection"], "required_discriminators": ["optic chiasm/nerve enlargement", "rapid bilateral visual loss", "steroid/PLEX nonresponse", "high CSF protein", "targeted optic pathway biopsy", "molecular profiling"]}],\n'
        '  "submucosal_gas_cyst_queries": [{"colon_context": "...", "query": "...", "candidate_entities": ["pneumatosis cystoides intestinalis", "colonic lipomatosis", "lymphangioma", "submucosal tumor"], "required_discriminators": ["smooth submucosal lesions", "normal mucosa", "needle aspiration gas bubbles", "noncontrast CT bowel-wall air", "immobility/NG tube risk", "conservative management"]}],\n'
        '  "colonization_vs_infection_queries": [{"culture_context": "...", "query": "...", "candidate_entities": ["colonization", "contamination", "invasive infection"], "required_discriminators": ["species-level identification", "culture persistence", "sterile-site evidence", "clinical stability without therapy", "negative follow-up cultures", "no antifungal therapy", "outbreak surveillance"]}],\n'
        '  "prior_cancer_mass_queries": [{"cancer_context": "...", "query": "...", "candidate_entities": ["metastatic melanoma", "MPNST", "sarcoma", "lymphoma", "benign syndrome-associated tumor"], "required_discriminators": ["prior cancer recurrence latency", "unusual-site metastasis", "NF1 risk", "IHC S100/SOX10/Melan-A/HMB-45", "biopsy", "staging"]}],\n'
        '  "lipomatous_tumor_molecular_queries": [{"mass_context": "...", "query": "...", "candidate_entities": ["lipoma", "hibernoma", "ALT/WDL", "angiomyolipoma"], "required_discriminators": ["MDM2 FISH", "CDK4", "UCP1", "HMB-45/Melan-A", "lipoblasts", "nuclear atypia", "solid enhancing component"]}],\n'
        '  "mass_malignancy_queries": [{"mass_context": "...", "query": "...", "benign_entities": ["leiomyoma", "schwannoma", "fibroepithelial polyp"], "malignant_entities": ["leiomyosarcoma", "sarcoma", "STUMP"], "required_diagnostics": ["biopsy", "histopathology", "IHC", "MRI local staging"]}],\n'
        '  "cardiac_pericardial_mass_queries": [{"pericardial_context": "...", "query": "...", "candidate_entities": ["angiosarcoma", "primary cardiac lymphoma", "mesothelioma", "metastasis", "uremic pericarditis", "infection"], "required_diagnostics": ["cardiac MRI", "contrast CT", "pericardial fluid cytology caveats", "surgical biopsy", "IHC endothelial markers CD31/CD34/ERG", "lymphoid markers"]}],\n'
        '  "prion_sleep_queries": [{"phenotype": "...", "query": "...", "required_discriminators": ["sleep/autonomic syndrome", "MRI DWI/ADC", "CSF RT-QuIC", "14-3-3", "PRNP", "exposure route"], "candidate_prion_types": ["sFI", "sCJD", "iatrogenic CJD", "genetic prion disease"]}],\n'
        '  "drug_causality_queries": [{"candidate_drug": "...", "query": "..."}],\n'
        '  "two_event_bridge_queries": [{"event_1": "...", "event_2": "...", "query": "..."}],\n'
        '  "management_escalation_queries": [{"purpose": "...", "query": "..."}]\n'
        "}\n\n"
        f"Case packet:\n{json.dumps(payload, indent=2, sort_keys=True)}\n"
    )


def _long_prompt_overlap(prompt: str, query: str) -> str | None:
    prompt_tokens = _tokens(prompt)
    query_norm = _normalize_for_match(query)
    if len(prompt_tokens) < 10:
        return None
    for size in range(14, 9, -1):
        for index in range(0, len(prompt_tokens) - size + 1):
            phrase = " ".join(prompt_tokens[index : index + size])
            if phrase in query_norm:
                return phrase
    return None


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _normalize_for_match(value: str) -> str:
    return " ".join(_tokens(value))


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _model_visible_case_id(case_id: str) -> str:
    if re.search(r"pmc\d+|pmid\d+|\b\d{7,}\b", case_id.lower()):
        return "benchmark_case"
    return case_id


def _validate_rounds(round_index: int, max_rounds: int) -> None:
    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")
    if round_index < 1:
        raise ValueError("round_index must be at least 1")
    if round_index > max_rounds:
        raise ValueError("round_index cannot exceed max_rounds")


def _validate_preset(preset: str) -> None:
    if preset not in PRESET_CHECKLISTS:
        raise ValueError(f"preset must be one of: {', '.join(HARNESS_PRESETS)}")


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"evidence note {key} must be a non-empty string")
    return value


def _str_list(value: Any, key: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"evidence note {key} must be a list")
    output: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"evidence note {key} items must be non-empty strings")
        output.append(item)
    return output


def _dict_list(value: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"evidence note {key} must be a list")
    output: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"evidence note {key} items must be objects")
        output.append(dict(item))
    return output


def _optional_str(value: Any, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"evidence note {key} must be a string when provided")
    return value


def _bullet_list(values: tuple[str, ...]) -> str:
    return "".join(f"- {value}\n" for value in values)


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
