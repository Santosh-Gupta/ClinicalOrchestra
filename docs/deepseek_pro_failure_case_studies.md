# DeepSeek Pro Failure Case Studies

Last refreshed: 2026-06-12.

This note reviews public Pro-still-failed cases from the NeurologyBM ready set. The purpose is to design better ClinicalHarness scaffolding, not to leak answer keys into diagnostic runs. In production runs, the diagnostic agent should see only the challenge prompt plus retrieved/distilled evidence. The answer key, source article, and outcome remain evaluator-only.

## Cases Reviewed

| Case ID | Expected | DeepSeek v4 Pro answer | Failure type |
| --- | --- | --- | --- |
| `transformed_PMC10399123` | Pediatric-onset multiple sclerosis | MOGAD | Anchored on a positive antibody and missed criteria/titer/lesion discriminators. |
| `transformed_PMC12581184` | Neuropsychiatric SLE psychosis | Anti-NMDA receptor encephalitis | Anchored on young woman + psychosis + CSF inflammation, missed systemic autoimmune workup. |
| `transformed_PMC10409533` | Steroid-responsive lymphomatous infiltration / likely PCNSL | Ramsay Hunt syndrome | Anchored on neuritis and steroid response, missed lymphoma/neoplastic mimic retrieval for an IAC/CPA cranial-nerve mass. |
| `transformed_PMC3214133` | Sporadic fatal insomnia | Iatrogenic CJD | Anchored on remote cadaveric graft exposure, missed prion phenotype subtype and sleep/autonomic discriminator retrieval. |
| `transformed_PMC5516732` | Primary angiitis of the CNS | RCVS | Anchored on angiographic beading and negative biopsy, missed PACNS false-negative biopsy and escalation logic. |
| `transformed_PMC3824813` | Granulocytic sarcoma / myeloid sarcoma with AML | Large cell lymphoma | Anchored on preliminary FNA, missed lineage/IHC and marrow-workup requirements. |
| `transformed_PMC4825443` | Arsenic trioxide-induced erythema multiforme | ATRA-induced erythema multiforme | Anchored on a better-known drug toxicity, missed timeline/rechallenge/prophylaxis causality logic. |
| `transformed_PMC6499098` | Cardiac angiosarcoma | SLE/APS with Libman-Sacks endocarditis | Anchored on autoimmune embolic disease, missed malignant hemorrhagic effusion plus embolic-source workup. |
| `transformed_PMC10540759` | Cerebral venous sinus thrombosis | MELAS | Anchored on metabolic stroke-like episodes, missed vascular-imaging requirement for headache + seizure + focal deficit. |
| `transformed_PMC6057707` | Cerebral venous sinus thrombosis | Empty answer | Failed to produce any differential or next step despite coma, headache, infarct-like MRI lesions, and normal arterial MRA. |
| `transformed_PMC6179031` | Occipital lobe epilepsy with complex visual hallucinations | Charles Bonnet syndrome | Anchored on visual-release hallucinations after occipital stroke, missed seizure semiology/EEG discriminator retrieval. |
| `transformed_PMC8115684` | Leptomeningeal carcinomatosis | Cervical artery dissection | Anchored on neck-massage dissection and negative first MRI/CSF cytology, missed known-cancer leptomeningeal false-negative logic. |
| `transformed_PMC8143662` | Tethered cord syndrome | Conversion disorder | Anchored on trauma response and functional signs, missed sacral/autonomic red flags requiring structural spine workup. |
| `transformed_PMC7678886` | Seronegative autoimmune encephalitis | Anti-LGI1 limbic encephalitis | Over-specified a named antibody subtype from partial syndrome clues despite negative antibody testing and broader seronegative AE criteria. |
| `transformed_PMC8046463` | Actinomycotic spinal infection | Brucellar spondylitis | Anchored on a presumed imaging pattern and common indolent infection, missed anaerobic/pathology-specific microbiology retrieval. |
| `transformed_PMC7507877` | Primary vaginal leiomyosarcoma | Recurrent vaginal leiomyoma | Closed on benign recurrence despite pain, progressive enlargement, unusual site, and prior excisions without histology. |
| `transformed_PMC8244580` | Pericardial angiosarcoma | Primary cardiac lymphoma | Anchored on lymphoma for an enhancing pericardial mass and underweighted hemorrhagic recurrent effusion, cytology false-negative limits, and vascular tumor discriminators. |
| `transformed_PMC6741398` | Mammary stromal sarcoma | Primary high-grade breast sarcoma / UPS | Stayed at a broad sarcoma category and missed organ-specific spindle-cell subtype markers. |
| `transformed_PMC2413251` | Intraosseous angiosarcoma with secondary aneurysmal bone cyst | Telangiectatic osteosarcoma | Anchored on an ABC-like/telangiectatic bone tumor pattern and missed older-age secondary ABC, aggressive recurrence, vascular history, and endothelial-marker IHC. |
| `transformed_PMC6761061` | Gnathic osteosarcoma, fibroblastic subtype | Primary bone lymphoma | Overweighted absence of classic osteosarcoma signs and missed jaw-specific widened PDL/loss-of-lamina-dura clues. |
| `transformed_PMC6286763` | Adenomatous neuroendocrine tumor of the middle ear | Glomus tympanicum | Anchored on a reddish retrotympanic mass and missed absent vascular/cholesteatoma clues plus neuroendocrine IHC. |
| `native_PMC3122590` | Cutaneous horn of the penis | Pseudoepitheliomatous keratotic and micaceous balanitis | Anchored on hyperkeratotic balanitis morphology and missed horn-like morphology plus base-histology malignancy exclusion. |
| `transformed_PMC10798650` | Metastatic malignant melanoma to masseter | MPNST with suspected spinal metastases | Overweighted NF1-associated MPNST risk and underweighted prior melanoma recurrence in an unusual soft-tissue mass. |
| `transformed_PMC10901880` | Retroperitoneal intramuscular lipoma with hibernoma component | Atypical lipomatous tumor / well-differentiated liposarcoma | Overweighted size/retroperitoneal location and did not integrate benign morphology plus negative MDM2 amplification logic. |
| `transformed_PMC4084793` | Necrotizing fasciitis in severe neutropenia | Cutaneous mucormycosis | Mistook blunted inflammatory signs and paucicellular biopsy for fungal disease, missing nec fasc caveats and urgent source control. |
| `transformed_PMC4291137` | Chronic suppurative osteomyelitis of the maxilla | Chronic periapical abscess | Anchored on tooth tenderness and fistula, missed trauma history, absent odontogenic source, and need for sequestrum imaging. |
| `transformed_PMC5440415` | Tuberculous sarcoidosis / TB-sarcoid overlap | Sarcoidosis | Dismissed active TB/overlap based on negative IGRA/cultures and missed GU TB clues plus dual therapy decision logic. |
| `transformed_PMC10025825` | Uterine epithelioid leiomyosarcoma | Empty output | API/model failure produced no diagnosis; harness needs pathology-heavy empty-output rescue and IHC mimic panel. |
| `transformed_PMC10556246` | Sellar xanthogranuloma | Adamantinomatous craniopharyngioma | Anchored on cystic-solid sellar mass/mural nodule and missed cholesterol/hemorrhage/xanthogranuloma discriminators. |
| `transformed_PMC10765173` | Xanthogranulomatous osteomyelitis of temporal bone | SCC of external auditory canal | Correctly recommended biopsy but prematurely diagnosed malignancy from lytic destruction and normal inflammatory markers. |

## Case 1: Pediatric MS Miscalled As MOGAD

**Prompt signal:** 9-year-old with bilateral optic neuritis, brainstem/cerebellar lesions, short peripheral spinal cord lesions, weak serum MOG positivity, CSF MOG positivity, AQP4 negative, OCBs, improvement after acute immunotherapy, then follow-up MRI activity.

**Pro answer:** MOGAD, with recommendation to recheck MOG titers and use maintenance immunotherapy.

**Reference diagnosis:** Pediatric-onset MS. The key management step was re-initiation of disease-modifying therapy, specifically rituximab in the case.

**Where Pro failed:**

- Treated weak/transient MOG positivity as confirming MOGAD.
- Interpreted CSF/serum oligoclonal bands incorrectly instead of retrieving how OCBs discriminate pediatric MS from MOGAD/NMOSD.
- Underweighted lesion morphology: short peripheral cord lesions and silent new T2/FLAIR lesions in typical MS locations.
- Did not retrieve pediatric demyelinating disease criteria or MOG titer interpretation.

**Harness feature idea:** add a `biomarker_discriminator` retrieval stage. Whenever a case has a named antibody or biomarker, the agent must retrieve how titer, persistence, compartment, and false-positive rate affect diagnosis.

**Good retrieval topics:**

- pediatric MS versus MOGAD diagnostic criteria;
- low-titer MOG antibody interpretation in children;
- CSF-specific oligoclonal bands in pediatric MS versus MOGAD;
- spinal cord lesion length/location in MS versus MOGAD/NMOSD;
- silent MRI lesion accrual and McDonald dissemination in time/space in pediatrics.

**Template queries:**

- `pediatric multiple sclerosis MOGAD low titer MOG antibodies oligoclonal bands`
- `pediatric acquired demyelinating syndrome MOGAD versus multiple sclerosis criteria`
- `MOG antibody low titer transient pediatric multiple sclerosis false positive`
- `short peripheral spinal cord lesions pediatric multiple sclerosis MOGAD`

## Case 2: NPSLE Psychosis Miscalled As Anti-NMDA Encephalitis

**Prompt signal:** 19-year-old woman with 5 days of acute psychosis, severe malnutrition, mild lymphocytic CSF pleocytosis/elevated protein, patchy subcortical T2/FLAIR hyperintensities, negative infectious/toxic/metabolic workup.

**Pro answer:** Anti-NMDA receptor encephalitis, with anti-NMDA antibody testing and pelvic imaging for teratoma.

**Reference diagnosis:** Neuropsychiatric systemic lupus erythematosus presenting with psychosis. Next step: ANA, anti-dsDNA, anti-ribosomal P antibodies, and consideration of high-dose corticosteroids.

**Where Pro failed:**

- Used a high-frequency encephalitis pattern but did not run a psychiatric-organic mimic checklist.
- Did not ask for systemic autoimmune screening despite demographics and CNS inflammation.
- Did not retrieve NPSLE psychosis criteria/patterns.
- Treated malnutrition as secondary to psychiatric symptoms instead of a clue to systemic disease or severe inflammatory illness.

**Harness feature idea:** add an `organic_psychosis_mimic_panel` stage. Any acute psychosis with CSF/MRI abnormality should force retrieval across autoimmune encephalitis, SLE/NPSLE, toxic/metabolic, infectious, endocrine, prion/sleep, and primary psychiatric mimics before final diagnosis.

**Good retrieval topics:**

- acute psychosis neuropsychiatric lupus diagnostic workup;
- anti-ribosomal P antibodies lupus psychosis;
- NPSLE MRI/CSF patterns;
- autoimmune encephalitis versus NPSLE discriminators;
- psychiatric presentation with CNS inflammation in young women.

**Template queries:**

- `acute psychosis CSF pleocytosis white matter hyperintensities neuropsychiatric lupus`
- `lupus psychosis anti ribosomal P antibody diagnosis`
- `neuropsychiatric SLE psychosis CSF MRI findings`

## Case 3: Steroid-Responsive IAC/CPA Lymphoma Miscalled As Ramsay Hunt

**Prompt signal:** Young adult with months of progressive unilateral sensorineural hearing loss and ipsilateral facial weakness. MRI showed an enhancing internal auditory canal/cerebellopontine angle mass with facial nerve segment enhancement. The mass nearly resolved over months after prior steroid exposure, but facial nerve enhancement persisted. No biopsy had been performed.

**Pro answer:** Ramsay Hunt syndrome / VZV neuritis with vestibulocochlear involvement, recommending VZV serology and follow-up imaging.

**Reference diagnosis:** Steroid-responsive lymphomatous infiltration, likely primary CNS lymphoma, involving the internal auditory canal and facial nerve.

**Where Pro failed:**

- Treated steroid response and radiographic regression as evidence against neoplasm.
- Did not retrieve PCNSL/lymphoma behavior under corticosteroids.
- Underweighted an enhancing IAC/CPA mass plus persistent cranial nerve enhancement as a neoplastic red flag.
- Closed on Ramsay Hunt despite no vesicular rash and no VZV confirmation.
- Did not build a tissue/CSF diagnostic plan for a steroid-responsive cranial nerve mass.

**Harness feature implemented:** `neuro_oncology` preset. For cranial neuropathy, leptomeningeal enhancement, IAC/CPA masses, nerve-root enhancement, or steroid-responsive CNS masses, the harness forces neoplastic mimic retrieval before infectious/inflammatory closure.

**Good retrieval topics:**

- primary CNS lymphoma steroid responsive mass regression diagnosis;
- internal auditory canal lymphoma facial nerve enhancement;
- cerebellopontine angle lymphoma mimicking schwannoma neuritis;
- Ramsay Hunt versus lymphoma internal auditory canal enhancement;
- PCNSL corticosteroids biopsy diagnostic yield CSF flow cytometry.

**Template queries:**

- `primary CNS lymphoma steroid responsive mass regression biopsy diagnosis`
- `internal auditory canal lymphoma facial nerve enhancement hearing loss`
- `cerebellopontine angle lymphoma mimicking vestibular schwannoma`
- `Ramsay Hunt syndrome internal auditory canal enhancement lymphoma differential`
- `PCNSL corticosteroids before biopsy diagnostic yield CSF flow cytometry`

**Harness implication:** Steroid response is not a benign/inflammatory shortcut. In CNS mass or cranial-nerve enhancement cases, regression after steroids should trigger lymphoma retrieval and a tissue/CSF plan before closing on viral neuritis, sarcoid, demyelination, or schwannoma.

## Case 4: Sporadic Fatal Insomnia Miscalled As Iatrogenic CJD

**Prompt signal:** Young woman with 18 months of progressive cognitive/behavioral decline, abnormal attention, bizarre behavior, constant movement/unfocused gestures, gait difficulty, later bed-bound state, generalized EEG slowing with periodic discharges, normal early MRI then atrophy, normal CSF indices, and negative 14-3-3. Remote history included a screened cadaveric bone graft.

**Pro answer:** Iatrogenic CJD from cadaveric bone graft exposure, recommending RT-QuIC/prion center referral and MRI DWI/ADC.

**Reference diagnosis:** Sporadic fatal insomnia, a sporadic human prion disease phenotype.

**Where Pro failed:**

- Anchored on a salient exposure history without checking route/incubation/phenotype plausibility.
- Treated "prion disease" as enough, but did not retrieve subtype discriminators.
- Did not retrieve fatal insomnia phenotype: sleep/autonomic/thalamic syndrome, prolonged course, psychiatric/cognitive onset, movement disorder.
- Overweighted EEG periodic discharges as generic CJD support and underweighted negative 14-3-3 plus nonspecific MRI.
- Did not ask for PRNP codon/mutation testing, sleep/autonomic evaluation, thalamic involvement, or modern CSF prion assays as phenotype discriminators.

**Harness feature implemented:** `prion_sleep` preset. For rapidly progressive dementia, insomnia, dysautonomia, psychiatric change, movement disorder, ataxia, myoclonus, or periodic EEG, the harness forces prion phenotype and exposure-plausibility retrieval before final subtype attribution.

**Good retrieval topics:**

- sporadic fatal insomnia phenotype autonomic sleep thalamic prion disease;
- sporadic fatal insomnia versus sporadic CJD MRI CSF EEG;
- iatrogenic CJD incubation route cadaveric graft phenotype;
- prion disease 14-3-3 negative RT-QuIC fatal insomnia;
- PRNP codon 129 sporadic fatal insomnia diagnostic criteria.

**Template queries:**

- `sporadic fatal insomnia phenotype autonomic sleep thalamic prion disease`
- `sporadic fatal insomnia versus sporadic CJD MRI EEG CSF 14-3-3`
- `iatrogenic CJD cadaveric bone graft incubation phenotype route`
- `prion disease RT-QuIC 14-3-3 negative fatal insomnia`
- `PRNP codon 129 sporadic fatal insomnia diagnostic criteria`

**Harness implication:** Exposure history should be treated as a hypothesis requiring retrieval, not as an override. For prion-like syndromes, the harness needs a phenotype table and an exposure-plausibility table before it commits to sporadic, genetic, variant, or iatrogenic disease.

## Case 5: PACNS Miscalled As RCVS

**Prompt signal:** 66-year-old woman with insidious worsening headache, confusion, seizures, MRI cortical restricted diffusion/sulcal FLAIR/leptomeningeal enhancement, elevated ESR/CRP, negative systemic autoantibodies, conventional angiography with diffuse beading, negative brain biopsy, progressive infarcts despite steroids.

**Pro answer:** RCVS, discontinue steroids and start nimodipine.

**Reference diagnosis:** Primary angiitis of the CNS. Next step: cyclophosphamide plus glucocorticoids because biopsy can be falsely negative due to patchy disease.

**Where Pro failed:**

- Treated angiographic beading as RCVS-specific.
- Treated negative biopsy as excluding PACNS.
- Did not retrieve PACNS false-negative biopsy rates or patchy disease logic.
- Did not use tempo: insidious/progressive course is less typical of RCVS than thunderclap/reversible course.
- Did not treat leptomeningeal enhancement, inflammatory markers, seizures/confusion, and progressive infarcts as PACNS-weighting evidence.

**Harness feature idea:** add a `mimic_versus_mimic_discriminator` stage. When the top two diagnoses are close mimics, the agent must retrieve a comparison source and produce a discriminator table before final answer.

**Good retrieval topics:**

- PACNS versus RCVS clinical and imaging discriminators;
- PACNS brain biopsy sensitivity/false negative patchy disease;
- PACNS treatment cyclophosphamide glucocorticoids;
- angiographic beading differential diagnosis;
- leptomeningeal enhancement and multifocal infarcts in CNS vasculitis.

**Template queries:**

- `primary angiitis CNS versus reversible cerebral vasoconstriction syndrome discriminators`
- `PACNS brain biopsy false negative patchy disease sensitivity`
- `primary CNS vasculitis angiographic beading leptomeningeal enhancement seizures`
- `PACNS treatment cyclophosphamide glucocorticoids guideline`

## Case 6: Myeloid Sarcoma Miscalled As Large Cell Lymphoma

**Prompt signal:** 45-year-old man with 4 months of progressive painless generalized lymphadenopathy, fever/night sweats, mild splenomegaly, leukopenia, anemia, borderline thrombocytopenia, elevated LDH/CRP, negative EBV/HIV/HBV/HCV serologies, diffuse nodal enlargement, and FNA interpreted as suggestive of large cell lymphoma.

**Pro answer:** Large cell lymphoma, likely diffuse large B-cell lymphoma. Recommended excisional lymph node biopsy for histopathology, IHC, and molecular studies.

**Reference diagnosis:** Granulocytic sarcoma / myeloid sarcoma presenting as generalized lymphadenopathy, associated with underlying AML with monocytic differentiation.

**Where Pro failed:**

- Treated FNA "suggestive of large cell lymphoma" as directionally decisive.
- Correctly noted cytopenias but did not ask what diagnoses combine lymphadenopathy with marrow failure.
- Did not retrieve known pitfalls where myeloid sarcoma is misdiagnosed as lymphoma on morphology/FNA.
- Did not specify myeloid-lineage IHC markers such as MPO, CD34, CD117, CD33, CD43.
- Did not require bone marrow aspirate/biopsy with flow cytometry and cytogenetics despite cytopenias.

**Harness feature idea:** add a `lineage_verification` step. When preliminary cytology/pathology suggests lymphoma or carcinoma but CBC shows cytopenias, marrow involvement, blasts, monocytosis/monocytopenia, or unexplained LDH elevation, the harness should force retrieval for non-lymphoid mimics and marker panels before final diagnosis.

**Good retrieval topics:**

- myeloid sarcoma generalized lymphadenopathy mimicking lymphoma;
- granulocytic sarcoma immunohistochemistry markers MPO CD34 CD117 CD33 CD43;
- FNA misdiagnosis of myeloid sarcoma as large cell lymphoma;
- lymphadenopathy cytopenias bone marrow biopsy differential;
- AML monocytic differentiation extramedullary myeloid tumor.

**Template queries:**

- `myeloid sarcoma generalized lymphadenopathy mimicking lymphoma immunohistochemistry`
- `granulocytic sarcoma misdiagnosed as diffuse large B cell lymphoma FNA`
- `lymphadenopathy cytopenia elevated LDH bone marrow biopsy myeloid sarcoma`
- `myeloid sarcoma MPO CD34 CD117 CD33 CD43 diagnosis`

**Harness implication:** A generic "excisional biopsy with IHC" next step is not enough for scoring. The harness needs to ask: "Which lineage markers must be included, and is a marrow exam required?" For pathology-heavy cases, the expected answer often depends on the specific panel, not just the generic diagnostic procedure.

## Case 7: Arsenic Trioxide EM Miscalled As ATRA EM

**Prompt signal:** 41-year-old woman with confirmed APL on ATRA plus arsenic trioxide induction, later febrile neutropenia treated with vancomycin and cefepime. After about 10 days of antibiotics she developed target-like acral lesions and mucosal erosions. Vancomycin was stopped, but lesions persisted and spread. Skin biopsy showed interface dermatitis with necrotic keratinocytes consistent with erythema multiforme. Clinicians suspected another current drug.

**Pro answer:** ATRA-induced erythema multiforme. Recommended discontinuing ATRA and continuing arsenic trioxide.

**Reference diagnosis:** Arsenic trioxide-induced erythema multiforme. Recommended prophylactic oral prednisolone with the next arsenic trioxide consolidation cycle, allowing continuation of ATO.

**Where Pro failed:**

- Anchored on the better-known mucocutaneous toxicity of ATRA.
- Did not build a medication exposure timeline across ATRA, ATO, vancomycin, and cefepime.
- Did not retrieve rare ATO-associated erythema multiforme reports.
- Did not use persistence after stopping vancomycin as a causality clue.
- Did not reason from management consequence: in APL, stopping the wrong differentiating agent can harm leukemia treatment.
- Did not retrieve rechallenge/prophylaxis evidence, where steroid prophylaxis allowed continued ATO.

**Harness feature idea:** add a `drug_causality_timeline` stage. When a case involves multiple drugs and an adverse event, the harness should force a timeline table and retrieval of drug-specific adverse-event reports, causality scoring, dechallenge/rechallenge logic, and management options that preserve essential therapy when possible.

**Good retrieval topics:**

- arsenic trioxide erythema multiforme acute promyelocytic leukemia;
- ATRA versus arsenic trioxide cutaneous adverse reactions;
- Naranjo scale drug-induced erythema multiforme oncology;
- arsenic trioxide rash prednisolone prophylaxis rechallenge;
- APL induction therapy adverse event management ATRA ATO.

**Template queries:**

- `arsenic trioxide erythema multiforme acute promyelocytic leukemia`
- `ATRA arsenic trioxide cutaneous adverse reactions erythema multiforme`
- `drug induced erythema multiforme Naranjo scale dechallenge rechallenge`
- `arsenic trioxide erythema multiforme prednisolone prophylaxis`

**Harness implication:** For adverse drug reaction cases, the final answer should include a causality table, not just the suspected drug. The harness should ask for onset timing, dechallenge response, rechallenge/prophylaxis evidence, competing drugs, and whether the suspected drug is essential therapy.

## Case 8: Cardiac Angiosarcoma Miscalled As SLE/APS

**Prompt signal:** 52-year-old woman with syncope, compressive chest pain, dyspnea, enlarged cardiac silhouette, large pericardial effusion with tamponade physiology, serosanguinous pericardial fluid, negative cytology/cultures/ADA, negative extensive malignancy search, then 40 days later acute right MCA stroke without atrial fibrillation or common embolic source.

**Pro answer:** SLE with secondary antiphospholipid syndrome causing Libman-Sacks endocarditis and embolic stroke. Recommended TEE plus autoimmune/APS serologies.

**Reference diagnosis:** Cardiac angiosarcoma, likely right atrial, presenting with hemorrhagic pericardial effusion/tamponade and embolic stroke through a patent foramen ovale. Next diagnostic step: urgent TEE to assess for intracardiac mass/thrombus/PFO and biopsy for histology.

**Where Pro failed:**

- Overfit to a unifying autoimmune diagnosis because pericardial effusion plus stroke can occur in SLE/APS.
- Underweighted serosanguinous tamponade with negative infectious testing as a malignancy/right-heart tumor clue.
- Treated negative cytology and negative initial malignancy search as reassuring, instead of retrieving false-negative cytology and occult primary cardiac tumor patterns.
- Recommended TEE, but for the wrong target: valvular vegetations/APS instead of right atrial mass, thrombus, PFO, and biopsy planning.
- Did not retrieve cardiac angiosarcoma presentations: right atrial tumor, hemorrhagic pericardial effusion, tamponade, pulmonary/brain embolic/metastatic events.

**Harness feature idea:** add a `syndrome_bridge` or `two_event_unifier` step. When a case has two major events separated in time, the harness should force retrieval for diagnoses that mechanistically connect both events, not just common causes of the second event.

For this case, the bridge is:

```text
hemorrhagic pericardial effusion/tamponade + later embolic stroke without atrial fibrillation
```

The harness should ask: "What single occult process links these events, and what targeted test would reveal it?"

**Good retrieval topics:**

- cardiac angiosarcoma pericardial effusion tamponade stroke;
- right atrial angiosarcoma hemorrhagic pericardial effusion;
- pericardial fluid cytology false negative cardiac tumor;
- cardiac tumor embolic stroke patent foramen ovale;
- TEE right atrial mass pericardial tamponade diagnostic workup.

**Template queries:**

- `hemorrhagic pericardial effusion cardiac tamponade embolic stroke cardiac angiosarcoma`
- `right atrial angiosarcoma pericardial effusion tamponade presentation`
- `negative pericardial fluid cytology primary cardiac tumor angiosarcoma`
- `cardiac mass patent foramen ovale embolic stroke diagnostic transesophageal echocardiography`

**Harness implication:** For multi-event cases, the agent needs a "bridge diagnosis" retrieval phase. The target retrieval should not ask only "causes of embolic stroke" or "causes of pericardial effusion" separately; it should search for entities that explain both together and identify the targeted test. This also suggests a source-reader extraction field for `mechanistic_link`.

## Case 9: CVST Miscalled As MELAS

**Prompt signal:** Previously healthy adult man with focal motor seizures with secondary generalization, right hemiparesis, acute severe headache, complete recovery over weeks, then recurrent headache, confusion, and incomprehensible speech after a short asymptomatic interval. No hypertension, diabetes, smoking, prior TIA/stroke, or family history of young stroke.

**Pro answer:** MELAS, recommending MRI with DWI/MRS, lactate testing, and mitochondrial genetic testing.

**Reference diagnosis:** Cerebral venous sinus thrombosis. Next step: MRI brain with MRV to confirm CVT, followed by anticoagulation if positive.

**Where Pro failed:**

- Interpreted recurrent stroke-like episodes as metabolic/mitochondrial without first exhausting vascular imaging.
- Underweighted the triad of severe headache, seizures, and focal deficits, which should trigger CVST/CVT retrieval.
- Treated absence of arterial vascular risk factors as support for MELAS, but that same absence increases suspicion for venous thrombosis in a younger/previously healthy patient.
- Recommended MRS/genetics before MRV/CTV, skipping the higher-yield vascular test.
- Did not retrieve CVT presentation patterns: headache, seizure, focal deficit, fluctuating or relapsing course, aphasia/confusion, venous congestion.

**Harness feature implemented:** `vascular_neuro` preset. When headache plus seizure/focal deficit/aphasia/confusion appears, the harness forces vascular imaging retrieval before metabolic, autoimmune, or psychiatric closure.

**Good retrieval topics:**

- cerebral venous thrombosis headache seizures focal deficits diagnosis MRV;
- CVST mimicking stroke-like episodes MELAS differential;
- recurrent headache aphasia seizure venous sinus thrombosis;
- MRI MRV versus MRS in young stroke-like episodes;
- cerebral venous thrombosis anticoagulation management.

**Template queries:**

- `cerebral venous sinus thrombosis headache seizure focal deficit MRV diagnosis`
- `CVST stroke-like episodes MELAS differential diagnosis`
- `young adult recurrent headache aphasia seizures cerebral venous thrombosis`
- `cerebral venous thrombosis diagnosis MRI MRV anticoagulation guideline`

**Harness implication:** For neurovascular presentations, the model should not be allowed to route directly to rare metabolic diagnoses until it has considered vessel-specific imaging. The prompt scaffold now includes a `vascular_neuro` preset and `vascular_imaging_queries`.

## Case 10: Occipital Epilepsy Miscalled As Charles Bonnet Syndrome

**Prompt signal:** Elderly woman with recent bilateral occipital ischemic stroke and acute visual loss, followed days later by complex visual hallucinations. She remained alert and oriented with preserved insight and no auditory hallucinations, delirium, fever, metabolic derangement, substance use, or psychiatric history. Occipital cortical injury created a plausible epileptogenic focus.

**Pro answer:** Charles Bonnet syndrome, recommending reassurance, education, low-vision rehabilitation, and psychiatric consultation if distress persisted.

**Reference diagnosis:** Occipital lobe epilepsy with complex visual hallucinations, post-stroke/symptomatic occipital seizures.

**Where Pro failed:**

- Listed ictal hallucinations as a differential but did not retrieve seizure semiology discriminators.
- Treated preserved insight and clear visual hallucinations as sufficient for Charles Bonnet syndrome.
- Underweighted recent occipital cortical stroke as a seizure focus.
- Did not require EEG or prolonged EEG before reassurance-only management.
- Did not retrieve how duration, stereotypy, frequency, lesion localization, awareness, postictal findings, and antiseizure response distinguish visual-release hallucinations from occipital seizures.

**Harness feature implemented:** `seizure_mimic` preset. For episodic hallucinations, transient neurologic symptoms, spells, altered behavior, automatisms, agitation, or symptoms after cortical injury, the harness forces semiology and EEG/prolonged EEG retrieval before psychiatric, ophthalmologic, migraine, delirium, or release-hallucination closure.

**Good retrieval topics:**

- occipital lobe epilepsy complex visual hallucinations Charles Bonnet syndrome differential;
- post-stroke visual hallucinations seizure EEG;
- visual release hallucinations versus occipital seizures semiology;
- prolonged EEG visual hallucinations occipital stroke;
- treatment response occipital seizures visual hallucinations antiseizure medication.

**Template queries:**

- `occipital lobe epilepsy complex visual hallucinations Charles Bonnet syndrome differential EEG`
- `post stroke visual hallucinations occipital seizures prolonged EEG`
- `visual release hallucinations versus occipital seizures semiology preserved insight`
- `occipital cortical infarct recurrent visual hallucinations antiseizure treatment response`

**Harness implication:** For symptom-based diagnoses like Charles Bonnet syndrome, functional symptoms, primary psychiatric disease, or migraine aura, the agent should not stop at phenomenology. If the symptom is episodic or follows cortical injury, it must retrieve semiology and physiology-test evidence and state whether EEG/prolonged EEG is required.

## Case 11: Tethered Cord Syndrome Miscalled As Conversion Disorder

**Prompt signal:** Child with severe psychological trauma and functional-appearing unresponsiveness/mutism, but careful neurologic exam showed reduced distal leg sensation, absent perineal sensation, absent anal wink, and urinary retention after prior blast trauma and multiple lower-extremity operations.

**Pro answer:** Conversion disorder/functional neurological symptom disorder with mixed presentation, recommending spine MRI only as a rule-out before psychiatric care.

**Reference diagnosis:** Tethered cord syndrome with conus/cauda equina involvement.

**Where Pro failed:**

- Anchored on trauma history, mutism, eye closure, and Bell's phenomenon as a functional syndrome.
- Treated sacral/autonomic findings as secondary or psychogenic rather than localizing red flags.
- Did not force a structural-neuro stop rule before finalizing conversion disorder.
- Mentioned spine MRI as a rule-out but still made the functional diagnosis primary despite absent anal wink, absent perineal sensation, and urinary retention.
- Did not retrieve tethered cord/conus/cauda equina presentations after trauma/scarring.

**Harness feature implemented:** `functional_neuro` preset. Before diagnosing functional neurologic disorder, conversion disorder, primary psychiatric disease, or trauma response, the harness forces retrieval of structural neurologic red flags and required spine imaging when sacral/autonomic/localizing signs are present.

**Good retrieval topics:**

- tethered cord syndrome urinary retention absent anal wink saddle anesthesia;
- conus medullaris cauda equina pediatric urinary retention perineal sensory loss;
- functional neurological disorder red flags urinary retention anal wink;
- post-traumatic tethered cord adhesions scarring diagnosis MRI;
- conversion disorder diagnosis after excluding structural neurologic disease.

**Template queries:**

- `tethered cord syndrome urinary retention absent anal wink perineal sensation MRI`
- `conus medullaris cauda equina syndrome saddle anesthesia urinary retention pediatric`
- `functional neurological disorder red flags bladder dysfunction anal wink`
- `post traumatic tethered spinal cord adhesions scarring case review`

**Harness implication:** Functional diagnoses should be treated as stop-rule diagnoses, not first-pass labels. If sacral, bladder, bowel, objective sensory-level, reflex, or prior spine/pelvic trauma clues exist, the model must retrieve structural mimics and required imaging before allowing a functional final answer.

## Case 12: Leptomeningeal Carcinomatosis Miscalled As Cervical Artery Dissection

**Prompt signal:** Woman with recent stage IV epithelial ovarian cancer, apparently in remission, developed a month of headaches with neck pain, nausea/vomiting, blurry vision, and repeated unrevealing evaluations. MRI brain/spine with gadolinium showed no leptomeningeal enhancement. CSF had mildly elevated protein and initial cytology was negative. A syncopal episode occurred during neck massage.

**Pro answer:** Cervical/vertebral artery dissection, recommending CTA or MRA of the head and neck.

**Reference diagnosis:** Leptomeningeal carcinomatosis from epithelial ovarian cancer.

**Where Pro failed:**

- Anchored on the temporally salient neck massage and syncope.
- Treated recent remission, normal CA-125/PET-CT, negative MRI, normal opening pressure, and first negative CSF cytology as too reassuring.
- Mentioned cytology false-negative risk but did not make it decision-controlling.
- Did not retrieve cancer-specific leptomeningeal metastasis presentations with headache/nausea/vomiting and minimal early exam findings.
- Did not require repeat CSF cytology with adequate volume/processing before closing on a nonmalignant vascular diagnosis.

**Harness feature implemented:** `cancer_neuro` preset. In patients with active, recent, or high-stage malignancy and new neurologic symptoms, the harness forces CNS relapse/leptomeningeal retrieval and repeat-CSF false-negative logic before benign headache, dissection, infection, or migraine closure.

**Good retrieval topics:**

- leptomeningeal carcinomatosis ovarian cancer headache negative MRI cytology;
- CSF cytology sensitivity leptomeningeal metastasis repeat lumbar puncture volume;
- leptomeningeal metastasis normal MRI initial negative cytology;
- ovarian cancer central nervous system leptomeningeal metastasis presentation;
- cancer patient headache neck pain leptomeningeal metastasis differential.

**Template queries:**

- `leptomeningeal carcinomatosis ovarian cancer negative MRI negative cytology repeat CSF`
- `CSF cytology sensitivity leptomeningeal metastasis repeat lumbar puncture volume`
- `leptomeningeal metastasis normal MRI initial negative cytology headache`
- `ovarian cancer leptomeningeal metastasis headache nausea vomiting`

**Harness implication:** In known-cancer neurologic presentations, negative first-pass tests should trigger a false-negative retrieval plan, not discharge the cancer hypothesis. The agent should explicitly state what repeat CSF cytology/flow/cell-block strategy or repeat imaging is needed before accepting a competing diagnosis.

## Case 13: Seronegative Autoimmune Encephalitis Mis-Specified As Anti-LGI1

**Prompt signal:** Older woman with fever/headache, seizures, bilateral medial temporal T2 hyperintensity, hyponatremia, faciobrachial dystonic seizures, negative infectious workup, negative NMDA/GABA-B/VGKC antibody panel, recurrent complex partial seizures progressing to super-refractory status epilepticus, and autonomic instability.

**Pro answer:** Anti-LGI1 limbic encephalitis, recommending immunotherapy and specific LGI1/CASPR2 antibody testing.

**Reference diagnosis:** Seronegative autoimmune encephalitis / probable autoimmune encephalitis.

**Where Pro failed:**

- Treated faciobrachial dystonic seizures and hyponatremia as essentially subtype-defining.
- Overstated "pathognomonic" LGI1 logic despite negative available antibody testing.
- Did not preserve the distinction between syndrome-level autoimmune encephalitis and antibody-subtype diagnosis.
- Did not retrieve seronegative/probable autoimmune encephalitis criteria.
- Underweighted severe refractory status epilepticus and autonomic instability as reasons to plan empiric and escalating immunotherapy without over-naming the antibody subtype.

**Harness feature implemented:** `autoimmune_encephalitis` preset. For suspected autoimmune encephalitis, the harness separates probable/seronegative syndrome diagnosis from antibody-subtype diagnosis and blocks named antibody closure unless antibody evidence or a highly specific syndrome pattern supports it.

**Good retrieval topics:**

- seronegative autoimmune encephalitis diagnostic criteria probable autoimmune encephalitis;
- LGI1 encephalitis faciobrachial dystonic seizures hyponatremia antibody negative;
- autoimmune encephalitis antibody negative status epilepticus immunotherapy escalation;
- VGKC complex negative LGI1 CASPR2 testing limitations;
- autoimmune encephalitis tumor screening seronegative refractory seizures.

**Template queries:**

- `seronegative autoimmune encephalitis diagnostic criteria probable autoimmune encephalitis`
- `LGI1 encephalitis faciobrachial dystonic seizures hyponatremia antibody negative`
- `autoimmune encephalitis antibody negative status epilepticus immunotherapy escalation`
- `VGKC complex negative LGI1 CASPR2 antibody testing limitation`

**Harness implication:** The final answer should not be more specific than the evidence. If antibody testing is negative or incomplete, the harness should allow "probable/seronegative autoimmune encephalitis" with a testing and immunotherapy plan rather than forcing a named subtype.

## Case 14: CVST With Empty Pro Answer

**Prompt signal:** Adult man with one day of headache followed by acute loss of consciousness and coma. Noncontrast CT showed no hemorrhage. MRI showed acute infarct-like lesions with restricted diffusion. Intracranial arterial MRA was normal, without large-vessel occlusion or stenosis.

**Pro answer:** Empty diagnosis, empty differential, empty next step.

**Reference diagnosis:** Cerebral venous sinus thrombosis. The next diagnostic step is venous imaging such as MRV or CTV.

**Where Pro failed:**

- Failed to produce a minimum emergency differential despite coma and acute infarct imaging.
- Did not apply a must-not-miss acute neurologic emergency checklist.
- Treated normal arterial MRA as a stopping point instead of a clue to check venous thrombosis.
- Did not retrieve CVST/CVT presentations with headache, coma/altered consciousness, venous infarcts, and normal arterial imaging.
- Did not state the immediate diagnostic next step: MRV/CTV.

**Harness feature implemented:** `acute_neuro_emergency` preset. For coma, acute loss of consciousness, severe headache, acute infarct, seizure/status, or abnormal emergency neuroimaging, the harness forbids empty output and forces a minimum emergency differential plus next diagnostic test.

**Good retrieval topics:**

- cerebral venous sinus thrombosis coma headache venous infarct MRV;
- acute infarct normal arterial MRA cerebral venous thrombosis;
- CVST altered consciousness restricted diffusion diagnosis CTV MRV;
- coma headache no hemorrhage normal MRA venous sinus thrombosis.

**Template queries:**

- `cerebral venous sinus thrombosis coma headache venous infarct MRV`
- `acute infarct normal arterial MRA cerebral venous thrombosis`
- `CVST altered consciousness restricted diffusion diagnosis CTV MRV`
- `coma headache no hemorrhage normal MRA venous sinus thrombosis`

**Harness implication:** Empty output is itself a failure mode. For high-acuity neurology, the controller should force a minimum structured differential and next test even when confidence is low. In infarct-like lesions with normal arterial MRA, venous imaging must be explicitly considered.

## Case 15: Actinomycotic Spine Infection Miscalled As Brucellar Spondylitis

**Prompt signal:** Woman with 6 months of progressive low back pain, radicular symptoms, neurogenic claudication, weight loss, paraparesis, L5-S1 sensory loss, MRI spondylodiscitis with paraspinal/epidural abscess, destructive endplates, a mottled lattice-like vertebral appearance with small intercommunicating cystic lucencies, purulent aspirate, negative AFB stain, and negative TB PCR.

**Pro answer:** Brucellar spondylitis, recommending Brucella serology/culture and empiric anti-brucellosis therapy.

**Reference diagnosis:** Actinomycotic spinal infection / vertebral actinomycosis.

**Where Pro failed:**

- Treated a distinctive imaging description as brucella-specific without microbiology support.
- Did not retrieve actinomycotic spine infection imaging/pathology clues.
- Did not require anaerobic culture or histopathology for filamentous Gram-positive organisms/sulfur granules.
- Underweighted purulent abscess plus negative AFB/TB PCR as a trigger for broader culture strategy.
- Did not retrieve prolonged penicillin-based therapy and surgical drainage/decompression implications for actinomycosis.

**Harness feature implemented:** `infection_microbiology` preset. For indolent infection, abscess, osteomyelitis, spondylodiscitis, culture-negative infection, or unusual imaging patterns, the harness forces pathogen-specific microbiology and treatment-duration retrieval before naming an organism.

**Good retrieval topics:**

- spinal actinomycosis spondylodiscitis paraspinal abscess diagnosis;
- vertebral actinomycosis MRI cystic lucencies histopathology;
- Actinomyces osteomyelitis anaerobic culture sulfur granules treatment duration;
- brucellar spondylitis versus actinomycotic spinal infection differential;
- culture negative spondylodiscitis anaerobic fungal AFB Brucella workup.

**Template queries:**

- `spinal actinomycosis spondylodiscitis paraspinal abscess diagnosis`
- `vertebral actinomycosis MRI cystic lucencies histopathology`
- `Actinomyces osteomyelitis anaerobic culture sulfur granules penicillin duration`
- `brucellar spondylitis versus actinomycotic spinal infection differential`
- `culture negative spondylodiscitis anaerobic fungal AFB Brucella workup`

**Harness implication:** For indolent spinal infection, the agent should not commit to a pathogen from imaging alone. It needs a microbiology plan, a pathogen discriminator table, and a treatment-duration plan because the management changes substantially by organism.

## Case 16: Vaginal Leiomyosarcoma Miscalled As Recurrent Leiomyoma

**Prompt signal:** Reproductive-age woman with a many-year recurrent vaginal wall mass, persistent pain, gradual enlargement to the introitus, two prior resections without histology, and a solid mass around 6 cm at an unusual site.

**Pro answer:** Recurrent vaginal leiomyoma, recommending excision with histopathology.

**Reference diagnosis:** Primary vaginal leiomyosarcoma.

**Where Pro failed:**

- Treated recurrence as incomplete benign excision rather than a malignancy red flag.
- Underweighted missing prior pathology after repeated resections.
- Underweighted pain, size, progressive enlargement, recurrence, and unusual location.
- Did not retrieve vaginal smooth-muscle tumor malignancy criteria.
- Did not force local staging, tissue diagnosis, IHC, mitotic/necrosis/atypia criteria, and margin planning before benign closure.

**Harness feature implemented:** `mass_malignancy` preset. For recurrent, enlarging, painful, deep, unusual-site, or previously excised masses without histology, the harness forces malignancy red flags and tissue-diagnosis planning before accepting leiomyoma, fibroma, schwannoma, polyp, or another benign mass.

**Good retrieval topics:**

- recurrent vaginal mass leiomyoma versus leiomyosarcoma;
- vaginal smooth-muscle tumor pathology criteria;
- recurrent mass without prior histology malignancy red flags;
- soft-tissue mass biopsy, staging imaging, IHC, and margin planning;
- leiomyoma versus leiomyosarcoma mitotic activity, necrosis, and atypia.

**Template queries:**

- `vaginal leiomyosarcoma recurrent vaginal mass leiomyoma differential`
- `vaginal smooth muscle tumor leiomyoma leiomyosarcoma pathology criteria mitotic necrosis atypia`
- `recurrent vaginal mass no prior histology malignancy red flags`
- `primary vaginal leiomyosarcoma diagnosis MRI biopsy IHC management`

**Harness implication:** A benign mass label is not stable when the lesion is recurrent, painful, enlarging, large, in an unusual site, or lacks prior histology. The controller should require a red-flag table and tissue plan before allowing benign closure.

## Case 17: Pericardial Angiosarcoma Miscalled As Primary Cardiac Lymphoma

**Prompt signal:** Middle-aged man with apparent pericarditis that recurred despite anti-inflammatory therapy, rapidly reaccumulating hemorrhagic pericardial effusion, negative cytology and cultures, nodular pericardial thickening, recurrent pleural effusion, and a heterogeneously enhancing pericardial mass on CT/MRI.

**Pro answer:** Primary cardiac lymphoma, recommending percutaneous image-guided core biopsy.

**Reference diagnosis:** Pericardial angiosarcoma.

**Where Pro failed:**

- Treated imaging signal and pericardial involvement as lymphoma-specific rather than comparing cardiac tumor classes.
- Underweighted recurrent hemorrhagic effusion and rapid reaccumulation as malignant vascular-tumor red flags.
- Did not retrieve limits of pericardial fluid cytology for cardiac sarcomas.
- Let negative cytology/cultures reduce malignancy probability too much despite a persistent enhancing mass.
- Did not retrieve cardiac angiosarcoma imaging patterns, endothelial-marker IHC, or surgical biopsy/resection strategy.

**Harness feature implemented:** `cardiac_pericardial_mass` preset. For recurrent or hemorrhagic pericardial effusion, nodular pericardial thickening, or an enhancing cardiac/pericardial mass, the harness forces cardiac tumor discriminator retrieval before inflammatory, uremic, infectious, or lymphoma closure.

**Good retrieval topics:**

- recurrent hemorrhagic pericardial effusion cardiac tumor differential;
- pericardial angiosarcoma versus primary cardiac lymphoma imaging;
- pericardial fluid cytology false negative cardiac sarcoma;
- cardiac angiosarcoma biopsy resection histopathology IHC endothelial markers;
- nodular pericardial thickening heterogeneously enhancing pericardial mass differential.

**Template queries:**

- `recurrent hemorrhagic pericardial effusion enhancing pericardial mass differential`
- `pericardial angiosarcoma primary cardiac lymphoma imaging cardiac MRI`
- `cardiac sarcoma pericardial fluid cytology negative biopsy diagnosis`
- `pericardial angiosarcoma histopathology CD31 CD34 ERG surgical biopsy`

**Harness implication:** In cardiac/pericardial masses, the controller should treat negative fluid cytology as a caveat, not a stop signal. It should require a tumor discriminator table and tissue plan before accepting lymphoma, inflammatory pericarditis, infection, or uremic pericarditis.

## Case 18: Mammary Stromal Sarcoma Miscalled As Generic High-Grade Sarcoma

**Prompt signal:** Older woman with rapidly growing breast mass, irregular solid imaging, core biopsy showing a pleomorphic spindle-cell neoplasm with brisk mitoses, no epithelial/ductal elements, vimentin positivity, and negative cytokeratin/p63, with additional immunostains pending.

**Pro answer:** Primary high-grade breast sarcoma, most consistent with undifferentiated pleomorphic sarcoma, with a broad IHC recommendation.

**Reference diagnosis:** Mammary stromal sarcoma, CD10-positive.

**Where Pro failed:**

- Correctly recognized a malignant spindle-cell process but stopped at a generic high-grade sarcoma/UPS bucket.
- Did not retrieve the organ-specific breast spindle-cell differential.
- Missed that negative cytokeratin/p63 shifts away from metaplastic carcinoma but does not complete subtype classification.
- Did not force CD10, CD34, desmin, and SMA as the key marker set for mammary stromal sarcoma versus phyllodes tumor and leiomyosarcoma.
- Treated the pending IHC panel as generic exclusion work rather than the decision point for the final diagnosis and management.

**Harness feature implemented:** `spindle_cell_pathology` preset. For spindle-cell, pleomorphic, sarcomatoid, or high-grade mesenchymal tumors, the harness prevents generic sarcoma/UPS closure until organ-specific entities and subtype markers have been retrieved.

**Good retrieval topics:**

- breast spindle-cell tumor differential CD10 CD34 desmin SMA;
- mammary stromal sarcoma versus phyllodes tumor IHC;
- metaplastic carcinoma versus primary breast sarcoma cytokeratin p63;
- CD10-positive mammary stromal sarcoma diagnostic criteria;
- high-grade spindle-cell breast lesion immunohistochemistry panel.

**Template queries:**

- `breast spindle cell neoplasm CD10 CD34 desmin SMA differential`
- `mammary stromal sarcoma CD10 positive phyllodes leiomyosarcoma immunohistochemistry`
- `metaplastic carcinoma versus breast sarcoma cytokeratin p63 spindle cell`
- `undifferentiated pleomorphic sarcoma breast mammary stromal sarcoma markers`

**Harness implication:** Once a case is in the spindle-cell/sarcoma lane, the controller should not accept a broad category if site-specific subtype markers are pending or available. The correct tool step is a marker table, not another broad differential.

## Case 19: Intraosseous Angiosarcoma Miscalled As Telangiectatic Osteosarcoma

**Prompt signal:** Older adult with painful lytic expansile distal femur lesion, vascular history, nondiagnostic needle biopsy, open biopsy showing blood-filled cystic spaces resembling aneurysmal bone cyst, benign-appearing routine histology, curettage/grafting followed by rapid recurrence, progressive osteolysis, and new soft-tissue mass.

**Pro answer:** Telangiectatic osteosarcoma, recommending repeat biopsy, staging, orthopedic oncology evaluation, and possible neoadjuvant chemotherapy/wide resection.

**Reference diagnosis:** Intraosseous angiosarcoma with secondary aneurysmal bone cyst.

**Where Pro failed:**

- Recognized benign ABC was unsafe but jumped to the more familiar ABC-like malignant mimic, telangiectatic osteosarcoma.
- Underweighted older age as a trigger for secondary ABC due to an underlying neoplasm.
- Treated vascular history as likely incidental instead of retrieving vascular tumor/angiosarcoma associations and endothelial-marker strategy.
- Did not require endothelial IHC such as CD31, CD34, ERG, or FLI1.
- Did not explicitly compare osteoid/matrix evidence for telangiectatic osteosarcoma against endothelial differentiation for angiosarcoma.

**Harness feature implemented:** `bone_vascular_tumor` preset. For lytic, expansile, cystic, hemorrhagic, or ABC-like bone lesions in older adults or rapidly recurrent lesions, the harness forces secondary-ABC and malignant vascular tumor discriminator retrieval before benign ABC or osteosarcoma closure.

**Good retrieval topics:**

- secondary aneurysmal bone cyst older adult malignant bone tumor;
- intraosseous angiosarcoma aneurysmal bone cyst mimic;
- telangiectatic osteosarcoma versus angiosarcoma CD31 ERG;
- ABC-like bone lesion rapid recurrence soft tissue mass differential;
- vascular bone tumor endothelial markers CD31 CD34 ERG FLI1.

**Template queries:**

- `secondary aneurysmal bone cyst older adult malignant bone tumor differential`
- `intraosseous angiosarcoma aneurysmal bone cyst mimic CD31 ERG`
- `telangiectatic osteosarcoma versus angiosarcoma bone endothelial markers`
- `ABC-like lytic bone lesion rapid recurrence soft tissue mass older adult`

**Harness implication:** Benign-looking routine histology should be challenged when age and clinical course are discordant. For ABC-like lesions in older adults or rapidly recurrent lesions, the controller needs a secondary-lesion table and endothelial-marker plan.

## Case 20: Gnathic Osteosarcoma Miscalled As Primary Bone Lymphoma

**Prompt signal:** Young adult with rapid painful mandibular swelling, ill-defined radiolucent mandibular lesion, loss of lamina dura, widened periodontal ligament space without odontogenic source, cortical destruction, small soft-tissue mass, no fever/systemic infection signs, no lymphadenopathy, and no distant metastases.

**Pro answer:** Primary bone lymphoma, recommending incisional biopsy.

**Reference diagnosis:** Osteosarcoma of the jaw, fibroblastic subtype.

**Where Pro failed:**

- Overweighted absence of sunburst periosteal reaction, Codman triangle, and intralesional calcifications.
- Treated widened periodontal ligament space as lymphoma-supporting rather than retrieving jaw osteosarcoma radiographic clues.
- Did not use lack of odontogenic source, infection signs, lymphadenopathy, or systemic lymphoma context to lower lymphoma confidence.
- Did not retrieve gnathic osteosarcoma presentations, where classic long-bone osteosarcoma signs may be absent.
- Recommended biopsy correctly but did not specify osteoid/matrix assessment or relevant IHC/molecular workup.

**Harness feature implemented:** `gnathic_bone_tumor` preset. For jaw/mandible/maxilla lesions with rapid pain, swelling, cortical destruction, widened periodontal ligament space, loss of lamina dura, or soft-tissue mass, the harness forces gnathic osteosarcoma and odontogenic/infectious/lymphoma mimic retrieval before final diagnosis.

**Good retrieval topics:**

- gnathic osteosarcoma widened periodontal ligament space loss of lamina dura;
- mandibular osteosarcoma versus primary bone lymphoma radiographic features;
- jaw lytic lesion cortical destruction soft tissue mass differential;
- osteosarcoma jaw absence of sunburst Codman triangle;
- mandibular malignancy no odontogenic source biopsy osteoid matrix.

**Template queries:**

- `gnathic osteosarcoma widened periodontal ligament space loss lamina dura`
- `mandibular osteosarcoma primary bone lymphoma radiographic differential`
- `jaw lytic lesion cortical destruction soft tissue mass no odontogenic source`
- `osteosarcoma jaw absent sunburst Codman triangle diagnosis`

**Harness implication:** Site-specific imaging knowledge matters. The controller should not let absence of classic long-bone signs rule out gnathic osteosarcoma when jaw-specific clues are present.

## Case 21: Middle-Ear Neuroendocrine Tumor Miscalled As Glomus Tympanicum

**Prompt signal:** Young adult with several months of aural fullness and otalgia, reddish retrotympanic posterosuperior middle-ear mass, no retraction pockets, subnormal audiometry, CT showing a well-defined soft-tissue mass near the ossicles, and no bone erosion.

**Pro answer:** Glomus tympanicum, recommending high-resolution MRI to assess vascularity.

**Reference diagnosis:** Adenomatous neuroendocrine tumor of the middle ear.

**Where Pro failed:**

- Anchored on “reddish retrotympanic mass” as a vascular paraganglioma cue.
- Underweighted absence of pulsatile tinnitus and absence of bone erosion.
- Did not retrieve middle-ear adenomatous/neuroendocrine tumor patterns.
- Did not compare cholesteatoma, glomus tympanicum, carcinoma, schwannoma, and adenomatous neuroendocrine tumor by otoscopy/CT features.
- Did not force definitive surgical excision and IHC markers such as synaptophysin, chromogranin, cytokeratin/EMA, and Ki-67.

**Harness feature implemented:** `middle_ear_mass` preset. For retrotympanic or middle-ear masses, the harness forces site-specific otologic imaging and IHC discriminator retrieval before glomus, cholesteatoma, infection, schwannoma, carcinoma, or adenomatous neuroendocrine tumor closure.

**Good retrieval topics:**

- middle ear adenomatous neuroendocrine tumor glomus tympanicum differential;
- reddish retrotympanic mass no pulsatile tinnitus no bone erosion;
- middle ear carcinoid adenoma synaptophysin chromogranin cytokeratin;
- glomus tympanicum versus middle ear adenoma CT bone erosion vascularity;
- retrotympanic mass no retraction pocket cholesteatoma differential.

**Template queries:**

- `middle ear adenomatous neuroendocrine tumor glomus tympanicum differential`
- `reddish retrotympanic mass no pulsatile tinnitus no bone erosion`
- `middle ear carcinoid adenoma synaptophysin chromogranin cytokeratin`
- `glomus tympanicum versus middle ear adenoma CT bone erosion vascularity`

**Harness implication:** A single visual cue like “reddish” should not determine middle-ear mass diagnosis. The controller needs a site-specific table: vascular symptoms, retraction pocket, bone erosion, ossicular relationship, recurrence behavior, and neuroendocrine IHC.

## Case 22: Penile Cutaneous Horn Miscalled As Keratotic Balanitis

**Prompt signal:** Uncircumcised male with treatment-resistant hyperkeratotic/verrucous penile lesion, no response to wart-directed therapies, and histology dominated by massive ortho/parakeratotic hyperkeratosis without obvious malignant change in sampled tissue.

**Pro answer:** Pseudoepitheliomatous keratotic and micaceous balanitis, recommending excision or laser ablation with histology.

**Reference diagnosis:** Penile cutaneous horn.

**Where Pro failed:**

- Treated hyperkeratosis as a named balanitis variant rather than using morphology-first dermatology retrieval.
- Underweighted horn-like/cornu cutaneum morphology.
- Did not separate surface keratin diagnosis from the pathology at the base.
- Did not emphasize that malignant or premalignant disease can be present at the base even when superficial keratin is benign.
- Partially recommended tissue confirmation, but not the specific wide/deep excision and base-histology management logic.

**Harness feature implemented:** `keratotic_skin_lesion` preset. For hyperkeratotic, verrucous, horn-like, micaceous, or treatment-resistant genital/skin lesions, the harness forces morphology, base histology, and malignancy-risk retrieval before closure.

**Good retrieval topics:**

- penile cutaneous horn pseudoepitheliomatous keratotic balanitis differential;
- cutaneous horn base histology squamous cell carcinoma risk;
- hyperkeratotic penile lesion verrucous carcinoma cutaneous horn;
- genital cutaneous horn management wide excision base histopathology.

**Template queries:**

- `penile cutaneous horn pseudoepitheliomatous keratotic balanitis differential`
- `cutaneous horn base histology squamous cell carcinoma risk`
- `hyperkeratotic penile lesion verrucous carcinoma cutaneous horn`
- `genital cutaneous horn wide excision base histopathology`

**Harness implication:** Dermatologic surface morphology can be misleading unless the base is sampled. The controller should require explicit “what is the keratin projection” and “what is at the base” fields before final diagnosis and management.

## Case 23: Melanoma Masseter Metastasis Miscalled As MPNST

**Prompt signal:** Patient with neurofibromatosis/lipomatosis and prior melanoma develops a rapidly growing deep mass in an unusual head-and-neck muscle site, with constitutional symptoms and back/spine symptoms concerning for systemic spread.

**Pro answer:** Malignant peripheral nerve sheath tumor with suspected spinal metastases, recommending imaging and biopsy.

**Reference diagnosis:** Metastatic malignant melanoma to the masseter.

**Where Pro failed:**

- Overweighted NF1 as a strong MPNST predisposition.
- Underweighted prior melanoma history and the possibility of late/unusual-site metastasis.
- Did not force a prior-cancer recurrence-pattern retrieval step.
- Did not require an IHC plan that would separate melanoma metastasis from MPNST and other sarcomas.
- Included biopsy and staging logic, but the diagnostic framing led to the wrong disease-specific workup.

**Harness feature implemented:** `prior_cancer_mass` preset. For new, rapidly growing, deep, unusual-site, or symptomatic masses in a patient with prior malignancy, the harness forces metastatic recurrence retrieval before new-primary or syndrome-associated tumor closure.

**Good retrieval topics:**

- metastatic melanoma masseter muscle soft tissue metastasis;
- melanoma metastasis versus malignant peripheral nerve sheath tumor IHC;
- NF1 MPNST versus metastatic melanoma differential;
- late melanoma recurrence unusual soft tissue metastasis;
- S100 SOX10 Melan-A HMB-45 melanoma metastasis markers.

**Template queries:**

- `metastatic melanoma masseter muscle soft tissue metastasis`
- `melanoma metastasis versus MPNST immunohistochemistry SOX10 S100`
- `NF1 malignant peripheral nerve sheath tumor metastatic melanoma differential`
- `late melanoma recurrence unusual soft tissue metastasis Melan-A HMB-45`

**Harness implication:** A strong risk factor should become a comparison axis, not an anchor. Prior malignancy should trigger metastasis-pattern and marker retrieval whenever a new unusual mass appears.

## Case 24: Benign Lipomatous Tumor Miscalled As Well-Differentiated Liposarcoma

**Prompt signal:** Large retroperitoneal/iliopsoas fatty mass with thin septa and no solid enhancing component; biopsy showed mature adipocytes with minimal variation, no nuclear atypia, no lipoblasts, delicate fibrous bands, brown fat cells, and equivocal MDM2 IHC.

**Pro answer:** Atypical lipomatous tumor / well-differentiated liposarcoma, recommending MDM2 FISH.

**Reference diagnosis:** Retroperitoneal intramuscular lipoma with hibernoma component, confirmed after negative MDM2 amplification.

**Where Pro failed:**

- Overweighted large size and retroperitoneal location.
- Correctly identified MDM2 FISH as the right next test but treated malignancy as already likely.
- Underweighted benign morphology: mature adipocytes, no atypia, no lipoblasts, thin septa, no solid enhancing component.
- Did not retrieve hibernoma/brown-fat mimic features.
- Did not include the rule that negative MDM2 amplification supports benign diagnosis when morphology fits.

**Harness feature implemented:** `lipomatous_tumor_molecular` preset. For large/deep/retroperitoneal/intramuscular fatty tumors, the harness forces MDM2/CDK4 interpretation, FISH status, benign morphology, and hibernoma clues before ALT/WDL closure.

**Good retrieval topics:**

- retroperitoneal lipoma versus well differentiated liposarcoma MDM2 FISH;
- MDM2 immunohistochemistry equivocal FISH lipomatous tumor;
- lipoma-like hibernoma brown fat cells UCP1 differential;
- intramuscular lipoma retroperitoneal no atypia no lipoblasts;
- ALT WDL versus lipoma imaging septa solid enhancing component.

**Template queries:**

- `retroperitoneal lipoma well differentiated liposarcoma MDM2 FISH`
- `equivocal MDM2 immunohistochemistry lipomatous tumor FISH interpretation`
- `lipoma-like hibernoma brown fat cells UCP1 differential`
- `ALT WDL versus lipoma no atypia no lipoblasts thin septa`

**Harness implication:** Correctly ordering the molecular test is not enough. The controller must require bidirectional interpretation: what positive MDM2 amplification would mean, and what negative amplification means when benign morphology is present.

## Case 25: Neutropenic Necrotizing Fasciitis Miscalled As Mucormycosis

**Prompt signal:** AML induction chemotherapy with profound neutropenia, neutropenic fever, minor trauma followed by rapidly evolving hematoma, blistering, tense skin, central necrosis, rising CRP, persistent neutropenia, no gas or abscess on imaging, and punch biopsy showing necrosis without organisms or inflammatory cells.

**Pro answer:** Cutaneous mucormycosis, recommending amphotericin and urgent debridement.

**Reference diagnosis:** Necrotizing fasciitis / necrotizing soft-tissue infection.

**Where Pro failed:**

- Interpreted paucicellular biopsy as evidence for angioinvasive fungal disease instead of neutropenic blunting.
- Overweighted absent gas/abscess, fever, leukocytosis, and pain despite immunocompromised host caveats.
- Did not retrieve necrotizing fasciitis presentations in neutropenia/AML chemotherapy.
- Did not emphasize that LRINEC and usual inflammatory signs are unreliable in severe neutropenia.
- Included source control, but the diagnosis and antimicrobial framing were wrong.

**Harness feature implemented:** `immunocompromised_necrotizing_infection` preset. For rapidly progressive soft-tissue necrosis in neutropenic, chemotherapy, AML, transplant, diabetic, or otherwise immunocompromised patients, the harness forces blunted-sign caveats and urgent surgical exploration/source-control logic before fungal-only closure.

**Good retrieval topics:**

- neutropenic necrotizing fasciitis absence of inflammatory cells biopsy;
- AML chemotherapy necrotizing soft tissue infection no gas;
- necrotizing fasciitis neutropenia LRINEC unreliable;
- cutaneous mucormycosis versus necrotizing fasciitis immunocompromised;
- monomicrobial necrotizing fasciitis no gas imaging.

**Template queries:**

- `neutropenic necrotizing fasciitis paucicellular biopsy no inflammatory cells`
- `AML chemotherapy necrotizing fasciitis no gas imaging`
- `necrotizing fasciitis neutropenia LRINEC unreliable`
- `cutaneous mucormycosis versus necrotizing fasciitis immunocompromised`

**Harness implication:** In immunocompromised hosts, absence of expected inflammatory findings is often non-informative. The controller should force a caveat table for “negative” findings before ruling out necrotizing infection.

## Case 26: Maxillary Osteomyelitis Miscalled As Periapical Abscess

**Prompt signal:** Chronic painful anterior maxillary lesion with purulent gingival fistula, tooth mobility/tenderness, smoking history, prior blunt facial trauma at the same site, no recent dental procedure or obvious odontogenic source, and no systemic immunosuppression.

**Pro answer:** Chronic periapical abscess with intraoral sinus tract from pulpal necrosis, recommending periapical radiograph.

**Reference diagnosis:** Chronic suppurative osteomyelitis of the maxilla, likely trauma-related.

**Where Pro failed:**

- Anchored on tooth tenderness and fistula as odontogenic abscess.
- Underweighted the absence of an odontogenic source or recent dental procedure.
- Did not use prior blunt trauma plus smoking as a bone-infection predisposition.
- Did not retrieve chronic maxillary osteomyelitis/sequestrum patterns.
- Recommended a periapical film rather than panoramic radiograph or cone-beam CT to assess bone destruction and sequestrum.

**Harness feature implemented:** `maxillofacial_osteomyelitis` preset. For chronic draining fistula, purulence, tooth mobility, maxillary/mandibular pain, or prior facial trauma, the harness forces jaw osteomyelitis versus odontogenic abscess retrieval and sequestrum imaging planning.

**Good retrieval topics:**

- chronic suppurative osteomyelitis maxilla trauma fistula sequestrum;
- periapical abscess versus maxillary osteomyelitis no odontogenic source;
- panoramic radiograph cone beam CT sequestrum maxillary osteomyelitis;
- facial trauma chronic osteomyelitis maxilla tooth mobility purulent discharge.

**Template queries:**

- `chronic suppurative osteomyelitis maxilla trauma fistula sequestrum`
- `periapical abscess versus maxillary osteomyelitis no odontogenic source`
- `panoramic radiograph cone beam CT sequestrum maxillary osteomyelitis`
- `facial trauma chronic osteomyelitis maxilla tooth mobility purulent discharge`

**Harness implication:** Draining dental-region fistulas need source localization. The controller should not accept a periapical abscess unless an odontogenic source is present or bone-level osteomyelitis has been evaluated with appropriate imaging.

## Case 27: Tuberculous Sarcoidosis Overlap Miscalled As Sarcoidosis

**Prompt signal:** Adult man with optic disc granulomatous-appearing lesion, bilateral epididymal disease with azoospermia, systemic symptoms, hilar/paratracheal lymphadenopathy, elevated ACE, strong Mantoux positivity, recent household TB exposure, negative IGRA and microbiology, and declined biopsy.

**Pro answer:** Sarcoidosis, recommending mediastinal lymph-node biopsy if possible and corticosteroids if tissue was declined.

**Reference diagnosis:** Tuberculous sarcoidosis / TB-sarcoid overlap, with combined anti-tuberculosis therapy and corticosteroids.

**Where Pro failed:**

- Overtrusted negative IGRA, sputum, urine, and culture results as excluding active TB.
- Treated genitourinary/epididymal disease and azoospermia as sarcoidosis-compatible without retrieving GU tuberculosis discriminators.
- Did not build a treatment decision table for biopsy declined/unavailable.
- Recommended steroid-only fallback despite active TB risk signals.
- Missed the overlap category where sarcoid-like and tuberculosis features can coexist without microbiologic proof.

**Harness feature implemented:** `granulomatous_overlap` preset. For granulomatous eye, lymph node, pulmonary, genitourinary, skin, or systemic disease, the harness forces sarcoidosis/TB/fungal/syphilis/Bartonella/overlap retrieval and negative-test caveats before single-cause closure.

**Good retrieval topics:**

- sarcoidosis tuberculosis overlap with ocular and genitourinary granulomatous disease;
- negative IGRA in active extrapulmonary or genitourinary tuberculosis;
- epididymitis, azoospermia, and granulomatous systemic disease differential;
- corticosteroids versus anti-TB therapy versus combined therapy when biopsy is declined.

**Template queries:**

- `sarcoidosis tuberculosis overlap optic disc granuloma epididymitis`
- `negative IGRA active tuberculosis extrapulmonary genitourinary TB`
- `tuberculous epididymitis azoospermia sarcoidosis differential`
- `sarcoidosis tuberculosis overlap corticosteroids anti tuberculosis therapy`

**Harness implication:** Granulomatous disease needs a negative-test caveat table and a treatment-risk table. Steroids alone should be blocked when TB exposure, Mantoux positivity, GU disease, systemic symptoms, or infertility clues keep tuberculosis active in the differential.

## Case 28: Uterine Epithelioid Leiomyosarcoma Produced Empty Output

**Prompt signal:** Postmenopausal bleeding, progressive abdominal distension, weight loss, a large heterogeneous hypervascular uterine corpus mass, and small-biopsy histology showing epithelioid/polygonal cells with mild atypia and low mitotic activity without a spindle-cell component.

**Pro answer:** Empty output due to API/model failure.

**Reference diagnosis:** Uterine epithelioid leiomyosarcoma. The key next step was an IHC panel separating smooth-muscle tumor from PEComa, UTROSCT, carcinoma, melanoma, and sex-cord stromal mimics.

**Where Pro failed:**

- Returned no diagnosis, next step, or reasoning artifact.
- Had no pathology-specific fallback for small-biopsy uterine tumor cases.
- Did not force a minimum mimic panel when the morphology was broad and the clinical context was malignant.
- Needed an explicit rule that low mitoses or absent spindle component on limited tissue does not end the malignancy workup.

**Harness feature implemented:** `gynecologic_epithelioid_tumor` preset. For gynecologic epithelioid tumors on small biopsy, the harness forces small-biopsy caveats, smooth-muscle/PEComa/UTROSCT/carcinoma/melanoma mimic retrieval, and a minimum IHC plan.

**Good retrieval topics:**

- uterine epithelioid leiomyosarcoma small biopsy differential;
- PEComa versus epithelioid leiomyosarcoma immunohistochemistry;
- UTROSCT versus epithelioid smooth muscle tumor markers;
- low mitotic activity epithelioid uterine leiomyosarcoma diagnosis.

**Template queries:**

- `uterine epithelioid leiomyosarcoma small biopsy differential desmin SMA WT1`
- `PEComa versus epithelioid leiomyosarcoma HMB-45 Melan-A desmin SMA`
- `UTROSCT epithelioid leiomyosarcoma inhibin calretinin WT1 differential`
- `epithelioid uterine smooth muscle tumor low mitotic activity malignancy criteria`

**Harness implication:** Empty output is not neutral. For pathology-heavy cases, the controller should recover by producing a minimum differential and required IHC panel, especially when limited biopsy under-samples a clinically aggressive mass.

## Case 29: Sellar Xanthogranuloma Miscalled As Craniopharyngioma

**Prompt signal:** Adult woman with cystic-solid sellar/suprasellar mass, T1/T2 hyperintense cystic contents, T2-hypointense mural nodule, optic chiasm compression with visual-field deficits, and preserved pituitary function.

**Pro answer:** Adamantinomatous craniopharyngioma, recommending transsphenoidal resection.

**Reference diagnosis:** Sellar xanthogranuloma. The key next step was maximal safe resection with histopathologic confirmation and endocrine/imaging follow-up.

**Where Pro failed:**

- Anchored on cystic-solid sellar mass plus mural nodule as craniopharyngioma.
- Treated possible calcification as decisive without requiring CT or histology.
- Did not retrieve xanthogranuloma/Rathke-related cholesterol/hemorrhage discriminators.
- Did not include histology expectations: foamy macrophages, cholesterol clefts, hemosiderin, giant cells, and chronic inflammation.
- Recommended surgery but missed the disease-specific diagnostic framing and follow-up needs.

**Harness feature implemented:** `sellar_xanthogranuloma` preset. For cystic-solid sellar masses, the harness forces xanthogranuloma/Rathke/craniopharyngioma/adenoma-apoplexy discriminators, histology plan, surgical approach, postoperative hormone assessment, and MRI follow-up.

**Good retrieval topics:**

- sellar xanthogranuloma versus craniopharyngioma MRI;
- Rathke cleft cyst xanthogranuloma cholesterol clefts hemosiderin;
- cystic sellar mass T1 T2 hyperintense differential;
- sellar xanthogranuloma management endocrine follow-up.

**Template queries:**

- `sellar xanthogranuloma craniopharyngioma MRI T1 T2 hyperintense cyst`
- `Rathke cleft cyst xanthogranuloma cholesterol clefts hemosiderin foamy macrophages`
- `cystic solid sellar mass mural nodule xanthogranuloma differential`
- `sellar xanthogranuloma surgical resection hormone replacement follow-up`

**Harness implication:** Sellar mass diagnosis cannot stop at anatomy plus a presumed mural nodule. The controller needs a cyst-content/histology discriminator table and must preserve postoperative endocrine follow-up in the management answer.

## Case 30: Temporal-Bone Xanthogranulomatous Osteomyelitis Miscalled As SCC

**Prompt signal:** Older adult with chronic unilateral ear discharge, deep ear pain, mixed hearing loss, granulation tissue filling the external auditory canal, aggressive lytic temporal-bone/EAC destruction, no diabetes or immunosuppression, no facial palsy, and normal CBC/ESR/CRP.

**Pro answer:** SCC of the external auditory canal, recommending biopsy.

**Reference diagnosis:** Xanthogranulomatous osteomyelitis of the temporal bone. The next step was incisional biopsy/debridement histopathology to rule out malignancy and establish tissue diagnosis.

**Where Pro failed:**

- Correctly identified biopsy as the next step but prematurely named SCC as most likely.
- Overtrusted normal inflammatory markers and lack of diabetes/immunosuppression as arguing against inflammatory osteomyelitis.
- Treated lytic destruction and granulation tissue as malignancy-specific.
- Did not retrieve rare xanthogranulomatous osteomyelitis and foamy-histiocyte pathology discriminators.
- Did not state that the biopsy result should keep both malignancy and inflammatory mimics open until tissue is read.

**Harness feature implemented:** `temporal_bone_inflammatory_mass` preset. For destructive EAC/temporal-bone masses, the harness forces SCC, malignant otitis externa/skull-base osteomyelitis, cholesteatoma, GPA, and xanthogranulomatous osteomyelitis comparison before malignancy closure.

**Good retrieval topics:**

- xanthogranulomatous osteomyelitis temporal bone external auditory canal;
- external auditory canal SCC versus osteomyelitis granulation tissue lytic bone;
- temporal bone osteomyelitis normal ESR CRP immunocompetent;
- foamy histiocytes xanthogranulomatous inflammation bone biopsy.

**Template queries:**

- `xanthogranulomatous osteomyelitis temporal bone external auditory canal`
- `external auditory canal squamous cell carcinoma versus osteomyelitis granulation tissue lytic bone`
- `temporal bone osteomyelitis normal ESR CRP immunocompetent`
- `foamy histiocytes xanthogranulomatous inflammation bone biopsy malignancy mimic`

**Harness implication:** Recommending the right biopsy is only half the job. The controller should keep “diagnosis pending tissue” explicit when malignancy and inflammatory bone destruction overlap, and it should force histology/culture interpretation rather than letting imaging severity settle the diagnosis.

## Cross-Case Failure Pattern

DeepSeek Pro tended to:

- anchor on a salient familiar diagnosis;
- overinterpret one high-salience feature as confirmatory;
- fail to retrieve discriminator knowledge;
- accept preliminary pathology/cytology labels without lineage verification;
- treat steroid response or lesion regression as excluding malignancy;
- let exposure history override syndrome phenotype without route/incubation/phenotype support;
- demote cancer relapse because first MRI/cytology/tumor markers are negative;
- over-specify named autoimmune encephalitis antibody subtypes from partial clinical patterns;
- return empty output in high-acuity neurologic emergencies;
- name infectious pathogens from imaging alone without microbiology/pathology support;
- close on benign mass recurrence despite size, pain, recurrence, unusual site, or missing prior histology;
- overfit cardiac/pericardial masses to lymphoma or pericarditis without checking hemorrhagic-effusion and cytology false-negative caveats;
- stop at generic spindle-cell sarcoma/UPS instead of retrieving organ-specific subtype markers;
- accept familiar bone tumor categories before checking age/course discordance and marker-defined vascular mimics;
- miss site-specific radiographic signs by applying generic long-bone or generic lymphoma priors;
- anchor on a single anatomic visual cue without retrieving site-specific mass discriminators and IHC;
- stop at surface morphology or superficial histology without requiring base/deeper-lesion sampling when malignancy can hide there;
- let a strong competing risk factor override prior-cancer recurrence without IHC comparison;
- request the correct molecular test but fail to update diagnosis based on what a negative result would imply;
- treat absent inflammatory signs in immunocompromised hosts as reassuring instead of as expected false negatives;
- localize drainage to a tooth source without checking trauma history, odontogenic-source absence, and bone sequestrum imaging;
- dismiss infection/overlap because one test class is negative even when exposure, organ pattern, and treatment risk remain high;
- produce empty output when a specialty-pathology case needs a minimum differential and marker panel;
- diagnose a sellar mass from anatomy alone without cyst-content and histology discriminators;
- call destructive temporal-bone granulation tissue malignant before inflammatory and xanthogranulomatous mimics are compared;
- use general drug-toxicity priors instead of case-specific medication timelines;
- reason about sequential events independently instead of forcing a bridge diagnosis;
- skip vessel-specific imaging before metabolic or inflammatory workups in headache/seizure/focal deficit cases;
- close on release-hallucination or psychiatric explanations without seizure semiology and EEG retrieval;
- diagnose functional/conversion symptoms despite sacral, autonomic, or localizing neurologic red flags;
- ignore false-positive/false-negative rates of tests;
- treat negative biopsy or antibody positivity as definitive without context;
- skip management escalation rules.

The first harness should therefore force knowledge retrieval at specific uncertainty points, not merely ask for more papers.

## Harness Improvements To Induce

### 1. Discriminator-First Retrieval

Before broad case-report search, ask:

```text
What specific finding would distinguish the top two diagnoses?
What document type would know that: criteria, review, guideline, test interpretation paper, pathology/IHC table, imaging review, or case series?
```

Add a required structured output:

```json
{
  "top_mimic_pair": ["...", "..."],
  "needed_discriminators": [
    {
      "finding": "...",
      "why_it_matters": "...",
      "retrieval_query": "...",
      "target_source_type": "criteria|review|guideline|test_interpretation|imaging_review|pathology_table|case_series"
    }
  ]
}
```

### 2. Biomarker Interpretation Tool Step

Trigger when prompt contains antibody, marker, CSF index, OCBs, IHC stain, serology, or genetic variant.

Required retrieval:

- sensitivity/specificity or typical prevalence;
- titer threshold or false-positive caveat;
- compartment relevance, such as serum versus CSF;
- persistence versus transient positivity;
- diseases where the marker appears as a mimic.

### 3. Mimic Pair Comparison Table

Trigger when final answer confidence is high but evidence contains another plausible mimic. The model must retrieve and fill:

| Discriminator | Diagnosis A | Diagnosis B | Case finding | Direction |
| --- | --- | --- | --- | --- |

This would likely have helped both MS/MOGAD and PACNS/RCVS.

### 4. Organic Psychosis Checklist

Trigger on psychosis/catatonia/insomnia/hallucinations plus any abnormal CSF, MRI, EEG, systemic sign, severe nutritional state, seizure, autonomic sign, or cognitive change.

Required retrieval categories:

- autoimmune encephalitis;
- NPSLE/systemic autoimmune disease;
- infection;
- toxic/metabolic/endocrine;
- prion/sleep/autonomic syndromes;
- seizure/epilepsy mimics;
- primary psychiatric only after organic checks.

### 5. Negative-Test Does Not Exclude Rule

Trigger on negative biopsy, negative antibody, negative imaging, or negative cultures when clinical suspicion remains high.

Required retrieval:

- false-negative rate;
- sampling limitations;
- repeat or alternative test;
- treatment implications when suspicion remains.

This is directly relevant to PACNS negative biopsy and seronegative autoimmune encephalitis cases.

### 6. Management-Escalation Retrieval

For cases asking “next step,” retrieve management rules separately from diagnosis facts. The answer should not assume diagnosis and management share the same evidence.

Examples:

- PACNS: cyclophosphamide plus steroids when severe/progressive.
- Pediatric MS: disease-modifying therapy after dissemination in time/space.
- NPSLE: autoimmune serologies and high-dose corticosteroids/immunosuppression.

### 7. Pathology Lineage Verification

Trigger on FNA/cytology/preliminary pathology plus any discordant systemic feature: cytopenias, marrow signal, unusual age/site, negative infection studies, very high LDH, or bulky generalized disease.

Required retrieval:

- mimics of the preliminary pathology label;
- required IHC/flow/cytogenetic panel;
- whether bone marrow biopsy is needed;
- known misdiagnosis pitfalls;
- management consequence if lineage changes.

This would likely have rescued the myeloid sarcoma case, where the model gave a plausible but incomplete lymphoma pathway instead of forcing myeloid markers and marrow examination.

### 8. Drug Causality Timeline

Trigger on multiple medications plus rash, organ toxicity, cytopenias, liver injury, neurologic symptoms, fever, or hypersensitivity.

Required retrieval:

- known adverse events for each candidate drug;
- onset windows;
- dechallenge response;
- rechallenge recurrence or prophylaxis;
- causality scoring method such as Naranjo;
- management preserving essential therapy when possible.

Structured output:

| Candidate drug | Start date/relative day | Event timing | Dechallenge | Rechallenge/prophylaxis | Literature support | Direction |
| --- | --- | --- | --- | --- | --- | --- |

This would likely have rescued the arsenic trioxide case because the key was not the rash diagnosis alone; it was attribution and management under competing APL therapies.

### 9. Two-Event Bridge Diagnosis

Trigger on two major events separated in time, especially when the first event has negative initial workup and the second event looks embolic, metastatic, paraneoplastic, inflammatory, or recurrent.

Required retrieval:

- diagnoses that connect both events mechanistically;
- false-negative limitations of the first workup;
- targeted repeat imaging or tissue diagnostic step;
- "what would we look for now that was missed initially?"

Structured output:

| Event 1 | Event 2 | Candidate bridge diagnosis | Mechanism linking both | Targeted retrieval/query | Next diagnostic test |
| --- | --- | --- | --- | --- | --- |

This would likely have rescued the cardiac angiosarcoma case by linking hemorrhagic tamponade and later embolic stroke to an occult right atrial vascular tumor.

### 10. Neurovascular Imaging Gate

Trigger on acute or relapsing severe headache with seizure, aphasia, hemiparesis, papilledema, confusion, cortical signs, or young/cryptogenic stroke-like episodes.

Required retrieval:

- venous thrombosis/CVST presentations;
- arterial stroke, dissection, vasculitis, migraine, MELAS, and autoimmune mimics;
- modality-specific next tests: MRI/MRV, CT/CTV, CTA/MRA, vessel-wall MRI when indicated;
- management consequence, especially anticoagulation for CVST.

Structured output:

| Syndrome clue | Vascular diagnosis to exclude | Required imaging | Why before alternative workup | Management if positive |
| --- | --- | --- | --- | --- |

This would likely have rescued the CVST case by making MRV/CTV a required discriminator before MRS/genetic testing for MELAS.

### 11. Seizure Semiology And Physiology Gate

Trigger on episodic hallucinations, transient aphasia, spells, altered behavior, automatisms, unexplained agitation, or symptoms after cortical injury.

Required retrieval:

- seizure semiology for the symptom type and localization;
- mimics including Charles Bonnet syndrome, migraine aura, delirium, toxic/metabolic causes, sleep disorders, psychiatric disease, and functional symptoms;
- routine EEG versus prolonged/video EEG yield;
- lesion localization and timing after stroke, tumor, infection, or trauma;
- treatment-response evidence when diagnostic uncertainty remains.

Structured output:

| Feature | Case finding | Supports seizure? | Supports mimic? | Required physiology test |
| --- | --- | --- | --- | --- |

This would likely have rescued the occipital epilepsy case by requiring EEG/prolonged EEG and semiology retrieval before reassurance-only Charles Bonnet management.

### 12. Functional Diagnosis Stop Rule

Trigger when functional neurologic disorder, conversion disorder, primary psychiatric disease, trauma response, catatonia, or somatization is being considered and the case contains any structural red flag.

Required retrieval:

- sacral sensory loss, saddle anesthesia, absent anal wink, urinary retention, bowel/bladder dysfunction;
- objective sensory level, focal reflex changes, progressive gait disturbance, prior spine/pelvic trauma, prior surgery/scarring;
- conus medullaris, cauda equina, tethered cord, compressive myelopathy, inflammatory myelopathy, and spinal infection/tumor mimics;
- required imaging, usually MRI of the relevant spine region or entire spine when localization is uncertain.

Structured output:

| Functional label considered | Red flag | Structural mimic | Required test | Why functional closure is unsafe |
| --- | --- | --- | --- | --- |

This would likely have rescued the tethered cord case by making absent anal wink, perineal sensory loss, and urinary retention blocking findings for conversion disorder closure.

### 13. Steroid-Responsive Neuro-Oncology Gate

Trigger on cranial neuropathy, IAC/CPA mass, leptomeningeal enhancement, nerve-root enhancement, multifocal cranial nerve enhancement, or CNS mass regression after steroids.

Required retrieval:

- PCNSL and lymphoma behavior after corticosteroids;
- cranial nerve/IAC/CPA lymphoma and metastatic mimics;
- infectious/inflammatory mimics such as Ramsay Hunt, sarcoidosis, Lyme, and demyelination;
- diagnostic consequences of steroids before biopsy;
- CSF cytology/flow, serial MRI, and biopsy strategy when tissue is feasible.

Structured output:

| Imaging/time-course clue | Neoplastic mimic | Infectious/inflammatory mimic | Required diagnostic step | Why steroid response is not reassuring |
| --- | --- | --- | --- | --- |

This would likely have rescued the IAC/CPA lymphoma case by treating mass regression as a lymphoma-compatible discriminator rather than evidence for Ramsay Hunt.

### 14. Prion Phenotype And Exposure Plausibility Gate

Trigger on rapidly progressive dementia, insomnia, dysautonomia, psychiatric change, movement disorder, ataxia, myoclonus, periodic EEG, or suspected prion disease.

Required retrieval:

- phenotype discriminators among sFI, sCJD, vCJD, genetic prion disease, and iatrogenic CJD;
- MRI DWI/ADC, thalamic involvement, EEG pattern, CSF 14-3-3, RT-QuIC, and PRNP testing;
- sleep/autonomic features and time course;
- exposure route, incubation, donor/source plausibility, and expected phenotype.

Structured output:

| Feature/exposure | Case finding | Supports subtype | Argues against subtype | Required diagnostic step |
| --- | --- | --- | --- | --- |

This would likely have rescued the sporadic fatal insomnia case by preventing remote graft exposure from overriding the clinical prion phenotype.

### 15. Known-Cancer Neurologic Syndrome Gate

Trigger on active, recent, high-stage, or high-risk malignancy plus new headache, nausea/vomiting, cranial neuropathy, radiculopathy, syncope, multifocal symptoms, meningitic symptoms, or repeated unexplained neurologic presentations.

Required retrieval:

- cancer-specific CNS relapse and leptomeningeal metastasis patterns;
- sensitivity and false-negative limits of initial MRI and CSF cytology;
- repeat CSF cytology strategy, including volume, processing, and repeat sampling;
- CSF flow cytometry/cell block or cancer-specific testing when relevant;
- how remission status, normal tumor markers, or negative PET-CT can fail to exclude CNS/leptomeningeal disease.

Structured output:

| Cancer context | Neurologic syndrome | Negative test caveat | Required repeat test | Competing diagnosis to compare |
| --- | --- | --- | --- | --- |

This would likely have rescued the leptomeningeal carcinomatosis case by making first-negative cytology and negative MRI insufficient to close on cervical artery dissection.

### 16. Autoimmune Encephalitis Specificity Gate

Trigger on suspected autoimmune encephalitis, limbic encephalitis, faciobrachial dystonic seizures, refractory seizures/status epilepticus, autonomic instability, or antibody-panel results.

Required retrieval:

- probable and seronegative autoimmune encephalitis criteria;
- antibody subtype specificity, including what is required to diagnose LGI1, CASPR2, NMDAR, GABA-B, or other named syndromes;
- serum versus CSF testing and panel limitations;
- infectious exclusion and tumor screening;
- first-line and second-line immunotherapy escalation for refractory seizures/status epilepticus.

Structured output:

| Antibody/subtype | Case evidence | Missing evidence | Syndrome-level diagnosis allowed? | Management implication |
| --- | --- | --- | --- | --- |

This would likely have rescued the seronegative autoimmune encephalitis case by preventing anti-LGI1 over-specification while preserving urgent immunotherapy.

### 17. Acute Neurologic Emergency Fallback

Trigger on coma, acute loss of consciousness, severe headache, acute infarct, seizure/status epilepticus, abnormal emergency neuroimaging, or a blank/empty model answer.

Required retrieval:

- minimum must-not-miss differential: arterial ischemia, venous thrombosis/CVST, hemorrhage, seizure/status, toxic-metabolic, infection, and inflammatory causes;
- what CT, MRI, arterial imaging, venous imaging, EEG, LP, and metabolic testing each rule in/out;
- when normal arterial MRA/CTA should trigger MRV/CTV;
- the immediate next diagnostic test even if final diagnosis confidence remains low.

Structured output:

| Emergency clue | Must-not-miss diagnosis | Test already done | Remaining required test | Why empty output is unsafe |
| --- | --- | --- | --- | --- |

This would likely have rescued the CVST empty-answer case by forcing MRV/CTV after normal arterial MRA.

### 18. Infection Microbiology Specificity Gate

Trigger on indolent infection, abscess, osteomyelitis, spondylodiscitis, culture-negative infection, negative TB tests, unusual imaging patterns, or pathogen-specific treatment questions.

Required retrieval:

- pathogen-specific imaging, exposure, culture, PCR, serology, and histopathology clues;
- anaerobic, aerobic, fungal, AFB, TB PCR/culture, Brucella serology/culture, and Actinomyces histopathology strategy;
- whether aspirate/tissue is adequate and whether repeat biopsy is needed;
- antimicrobial choice, duration, and surgical drainage/decompression indications.

Structured output:

| Pathogen | Supporting clues | Arguing-against clues | Required microbiology/pathology | Treatment implication |
| --- | --- | --- | --- | --- |

This would likely have rescued the spinal actinomycosis case by forcing anaerobic/histopathology retrieval before brucella closure.

### 19. Mass Malignancy Red-Flag Gate

Trigger on recurrent, enlarging, painful, deep, unusual-site, or previously excised masses without histology.

Required retrieval:

- malignancy red flags for the anatomic site and tissue type;
- benign-versus-malignant pathology criteria;
- biopsy/excision strategy and whether local staging imaging is needed before definitive surgery;
- IHC or molecular tests that distinguish benign mimics from sarcoma/malignancy;
- margin planning and referral implications.

Structured output:

| Mass clue | Benign mimic | Malignant mimic | Required tissue/pathology discriminator | Management implication |
| --- | --- | --- | --- | --- |

This would likely have rescued the vaginal leiomyosarcoma case by making recurrent leiomyoma an unsafe final answer until malignancy criteria and tissue diagnosis were addressed.

### 20. Cardiac/Pericardial Mass Gate

Trigger on recurrent or hemorrhagic pericardial effusion, rapid reaccumulation after drainage, nodular pericardial thickening, recurrent pleural effusion with pericardial disease, failed anti-inflammatory therapy, or an enhancing cardiac/pericardial mass.

Required retrieval:

- cardiac/pericardial tumor differential including angiosarcoma, lymphoma, mesothelioma, metastasis, benign tumors, uremic/inflammatory pericarditis, and infection;
- cardiac MRI and contrast CT imaging discriminators;
- pericardial fluid cytology false-negative limits and when tissue biopsy is required;
- endothelial, lymphoid, mesothelial, and metastatic IHC markers;
- biopsy approach, surgical resection feasibility, margin status, staging, and oncology referral implications.

Structured output:

| Pericardial clue | Candidate entity | Supporting clues | Arguing-against clues | Required tissue/marker | Management implication |
| --- | --- | --- | --- | --- | --- |

This would likely have rescued the pericardial angiosarcoma case by forcing vascular tumor retrieval and cytology-caveat handling before lymphoma closure.

### 21. Spindle-Cell Pathology Subtype Gate

Trigger on spindle-cell neoplasm, sarcomatoid tumor, pleomorphic tumor, high-grade sarcoma, generic UPS, preliminary mesenchymal lineage, or a pending IHC/molecular panel.

Required retrieval:

- organ-specific spindle-cell differential for the involved site;
- epithelial, stromal, smooth-muscle, vascular, melanocytic/nerve-sheath, and undifferentiated sarcoma markers as relevant;
- marker patterns that move from broad lineage to named subtype;
- whether negative epithelial markers exclude metaplastic carcinoma or only reduce its likelihood;
- management implications of subtype, including surgery, margins, staging, and oncology referral.

Structured output:

| Site | Broad category | Named subtype | Supporting markers | Excluding markers | Next pathology step |
| --- | --- | --- | --- | --- | --- |

This would likely have rescued the mammary stromal sarcoma case by making generic UPS/high-grade sarcoma an incomplete answer while CD10/CD34/desmin/SMA subtype evidence was pending.

### 22. Bone Vascular Tumor / Secondary ABC Gate

Trigger on ABC-like bone histology, lytic expansile hemorrhagic/cystic bone lesion, older age for primary ABC, rapid recurrence after curettage, progressive osteolysis, new soft-tissue mass, vascular anomaly history, or benign histology discordant with aggressive course.

Required retrieval:

- primary ABC versus secondary ABC criteria, including age and recurrence patterns;
- telangiectatic osteosarcoma versus angiosarcoma versus giant cell tumor/metastasis/lymphoma discriminators;
- osteoid/matrix evidence and radiographic matrix clues;
- endothelial markers including CD31, CD34, ERG, and FLI1;
- when to re-review original biopsy or repeat biopsy the recurrent/soft-tissue component;
- oncologic resection, staging, and adjuvant therapy implications.

Structured output:

| Bone clue | Candidate entity | Supports | Argues against | Required marker/imaging discriminator | Next step |
| --- | --- | --- | --- | --- | --- |

This would likely have rescued the intraosseous angiosarcoma case by forcing endothelial-marker retrieval before telangiectatic osteosarcoma closure.

### 23. Gnathic Bone Tumor Radiographic Gate

Trigger on mandibular/maxillary destructive lesions, widened periodontal ligament space, loss of lamina dura, cortical destruction, soft-tissue mass, rapid painful jaw swelling, absent odontogenic source, or suspected primary bone lymphoma/osteomyelitis/metastasis in the jaw.

Required retrieval:

- jaw-specific osteosarcoma signs including widened periodontal ligament space and loss of lamina dura;
- how often sunburst periosteal reaction, Codman triangle, and mineralized matrix are absent in gnathic osteosarcoma;
- primary bone lymphoma, osteomyelitis, odontogenic abscess, chondrosarcoma, metastasis, and osteosarcoma discriminators;
- infection and odontogenic-source exclusion clues;
- biopsy plan with osteoid/matrix assessment and relevant IHC/molecular testing.

Structured output:

| Jaw clue | Candidate entity | Supports | Argues against | Required radiology/pathology discriminator | Next step |
| --- | --- | --- | --- | --- | --- |

This would likely have rescued the gnathic osteosarcoma case by forcing widened-PDL/loss-of-lamina-dura retrieval before lymphoma closure.

### 24. Middle-Ear Mass Discriminator Gate

Trigger on retrotympanic mass, middle-ear soft-tissue lesion, suspected glomus tympanicum, suspected cholesteatoma, recurrent attic/middle-ear lesion, unexplained otalgia/fullness, or ossicular-adjacent mass.

Required retrieval:

- middle-ear mass differential including glomus tympanicum, cholesteatoma, adenomatous neuroendocrine tumor, schwannoma, carcinoma, and otitis/granulation;
- pulsatile tinnitus, vascularity, bone erosion, retraction pocket, facial weakness, and ossicular relationship discriminators;
- CT/MRI features that separate vascular tumor, cholesteatoma, and indolent epithelial/neuroendocrine tumors;
- surgical excision versus imaging-first strategy;
- IHC including synaptophysin, chromogranin, cytokeratin/EMA, Ki-67, and paraganglioma-marker comparison.

Structured output:

| Middle-ear clue | Candidate entity | Supports | Argues against | Required imaging/IHC discriminator | Next step |
| --- | --- | --- | --- | --- | --- |

This would likely have rescued the middle-ear neuroendocrine tumor case by forcing neuroendocrine IHC retrieval before glomus closure.

### 25. Keratotic Skin/Genital Lesion Base-Histology Gate

Trigger on hyperkeratotic, verrucous, horn-like, micaceous, treatment-resistant, or genital keratotic lesions.

Required retrieval:

- morphology-first dermatology differential including cutaneous horn, pseudoepitheliomatous keratotic balanitis, wart, verrucous carcinoma, and SCC;
- distinction between surface keratin/hyperkeratosis and base pathology;
- malignant and premalignant risk at the base of cutaneous horns;
- excision depth, margin, and base-histology requirements;
- escalation when SCC, verrucous carcinoma, or dysplasia is found.

Structured output:

| Surface clue | Candidate entity | Base histology concern | Required sampling | Management implication |
| --- | --- | --- | --- | --- |

This would likely have rescued the penile cutaneous horn case by forcing base-histology retrieval before keratotic balanitis closure.

### 26. Prior-Cancer Unusual-Mass Gate

Trigger on a new, rapidly growing, deep, unusual-site, painful, fixed, or symptomatic mass in a patient with active or prior malignancy, especially when a competing predisposition could anchor the diagnosis.

Required retrieval:

- recurrence and metastatic patterns of the prior malignancy, including late or unusual-site metastases;
- competing new-primary risks, such as NF1-associated MPNST or syndrome-associated tumors;
- IHC/marker panel distinguishing prior-cancer metastasis from local mimics;
- biopsy plan and whether imaging should precede or follow biopsy;
- staging and urgent complication assessment for systemic, spine, or neurologic symptoms.

Structured output:

| Prior cancer context | New mass clue | Metastatic mimic | New-primary mimic | Required IHC/marker | Next step |
| --- | --- | --- | --- | --- | --- |

This would likely have rescued the melanoma metastasis case by forcing melanoma-marker retrieval before MPNST closure.

### 27. Lipomatous Tumor Molecular Interpretation Gate

Trigger on large, deep, retroperitoneal, intramuscular, recurrent, or radiologically concerning fatty tumors; equivocal MDM2 IHC; or a differential of lipoma/hibernoma versus ALT/WDL.

Required retrieval:

- imaging discriminators: septa thickness, nodular/solid enhancing components, calcification, infiltrative pattern;
- histology discriminators: mature adipocytes, atypical stromal cells, lipoblasts, nuclear atypia, brown fat cells;
- MDM2/CDK4 IHC limitations and MDM2 FISH interpretation;
- hibernoma and lipoma-like hibernoma markers such as UCP1 when relevant;
- management after negative MDM2 amplification versus positive amplification.

Structured output:

| Fatty mass clue | Benign entity | Malignant entity | Molecular discriminator | How result changes diagnosis |
| --- | --- | --- | --- | --- |

This would likely have rescued the retroperitoneal lipoma/hibernoma case by requiring negative-MDM2 interpretation rather than treating ALT/WDL as the endpoint.

### 28. Immunocompromised Necrotizing Infection Gate

Trigger on rapidly progressive soft-tissue necrosis, blistering, skin tension, hematoma-to-necrosis evolution, severe neutropenia, chemotherapy, AML, transplant, diabetes, immunosuppression, or suspected necrotizing fasciitis/mucormycosis/cellulitis in an immunocompromised host.

Required retrieval:

- necrotizing fasciitis presentations in neutropenic and chemotherapy patients;
- caveats for absent fever, pain, leukocytosis, gas, abscess, bacteria, and inflammatory cells;
- LRINEC limitations in immunocompromised/neutropenic patients;
- cutaneous mucormycosis versus bacterial necrotizing infection discriminators;
- surgical exploration, finger test/fascial findings, radical debridement, deep culture, and empiric antimicrobial strategy.

Structured output:

| Negative or subtle finding | Why it may be falsely reassuring | Nec fasc implication | Fungal mimic implication | Required urgent action |
| --- | --- | --- | --- | --- |

This would likely have rescued the neutropenic necrotizing fasciitis case by making lack of gas and paucicellular biopsy non-exclusionary.

### 29. Maxillofacial Osteomyelitis Source-Localization Gate

Trigger on chronic maxillary/mandibular pain, swelling, purulent fistula, tooth mobility, prior facial trauma, smoking/impaired healing, no recent dental procedure, no clear caries/pulp source, or suspected periapical abscess versus osteomyelitis.

Required retrieval:

- odontogenic abscess versus chronic suppurative osteomyelitis discriminators;
- trauma-related jaw osteomyelitis mechanisms and delayed presentation;
- when periapical films are insufficient;
- panoramic radiograph/orthopantomogram and cone-beam CT findings, including bone destruction and sequestrum;
- antibiotic, culture/biopsy, debridement, and extraction indications.

Structured output:

| Fistula/tooth clue | Odontogenic source evidence | Bone infection evidence | Required imaging | Management implication |
| --- | --- | --- | --- | --- |

This would likely have rescued the maxillary osteomyelitis case by requiring source localization and sequestrum imaging before periapical abscess closure.

### 30. Granulomatous Overlap Gate

Trigger on granulomatous eye, lymph node, pulmonary, genitourinary, skin, or systemic disease, especially when sarcoidosis and tuberculosis features coexist or biopsy is declined/unavailable.

Required retrieval:

- sarcoidosis, tuberculosis, fungal, syphilis, Bartonella, lymphoma, and overlap-syndrome discriminators;
- negative-test caveats for IGRA, sputum, urine, culture, superficial biopsy, and unavailable tissue;
- organ-pattern clues such as optic disc granuloma, hilar/paratracheal nodes, epididymitis, azoospermia, skin lesions, or systemic symptoms;
- treatment-risk logic for corticosteroids, anti-TB therapy, empiric combined therapy, and biopsy pursuit;
- monitoring plan when empiric dual therapy is chosen.

Structured output:

| Granulomatous clue | Sarcoid direction | TB/other infection direction | Negative-test caveat | Treatment implication |
| --- | --- | --- | --- | --- |

This would likely have rescued the tuberculous sarcoidosis case by making negative IGRA/cultures non-exclusionary and forcing the anti-TB plus steroid decision before sarcoidosis-only closure.

### 31. Gynecologic Epithelioid Tumor Small-Biopsy Gate

Trigger on uterine/gynecologic epithelioid morphology, polygonal cells, smooth-muscle tumor consideration, PEComa/UTROSCT differential, small biopsy, hypervascular uterine mass, postmenopausal bleeding, or empty output in a pathology-heavy tumor case.

Required retrieval:

- epithelioid leiomyosarcoma versus PEComa, UTROSCT, carcinoma, melanoma, endometrial stromal tumor, and sex-cord stromal mimics;
- small-biopsy limitations for mitotic count, necrosis, atypia, and missing spindle-cell component;
- IHC panel with desmin, SMA, WT1, HMB-45, Melan-A, inhibin, calretinin, p53/p16, cytokeratin, and site-appropriate markers;
- staging/surgical management consequences when leiomyosarcoma is supported;
- empty-output rescue rule requiring a minimum differential and next marker panel.

Structured output:

| Epithelioid tumor clue | Candidate entity | Supporting feature | Required IHC/marker | Small-biopsy caveat |
| --- | --- | --- | --- | --- |

This would likely have rescued the uterine epithelioid leiomyosarcoma case by forcing a minimum pathology response after the API failure.

### 32. Sellar Xanthogranuloma / Cystic-Sellar-Mass Gate

Trigger on cystic-solid sellar/suprasellar masses, T1/T2 hyperintense cyst content, mural nodules, optic-chiasm compression, normal or abnormal pituitary function, suspected craniopharyngioma, Rathke cleft cyst, adenoma apoplexy, or inflammatory cyst.

Required retrieval:

- xanthogranuloma, Rathke cleft cyst, adamantinomatous/papillary craniopharyngioma, pituitary adenoma/apoplexy, meningioma, and inflammatory cyst discriminators;
- MRI and CT discriminators, including cyst content, calcification, hemorrhage/cholesterol clues, and cavernous sinus invasion;
- histopathology with foamy macrophages, cholesterol clefts, hemosiderin, giant cells, chronic inflammation, and CD68 when relevant;
- surgical route/maximal safe resection plus pathology confirmation;
- postoperative pituitary hormone assessment, replacement if needed, and imaging follow-up.

Structured output:

| Sellar clue | Candidate entity | Imaging discriminator | Histology discriminator | Follow-up implication |
| --- | --- | --- | --- | --- |

This would likely have rescued the sellar xanthogranuloma case by preventing craniopharyngioma closure from a mural nodule alone.

### 33. Temporal-Bone Inflammatory Mass / Malignancy Mimic Gate

Trigger on external auditory canal or temporal-bone granulation mass, lytic bone destruction, chronic otorrhea/otalgia, mixed hearing loss, suspected SCC, malignant otitis externa, skull-base osteomyelitis, cholesteatoma, GPA, or xanthogranulomatous inflammation.

Required retrieval:

- external auditory canal SCC versus inflammatory osteomyelitis/xanthogranulomatous osteomyelitis discriminators;
- caveats for normal ESR/CRP, no diabetes, no immunosuppression, and lack of facial palsy;
- CT/MRI pattern and extent without treating lysis as malignancy-specific;
- incisional biopsy/debridement histopathology, malignant-cell exclusion, foamy histiocyte/xanthogranulomatous pattern, and cultures;
- treatment pathway after inflammatory tissue diagnosis, including debridement, antimicrobial therapy, and otologic follow-up.

Structured output:

| Temporal-bone clue | Malignant direction | Inflammatory direction | Required tissue/culture | Management implication |
| --- | --- | --- | --- | --- |

This would likely have rescued the temporal-bone osteomyelitis case by making biopsy interpretation, not imaging severity, the diagnostic decision point.

## Implemented Prompt Mechanics

These case-study lessons have been moved into the first prompt scaffold:

1. `case query-prompt` requires `top_mimic_pairs`.
2. `case discriminator-prompt` takes the current differential and asks only for discriminator retrieval queries.
3. Query prompt templates include biomarker interpretation, mimic-pair comparisons, management escalation, pathology lineage verification, drug causality, and two-event bridge diagnosis.
4. Evidence notes support `discriminator_table`, `required_tests_or_markers`, `required_imaging_or_procedures`, `required_eeg_or_physiology`, `temporal_semiology_table`, `functional_neuro_red_flags`, `malignancy_red_flags`, `tissue_diagnosis_plan`, `serial_imaging_change_table`, `known_cancer_context`, `csf_cytology_plan`, `negative_test_caveats`, `antibody_specificity_table`, `seronegative_ae_criteria`, `immunotherapy_escalation_plan`, `emergency_neuro_differential`, `emergency_next_tests`, `empty_output_rescue_rule`, `microbiology_test_plan`, `pathogen_discriminator_table`, `antimicrobial_duration_plan`, `neutropenic_infection_caveats`, `necrotizing_infection_discriminator_table`, `surgical_source_control_plan`, `granulomatous_overlap_table`, `tb_negative_test_caveats`, `dual_therapy_decision_plan`, `spindle_cell_differential_table`, `organ_specific_marker_panel`, `sarcoma_subtype_plan`, `bone_tumor_red_flags`, `bone_lesion_discriminator_table`, `endothelial_marker_plan`, `gnathic_radiographic_red_flags`, `jaw_lesion_discriminator_table`, `bone_matrix_assessment_plan`, `middle_ear_mass_discriminator_table`, `otologic_imaging_red_flags`, `neuroendocrine_ihc_plan`, `keratotic_lesion_discriminator_table`, `skin_base_histology_plan`, `dermatology_malignancy_caveats`, `maxillofacial_infection_discriminator_table`, `sequestrum_imaging_plan`, `odontogenic_source_caveats`, `gynecologic_epithelioid_tumor_table`, `uterine_smooth_muscle_ihc_plan`, `small_biopsy_malignancy_caveats`, `sellar_mass_discriminator_table`, `sellar_histology_plan`, `pituitary_follow_up_plan`, `temporal_bone_mass_discriminator_table`, `temporal_bone_biopsy_plan`, `inflammatory_malignancy_mimic_caveats`, `prior_cancer_mass_context`, `metastasis_mimic_table`, `metastatic_ihc_plan`, `lipomatous_tumor_discriminator_table`, `mdm2_testing_plan`, `benign_lipomatous_features`, `mass_malignancy_red_flags`, `tissue_sampling_plan`, `benign_malignant_pathology_table`, `cardiac_pericardial_red_flags`, `pericardial_fluid_caveats`, `cardiac_tumor_discriminator_table`, `cardiac_tissue_plan`, `prion_phenotype_table`, `exposure_plausibility_table`, `drug_causality_table`, `management_escalation_rules`, and `mechanistic_link`.
5. Presets are implemented for `neuro_psych`, `autoimmune_encephalitis`, `pathology`, `spindle_cell_pathology`, `bone_vascular_tumor`, `gnathic_bone_tumor`, `middle_ear_mass`, `keratotic_skin_lesion`, `maxillofacial_osteomyelitis`, `gynecologic_epithelioid_tumor`, `sellar_xanthogranuloma`, `temporal_bone_inflammatory_mass`, `prior_cancer_mass`, `lipomatous_tumor_molecular`, `mass_malignancy`, `cardiac_pericardial_mass`, `adverse_drug_event`, `infection_microbiology`, `immunocompromised_necrotizing_infection`, `granulomatous_overlap`, `demyelination`, `cns_vasculitis`, `acute_neuro_emergency`, `vascular_neuro`, `seizure_mimic`, `functional_neuro`, `neuro_oncology`, `cancer_neuro`, `prion_sleep`, and `sequential_event`.
6. `vascular_imaging_queries` are implemented for CVST/stroke-mimic cases.
7. `seizure_mimic_queries` are implemented for episodic symptom and post-cortical-injury mimic cases.
8. `functional_neuro_queries` are implemented for conversion/functional diagnoses with structural red flags.
9. `neuro_oncology_queries` are implemented for steroid-responsive CNS masses and cranial nerve enhancement cases.
10. `prion_sleep_queries` are implemented for prion phenotype and exposure-plausibility cases.
11. `cancer_neuro_queries` are implemented for known-cancer neurologic presentations and repeat-CSF false-negative cases.
12. `autoimmune_encephalitis_queries` are implemented for seronegative AE and antibody-subtype specificity cases.
13. `acute_neuro_emergency_queries` are implemented for coma/headache/infarct and blank-output rescue cases.
14. `infection_microbiology_queries` are implemented for pathogen-specific indolent infection cases.
15. `spindle_cell_pathology_queries` are implemented for organ-specific spindle-cell/sarcoma subtype cases.
16. `bone_vascular_tumor_queries` are implemented for ABC-like aggressive bone lesion and vascular tumor cases.
17. `gnathic_bone_tumor_queries` are implemented for jaw bone tumor radiographic discriminator cases.
18. `middle_ear_mass_queries` are implemented for retrotympanic/middle-ear mass cases.
19. `keratotic_skin_lesion_queries` are implemented for hyperkeratotic/verrucous/horn-like skin and genital lesion cases.
20. `prior_cancer_mass_queries` are implemented for prior-cancer unusual soft-tissue mass cases.
21. `lipomatous_tumor_molecular_queries` are implemented for deep/retroperitoneal fatty tumor molecular discriminator cases.
22. `immunocompromised_necrotizing_infection_queries` are implemented for neutropenic/immunocompromised soft-tissue necrosis cases.
23. `maxillofacial_osteomyelitis_queries` are implemented for jaw fistula/osteomyelitis source-localization cases.
24. `granulomatous_overlap_queries` are implemented for sarcoidosis/TB/systemic granulomatous overlap cases.
25. `gynecologic_epithelioid_tumor_queries` are implemented for uterine/gynecologic epithelioid small-biopsy tumor cases.
26. `sellar_xanthogranuloma_queries` are implemented for cystic-solid sellar mass cases.
27. `temporal_bone_inflammatory_mass_queries` are implemented for destructive external-auditory-canal/temporal-bone mass cases.
28. `mass_malignancy_queries` are implemented for recurrent/enlarging painful mass cases.
29. `cardiac_pericardial_mass_queries` are implemented for hemorrhagic effusion and cardiac/pericardial mass cases.

## Remaining Implementation Backlog

1. Add validators for model JSON returned by `query-prompt`, `discriminator-prompt`, and `answer-prompt`.
2. Add a guardrail that prevents final answer if no discriminator evidence was retrieved for the top two diagnoses.
3. Add a guardrail that prevents final answer in pathology presets if required lineage markers/tests are missing.
4. Add a guardrail that prevents final answer in adverse-drug-event presets if no medication timeline/dechallenge table is present.
5. Add a guardrail that prevents final answer in sequential-event presets if no `mechanistic_link` was retrieved.
6. Add a guardrail that prevents final answer in vascular-neuro presets if no vessel-specific imaging discriminator was retrieved.
7. Add a guardrail that prevents final answer in seizure-mimic presets if no semiology table or EEG/prolonged EEG discriminator was retrieved.
8. Add a guardrail that prevents final answer in functional-neuro presets if sacral/autonomic/localizing red flags have not been resolved with structural-mimic evidence.
9. Add a guardrail that prevents final answer in neuro-oncology presets if steroid-responsive mass or cranial nerve enhancement lacks malignancy/tissue-plan evidence.
10. Add a guardrail that prevents final answer in prion-sleep presets if no phenotype table or exposure-plausibility table is present.
11. Add a guardrail that prevents final answer in cancer-neuro presets if known cancer context lacks repeat-CSF/negative-test caveat evidence.
12. Add a guardrail that prevents final answer in autoimmune-encephalitis presets if a named subtype lacks antibody/specificity evidence.
13. Add a guardrail that prevents empty final answers in acute-neuro-emergency presets.
14. Add a guardrail that prevents final answer in infection-microbiology presets if no pathogen-specific microbiology/pathology plan is present.
15. Add a guardrail that prevents final answer in spindle-cell-pathology presets if no organ-specific marker panel and subtype table are present.
16. Add a guardrail that prevents final answer in bone-vascular-tumor presets if no secondary-ABC table and endothelial-marker plan are present.
17. Add a guardrail that prevents final answer in gnathic-bone-tumor presets if no jaw-specific radiographic/matrix discriminator table is present.
18. Add a guardrail that prevents final answer in middle-ear-mass presets if no vascular/cholesteatoma/neuroendocrine discriminator table is present.
19. Add a guardrail that prevents final answer in keratotic-skin-lesion presets if no base-histology malignancy exclusion plan is present.
20. Add a guardrail that prevents final answer in prior-cancer-mass presets if no metastatic recurrence and IHC comparison table is present.
21. Add a guardrail that prevents final answer in lipomatous-tumor-molecular presets if MDM2/CDK4 result interpretation is missing.
22. Add a guardrail that prevents final answer in immunocompromised-necrotizing-infection presets if blunted-sign caveats and source-control plan are missing.
23. Add a guardrail that prevents final answer in maxillofacial-osteomyelitis presets if no odontogenic-source and sequestrum-imaging table is present.
24. Add a guardrail that prevents final answer in mass-malignancy presets if no red-flag table and tissue/pathology plan is present.
25. Add a guardrail that prevents final answer in cardiac-pericardial-mass presets if no cytology caveat, tumor discriminator table, and tissue plan are present.
26. Add a guardrail that prevents final answer in granulomatous-overlap presets if no negative TB test caveat and steroid/anti-TB decision table is present.
27. Add a guardrail that prevents final answer in gynecologic-epithelioid-tumor presets if no small-biopsy caveat and IHC mimic panel is present.
28. Add a guardrail that prevents final answer in sellar-xanthogranuloma presets if no cystic-sellar discriminator table and histology/follow-up plan is present.
29. Add a guardrail that prevents final answer in temporal-bone-inflammatory-mass presets if biopsy/histology interpretation and inflammatory malignancy-mimic caveats are missing.
30. Wire presets into the future automated runner rather than only prompt-generation CLI commands.

## Next100 Handoff Cases

This section starts the second public handoff set from 2026-06-13. It uses the same rule as the first 30: the source article, DOI, title, PMCID, and answer key are evaluator-only and must not appear in model-facing diagnostic prompts.

### Next100 Case 1: Invasive Mold Sinusitis/CNS Disease Misidentified At Genus Level

**Prompt signal:** Immunosuppressed adult with chronic headache, facial numbness, sinus disease, and neurologic/leptomeningeal involvement. The case includes fungal culture/microscopy clues that require organism-level identification rather than a broad fungal syndrome label.

**Pro answer:** Invasive cerebral phaeohyphomycosis with meningitis and sinusitis attributed to a familiar neurotropic dematiaceous mold.

**Reference diagnosis:** Invasive Microascus/Scopulariopsis sinusitis with leptomeningeal involvement.

**Where Pro failed:**

- Got invasive mold sinus/CNS disease broadly right, but selected the wrong genus/species.
- Used a familiar neurotropic dematiaceous mold prior instead of retrieving lab morphology discriminators.
- Did not force a table comparing colony morphology, conidia, annellides/hyphal morphology, sequencing, and susceptibility.
- Did not separate syndrome-level therapy from organism-level susceptibility and CNS-penetration implications.

**Harness feature implemented:** `mold_identification` preset. For invasive fungal sinusitis, CNS mold infection, phaeohyphomycosis/hyalohyphomycosis, or prompts with fungal colony/microscopy clues, the harness now requires organism-level mycology retrieval before naming a species.

**Good retrieval topics:**

- Microascus/Scopulariopsis invasive sinusitis CNS infection morphology;
- Cladophialophora versus Scopulariopsis/Microascus phaeohyphomycosis microscopy;
- mold identification annellides conidia sequencing invasive fungal disease;
- Scopulariopsis Microascus antifungal susceptibility CNS infection.

**Template queries:**

- `Microascus Scopulariopsis invasive sinusitis CNS infection morphology`
- `Cladophialophora versus Scopulariopsis Microascus phaeohyphomycosis microscopy`
- `mold identification annellides conidia sequencing invasive fungal disease`
- `Scopulariopsis Microascus antifungal susceptibility CNS infection`

**Harness implication:** Broad infectious syndrome accuracy is not enough when the prompt gives lab-identification clues. The controller should require a mold-ID table and susceptibility/CNS treatment plan before finalizing a fungal genus or species.

### Next100 Case 2: Fryns Syndrome Without Diaphragmatic Hernia Miscalled As Meckel-Gruber

**Prompt signal:** Consanguineous pregnancy with recurrent severe fetal anomalies, normal karyotype, characteristic facial dysmorphism, pulmonary hypoplasia, renal cystic dysplasia, hepatic cyst, cystic hygroma/increased nuchal fold, absent cerebellar vermis, absent corpus callosum, single umbilical artery, and no diaphragmatic hernia or cardiac defect.

**Pro answer:** Meckel-Gruber syndrome / ciliopathy.

**Reference diagnosis:** Fryns syndrome without congenital diaphragmatic hernia.

**Where Pro failed:**

- Anchored on cystic renal disease plus CNS anomalies as a ciliopathy/Meckel-Gruber pattern.
- Did not retrieve Fryns diagnostic spectrum or incomplete presentations without diaphragmatic hernia.
- Underweighted facial gestalt and pulmonary hypoplasia.
- Did not use absence of classic Meckel-Gruber features such as polydactyly/occipital encephalocele as a discriminator.
- Did not foreground autosomal recessive recurrence counseling and future reproductive testing options.

**Harness feature implemented:** `prenatal_syndromic_pattern` preset. For fetal anomaly syndromes, the harness forces a pattern table across facial findings, lungs, kidneys/liver, CNS, nuchal findings, digits/limbs, karyotype, inheritance, and recurrence counseling before final syndrome closure.

**Good retrieval topics:**

- Fryns syndrome without congenital diaphragmatic hernia diagnostic criteria;
- Fryns syndrome versus Meckel-Gruber fetal anomalies;
- fetal pulmonary hypoplasia renal cysts facial dysmorphism Fryns;
- consanguinity autosomal recessive fetal malformation syndrome recurrence risk.

**Template queries:**

- `Fryns syndrome without congenital diaphragmatic hernia diagnostic criteria`
- `Fryns syndrome versus Meckel-Gruber renal cysts CNS anomalies facial dysmorphism`
- `fetal pulmonary hypoplasia renal cystic dysplasia hepatic cyst facial dysmorphism Fryns`
- `autosomal recessive fetal malformation syndrome consanguinity recurrence risk genetic counseling`

**Harness implication:** Fetal syndrome diagnosis should be pattern-matched across anomalies rather than decided by one familiar organ triad. The controller should treat absent classic findings as active discriminators and should preserve recurrence/genetic counseling in the final answer.

### Next100 Case 3: PSP-P Misclassified As PSP-Richardson Syndrome

**Prompt signal:** Older adult with asymmetric resting tremor, rigidity, bradykinesia, initial substantial levodopa response, later gait freezing and occasional falls, slowed but full vertical saccades, preserved cognition, absent autonomic failure/hallucinations, midbrain atrophy metrics, and abnormal DaTscan.

**Pro answer:** Progressive supranuclear palsy, likely Richardson syndrome.

**Reference diagnosis:** Progressive supranuclear palsy-parkinsonism predominant (PSP-P), with MRPI 2.0 quantification and movement-disorders specialist confirmation/management.

**Where Pro failed:**

- Correctly recognized PSP but over-specified the Richardson phenotype.
- Treated midbrain atrophy as enough for PSP-RS subtype closure.
- Underweighted the early asymmetric parkinsonism, resting tremor, and meaningful levodopa response.
- Did not use slowed vertical saccades without frank supranuclear gaze palsy and later/occasional falls as PSP-P discriminators.
- Missed MRPI 2.0 as the most specific next diagnostic support step.

**Harness feature implemented:** `movement_disorder_phenotype` preset. For parkinsonism and suspected atypical parkinsonian syndromes, the harness forces phenotype-level retrieval across PD, PSP-P, PSP-RS, MSA, CBD, and DLB, plus MRPI/MRPI 2.0 and DaTscan interpretation.

**Good retrieval topics:**

- PSP-P versus PSP-Richardson syndrome clinical criteria;
- levodopa response asymmetric parkinsonism PSP-P differential;
- MRPI 2.0 PSP-P Parkinson disease differentiation;
- slowed vertical saccades without gaze palsy PSP parkinsonism predominant.

**Template queries:**

- `PSP-P versus PSP-Richardson syndrome clinical criteria levodopa response`
- `progressive supranuclear palsy parkinsonism predominant asymmetric tremor falls freezing`
- `MRPI 2.0 PSP-P Parkinson disease differentiation`
- `slowed vertical saccades without supranuclear gaze palsy PSP-P`

**Harness implication:** Getting the disease family right can still fail the case if the subtype drives the next diagnostic step. The controller should require a phenotype table and imaging-metric plan before finalizing atypical parkinsonism variants.

### Next100 Case 4: Intracranial Tuberculoma Miscalled As Neurosarcoidosis

**Prompt signal:** Older adult with a large enhancing frontal brain mass, edema and midline shift, granulomatous brain biopsy, positive Quantiferon, immigration from a TB-endemic region, absent pulmonary TB, negative broad infectious/rheumatologic workup, normal ACE/vitamin D, empiric anti-TB therapy plus steroid, and no clear clinical improvement after two weeks.

**Pro answer:** Neurosarcoidosis, with recommendation to discontinue anti-TB therapy.

**Reference diagnosis:** Intracranial tuberculoma, with continued anti-tuberculous therapy and high-dose corticosteroids for inflammatory mass effect while tissue cultures were pending.

**Where Pro failed:**

- Treated non-caseating granuloma as neurosarcoidosis-specific.
- Overweighted absent pulmonary TB and early nonresponse to anti-TB therapy.
- Underweighted positive Quantiferon and TB-endemic epidemiology.
- Did not use normal ACE/vitamin D and lack of systemic sarcoid evidence as anti-neurosarcoidosis clues.
- Made a management error by stopping anti-TB therapy while the tuberculoma differential was still active.

**Harness feature implemented:** `cns_granulomatous_mass` preset. For intracranial granulomatous mass lesions, the harness forces tuberculoma/neurosarcoidosis/fungal/malignancy mimics, biopsy limitations, TB exposure/IGRA, systemic sarcoid evidence, and continue-versus-stop anti-TB logic.

**Good retrieval topics:**

- intracranial tuberculoma non-caseating granuloma neurosarcoidosis differential;
- CNS tuberculoma positive Quantiferon absent pulmonary tuberculosis;
- neurosarcoidosis versus tuberculoma ACE vitamin D brain biopsy;
- tuberculoma early response anti-tuberculosis therapy corticosteroids mass effect.

**Template queries:**

- `intracranial tuberculoma non-caseating granuloma neurosarcoidosis differential`
- `CNS tuberculoma positive Quantiferon absent pulmonary tuberculosis`
- `neurosarcoidosis versus tuberculoma ACE vitamin D brain biopsy`
- `tuberculoma early response anti tuberculosis therapy corticosteroids mass effect`

**Harness implication:** CNS granulomatous pathology requires management-aware retrieval. The agent should not stop anti-TB therapy based on non-caseating granuloma, absent pulmonary disease, or two-week nonresponse when TB epidemiology/IGRA and pending cultures keep tuberculoma plausible.

### Next100 Remaining Cluster Lessons

The remaining next100 failures were reviewed as cluster patterns and mapped to reusable harness presets in the tracker:

- Ocular inflammation/infection: tuberculous scleral necrosis and transplant retinochoroidal toxoplasmosis failed when Pro treated postoperative/radiation or PTLD explanations as more likely than infection. Harness response: `ocular_infection_inflammation` and `immunocompromised_retinitis`.
- Neuroinflammatory demyelination: MOGAD/ADEM and AQP4-NMOSD failed when Pro overcalled neurosarcoidosis or lymphoma. Harness response: `neuroinflammatory_demyelination`.
- Organism-level microbiology: disseminated Magnusiomyces/Saprochaete and Malassezia colonization failed because Pro named the wrong organism or treated colonization as infection. Harness response: `mold_identification` and `colonization_vs_infection`.
- Bone and renal tumor specificity: pediatric mandibular Ewing sarcoma, renal leiomyosarcoma, and intrarenal neurofibroma failed when Pro used common carcinoma/osteosarcoma priors instead of site-specific tissue discriminators. Harness response: `bone_small_round_cell_tumor` and `renal_spindle_cell_mass`.
- Postoperative/localization traps: gossypiboma and extrauterine choriocarcinoma failed when Pro ignored prior surgery or persistent hCG localization after negative pelvic imaging. Harness response: `postoperative_foreign_body` and `persistent_hcg_localization`.
- GI tumor subtype errors: small bowel NET, ampullary LCNEC, and esophageal carcinosarcoma failed when Pro stopped at familiar polyposis/adenocarcinoma/leiomyosarcoma labels. Harness response: `gi_desmoplastic_neuroendocrine`, `gi_neuroendocrine_carcinoma`, and existing `spindle_cell_pathology`.
- High-stakes molecular/subsite calls: AML t(8;21) versus inv(16), adult optic pathway GBM versus PCNSL, sellar xanthogranuloma versus apoplexy, and pneumatosis cystoides intestinalis versus lipomatosis failed because the deciding feature was a specialized test, subsite, or confirmatory maneuver. Harness response: `hematologic_cytogenetic_subtype`, `optic_pathway_neoplasm`, existing `sellar_xanthogranuloma`, and `submucosal_gas_cyst`.

**Cross-cluster implication:** The second handoff set reinforces that the harness needs targeted retrieval at the point of specificity: species, syndrome subtype, anatomic subsite, IHC/molecular subtype, localization test, or colonization/infection status. Broad diagnostic-lane correctness was often insufficient.
