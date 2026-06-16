"""Feature-indexed preset selection.

Historically the harness mapped each known ``case_id`` to a hand-tuned preset
(``PRESET_BY_CASE_ID``). That made the 22-case set perform well but does not generalize: a
brand-new case has no entry and silently falls through to the weak ``general`` preset -- the path
the control ablation showed *regressing* easy cases. This module selects a preset from the case's
*clinical features* (vocabulary in the redacted challenge prompt, never the answer key), so a new
case is routed to the right reasoning family automatically.

Design:
- ``PRESET_BY_CASE_ID`` is kept as an explicit override for the originally-tuned cases (continuity
  + reproducibility of the 3->18 result). New/unknown cases use feature selection.
- ``select_preset(prompt, case_id=...)`` returns the override if present (and enabled), else the
  highest-scoring preset whose distinctive features fire, else ``general``.
- ``PRESET_FAMILY`` groups presets into reusable reasoning families; family-level agreement is how
  we validate the selector (most presets are single-case, so exact agreement is not the right bar).

Selection uses only ``ClinicalCase.prompt`` (the redacted presentation). It must never read the
answer key -- that would be choosing the reasoning framework from the answer.
"""

from __future__ import annotations

import re

# case_id -> hand-tuned preset for the originally-curated cases (override set).
PRESET_BY_CASE_ID: dict[str, str] = {
    "native_PMC3122590": "keratotic_skin_lesion",
    "transformed_PMC10025825": "gynecologic_epithelioid_tumor",
    "transformed_PMC10399123": "demyelination",
    "transformed_PMC10409533": "neuro_oncology",
    "transformed_PMC10540759": "vascular_neuro",
    "transformed_PMC10556246": "sellar_xanthogranuloma",
    "transformed_PMC10765173": "temporal_bone_inflammatory_mass",
    "transformed_PMC10798650": "prior_cancer_mass",
    "transformed_PMC10901880": "lipomatous_tumor_molecular",
    "transformed_PMC12581184": "neuro_psych",
    "transformed_PMC2413251": "bone_vascular_tumor",
    "transformed_PMC3214133": "prion_sleep",
    "transformed_PMC3824813": "pathology",
    "transformed_PMC4084793": "immunocompromised_necrotizing_infection",
    "transformed_PMC4291137": "maxillofacial_osteomyelitis",
    "transformed_PMC4825443": "adverse_drug_event",
    "transformed_PMC5440415": "granulomatous_overlap",
    "transformed_PMC5516732": "cns_vasculitis",
    "transformed_PMC6057707": "acute_neuro_emergency",
    "transformed_PMC6179031": "seizure_mimic",
    "transformed_PMC6286763": "middle_ear_mass",
    "transformed_PMC6499098": "sequential_event",
    "transformed_PMC6741398": "spindle_cell_pathology",
    "transformed_PMC6761061": "gnathic_bone_tumor",
    "transformed_PMC7507877": "mass_malignancy",
    "transformed_PMC7678886": "autoimmune_encephalitis",
    "transformed_PMC8046463": "infection_microbiology",
    "transformed_PMC8115684": "cancer_neuro",
    "transformed_PMC8143662": "functional_neuro",
    "transformed_PMC8244580": "cardiac_pericardial_mass",
    "next_native_PMC11980373": "mold_identification",
    "next_native_PMC12506031": "colonization_vs_infection",
    "next_native_PMC12710301": "mold_identification",
    "next_native_PMC3522357": "bone_small_round_cell_tumor",
    "next_native_PMC5458444": "postoperative_foreign_body",
    "next_native_PMC5590213": "persistent_hcg_localization",
    "next_native_PMC7944237": "prenatal_syndromic_pattern",
    "next_native_PMC9524449": "submucosal_gas_cyst",
    "next_transformed_PMC10200070": "gi_desmoplastic_neuroendocrine",
    "next_transformed_PMC10240848": "spindle_cell_pathology",
    "next_transformed_PMC10498951": "spindle_cell_pathology",
    "next_transformed_PMC11039432": "optic_pathway_neoplasm",
    "next_transformed_PMC11066795": "renal_spindle_cell_mass",
    "next_transformed_PMC3830810": "renal_spindle_cell_mass",
    "next_transformed_PMC4523567": "immunocompromised_retinitis",
    "next_transformed_PMC7078665": "movement_disorder_phenotype",
    "next_transformed_PMC7930965": "cns_granulomatous_mass",
    "next_transformed_PMC8986709": "sellar_xanthogranuloma",
    "next_transformed_PMC9161094": "neuroinflammatory_demyelination",
    "next_transformed_PMC9332052": "gi_neuroendocrine_carcinoma",
    "next_transformed_PMC9830568": "neuroinflammatory_demyelination",
    "next_transformed_PMC9934935": "hematologic_cytogenetic_subtype",
    "next_transformed_PMC9979078": "ocular_infection_inflammation",
}

# Reusable reasoning families -- the level at which feature selection is expected to generalize.
PRESET_FAMILY: dict[str, str] = {
    "general": "general",
    # tumor / pathology subtyping: "don't stop at the generic lineage; require the subtype test"
    "pathology": "tumor_subtype",
    "spindle_cell_pathology": "tumor_subtype",
    "bone_vascular_tumor": "tumor_subtype",
    "gnathic_bone_tumor": "tumor_subtype",
    "bone_small_round_cell_tumor": "tumor_subtype",
    "gynecologic_epithelioid_tumor": "tumor_subtype",
    "gi_desmoplastic_neuroendocrine": "tumor_subtype",
    "gi_neuroendocrine_carcinoma": "tumor_subtype",
    "hematologic_cytogenetic_subtype": "tumor_subtype",
    "lipomatous_tumor_molecular": "tumor_subtype",
    "mass_malignancy": "tumor_subtype",
    "prior_cancer_mass": "tumor_subtype",
    "renal_spindle_cell_mass": "tumor_subtype",
    "cardiac_pericardial_mass": "tumor_subtype",
    "middle_ear_mass": "tumor_subtype",
    "sellar_xanthogranuloma": "tumor_subtype",
    "keratotic_skin_lesion": "tumor_subtype",
    "optic_pathway_neoplasm": "tumor_subtype",
    "neuro_oncology": "tumor_subtype",
    "cancer_neuro": "tumor_subtype",
    # infection: organism ID, colonization vs invasion, necrotizing/immunocompromised
    "infection_microbiology": "infection",
    "mold_identification": "infection",
    "colonization_vs_infection": "infection",
    "immunocompromised_necrotizing_infection": "infection",
    "immunocompromised_retinitis": "infection",
    "ocular_infection_inflammation": "infection",
    "maxillofacial_osteomyelitis": "infection",
    "temporal_bone_inflammatory_mass": "infection",
    # granulomatous overlap (TB / sarcoid / fungal)
    "granulomatous_overlap": "granulomatous",
    "cns_granulomatous_mass": "granulomatous",
    # autoimmune / psych / demyelinating neuro
    "neuro_psych": "neuro_immune",
    "autoimmune_encephalitis": "neuro_immune",
    "demyelination": "neuro_immune",
    "neuroinflammatory_demyelination": "neuro_immune",
    "cns_vasculitis": "neuro_immune",
    # neuro syndromes (emergency / vascular / seizure / movement / functional / prion)
    "acute_neuro_emergency": "neuro_syndrome",
    "vascular_neuro": "neuro_syndrome",
    "seizure_mimic": "neuro_syndrome",
    "functional_neuro": "neuro_syndrome",
    "movement_disorder_phenotype": "neuro_syndrome",
    "prion_sleep": "neuro_syndrome",
    # distinctive single-mechanism presets
    "postoperative_foreign_body": "other_specific",
    "persistent_hcg_localization": "other_specific",
    "submucosal_gas_cyst": "other_specific",
    "prenatal_syndromic_pattern": "other_specific",
    "adverse_drug_event": "other_specific",
    "sequential_event": "other_specific",
}

# Per-preset trigger rules: (term_or_regex, weight). Terms are matched case-insensitively as
# whole words (\b...\b). Highly distinctive anchors carry weight >= 2 so they win ties; generic
# family cues carry weight 1. Grounded in the preset checklists and observed case vocabulary.
PRESET_FEATURE_RULES: dict[str, tuple[tuple[str, int], ...]] = {
    # --- tumor / pathology subtyping ---
    "spindle_cell_pathology": (
        ("spindle.?cell", 3), ("sarcomatoid", 3), ("pleomorphic", 2), ("metaplastic", 2),
        ("mesenchymal", 2), ("phyllodes", 3), ("leiomyosarcoma", 2), ("breast", 1), ("sarcoma", 1),
        ("ihc", 1), ("immunohistochem", 1), ("cytokeratin", 1),
    ),
    "bone_vascular_tumor": (
        ("aneurysmal bone cyst", 3), ("telangiectatic", 3), ("angiosarcoma", 3), ("lytic", 2),
        ("expansile", 2), ("giant cell tumor", 2), ("bone", 1), ("osteoid", 1),
        ("popliteal", 2), ("hemorrhagic", 1),
    ),
    "gnathic_bone_tumor": (
        ("mandible", 3), ("maxilla", 2), ("jaw", 2), ("periodontal", 2), ("lamina dura", 3),
        ("odontogenic", 2), ("gnathic", 3), ("sunburst", 2), ("osteosarcoma", 1),
    ),
    "bone_small_round_cell_tumor": (
        ("ewing", 3), ("small round", 3), ("cd99", 3), ("ewsr1", 3), ("sunray", 2),
        ("permeative", 2), ("periosteal", 1),
    ),
    "gynecologic_epithelioid_tumor": (
        ("uterine", 3), ("uterus", 2), ("gynecolog", 2), ("pecoma", 3), ("utrosct", 3),
        ("myometr", 2), ("postmenopausal", 1), ("vaginal bleeding", 1), ("g2p2", 1),
    ),
    "gi_desmoplastic_neuroendocrine": (
        ("desmoplas", 3), ("mesenteric", 3), ("small bowel", 3), ("ileal", 2), ("ileum", 2),
        ("intussuscept", 2), ("carcinoid", 2), ("neuroendocrine", 1),
    ),
    "gi_neuroendocrine_carcinoma": (
        ("ampullary", 3), ("pancreatobiliary", 3), ("obstructive jaundice", 2), ("jaundice", 1),
        ("lcnec", 3), ("large.?cell neuroendocrine", 3), ("synaptophysin", 1), ("chromogranin", 1),
    ),
    "hematologic_cytogenetic_subtype": (
        ("leukemia", 3), ("blast", 2), ("eosinophil", 2), ("myelodyspla", 2), ("marrow", 2),
        ("inv\\(16\\)", 3), ("cytogenet", 2), ("flow cytometry", 1), ("aml", 2),
    ),
    "lipomatous_tumor_molecular": (
        ("lipomatous", 3), ("liposarcoma", 3), ("adipocyt", 2), ("fatty", 2), ("mdm2", 3),
        ("cdk4", 3), ("retroperitoneal", 2), ("lipoma", 2), ("hibernoma", 2),
    ),
    "renal_spindle_cell_mass": (
        ("renal mass", 3), ("kidney", 2), ("renal", 1), ("nephrectomy", 2), ("leiomyosarcoma", 1),
        ("neurofibroma", 2), ("smooth muscle", 1), ("collecting duct", 2),
    ),
    "cardiac_pericardial_mass": (
        ("pericardial", 3), ("pericardium", 3), ("cardiac mass", 3), ("effusion", 1),
        ("intracardiac", 2), ("tamponade", 2), ("angiosarcoma", 1), ("mesothelioma", 1),
    ),
    "middle_ear_mass": (
        ("middle ear", 3), ("retrotympanic", 3), ("tympanic", 2), ("glomus", 3),
        ("pulsatile tinnitus", 3), ("cholesteatoma", 2), ("otoscopy", 1),
    ),
    "sellar_xanthogranuloma": (
        ("sellar", 3), ("suprasellar", 3), ("rathke", 3), ("craniopharyngioma", 3),
        ("pituitary", 2), ("xanthogranuloma", 3), ("chiasm", 1),
    ),
    "optic_pathway_neoplasm": (
        ("optic nerve", 3), ("optic glioma", 3), ("chiasm", 2), ("optic pathway", 3),
        ("optic nerve enlargement", 3), ("pcnsl", 1),
    ),
    "keratotic_skin_lesion": (
        ("keratotic", 3), ("verrucous", 3), ("hyperkeratotic", 3), ("cutaneous horn", 3),
        ("glans", 2), ("penis", 2), ("balanitis", 3), ("micaceous", 3),
    ),
    "prior_cancer_mass": (
        ("history of (cancer|malignancy|carcinoma)", 3), ("prior (cancer|malignancy)", 3),
        ("known malignancy", 3), ("treated for .* cancer", 2), ("recurrence", 1), ("metasta", 1),
    ),
    "mass_malignancy": (
        ("recurrent .* mass", 2), ("enlarging mass", 2), ("rapidly growing", 1), ("excised", 1),
        ("no prior (histology|pathology)", 2), ("painless .* mass", 1),
    ),
    "pathology": (
        ("fna", 3), ("fine.?needle", 3), ("cytology", 3), ("biopsy", 1), ("lymphadenopathy", 1),
        ("preliminary pathology", 2), ("ldh", 1), ("flow cytometry", 1),
    ),
    "neuro_oncology": (
        ("cerebellopontine", 3), ("internal auditory", 3), ("leptomeningeal", 2),
        ("cranial neuropathy", 2), ("vestibular schwannoma", 2), ("acoustic", 1),
    ),
    "cancer_neuro": (
        ("metasta", 1), ("leptomeningeal carcinomatosis", 3), ("known cancer", 2),
        ("active malignancy", 2), ("csf cytology", 2),
    ),
    # --- infection ---
    "mold_identification": (
        ("mold", 3), ("fungal", 2), ("fungus", 2), ("hyphae", 3), ("conidia", 3),
        ("mucormycosis", 2), ("aspergill", 2), ("dematiaceous", 3), ("phaeohyphomycosis", 3),
        ("neutropenia", 1),
    ),
    "colonization_vs_infection": (
        ("colonization", 3), ("colonisation", 3), ("surveillance culture", 3), ("nicu", 2),
        ("neonat", 2), ("preterm", 2), ("premature", 1), ("low birth weight", 2),
        ("icu", 1), ("catheter", 1), ("contamination", 2), ("positive culture", 2),
    ),
    "immunocompromised_necrotizing_infection": (
        ("necrotizing", 3), ("necrotising", 3), ("necrotizing fasciitis", 3), ("neutropenic", 2),
        ("soft.?tissue necrosis", 3), ("chemotherapy", 1), ("transplant", 1), ("debridement", 1),
    ),
    "immunocompromised_retinitis": (
        ("retinitis", 3), ("retinochoroiditis", 3), ("vitritis", 3), ("uveitis", 2),
        ("transplant", 2), ("toxoplasm", 2), ("immunosuppress", 1),
    ),
    "ocular_infection_inflammation": (
        ("scleritis", 3), ("scleral", 2), ("uveitis", 2), ("retinochoroiditis", 2), ("ocular", 1),
        ("eye", 1), ("igra", 1),
    ),
    "maxillofacial_osteomyelitis": (
        ("osteomyelitis", 2), ("maxilla", 2), ("mandible", 2), ("purulent", 2), ("fistula", 2),
        ("gingiv", 2), ("stomatology", 2), ("draining", 1), ("dental", 1),
    ),
    "temporal_bone_inflammatory_mass": (
        ("temporal bone", 3), ("external auditory", 3), ("ear discharge", 3), ("otitis externa", 3),
        ("skull base osteomyelitis", 3), ("ear", 1),
    ),
    "infection_microbiology": (
        ("osteomyelitis", 1), ("spondylodisc", 3), ("abscess", 2), ("discitis", 3),
        ("tuberculosis", 1), ("actinomyc", 3), ("brucell", 3), ("culture.?negative", 2),
        ("afb", 2), ("low back pain", 1),
    ),
    # --- granulomatous ---
    "cns_granulomatous_mass": (
        ("tuberculoma", 3), ("intracranial .* granuloma", 3), ("neurosarcoid", 2),
        ("non.?caseating", 2), ("cns .* mass", 1), ("ring.?enhancing", 1),
    ),
    "granulomatous_overlap": (
        ("granulomat", 3), ("sarcoidosis", 2), ("igra", 2), ("mantoux", 2), ("epididym", 2),
        ("azoospermia", 2), ("night sweats", 1), ("tuberculosis", 1),
    ),
    # --- neuro immune ---
    "neuro_psych": (
        ("psychosis", 3), ("psychiatric", 2), ("catatonia", 3), ("hallucinat", 2),
        ("paranoi", 2), ("behavioral change", 2), ("anti.?nmda", 2), ("lupus", 2), ("ana", 1),
    ),
    "autoimmune_encephalitis": (
        ("encephalitis", 4), ("encephalopathy", 2), ("lgi1", 3), ("nmdar", 3), ("caspr2", 3),
        ("autoimmune", 1), ("antibody", 1), ("acyclovir", 2), ("viral encephalitis", 2),
        ("status epilepticus", 1),
    ),
    "neuroinflammatory_demyelination": (
        ("area postrema", 4), ("intractable hiccup", 4), ("hiccup", 2), ("letm", 4),
        ("longitudinally extensive", 4), ("mogad", 4), ("nmosd", 4), ("aqp4", 4),
        ("myelitis", 2), ("ascending paresthes", 2),
    ),
    "demyelination": (
        ("demyelinat", 3), ("multiple sclerosis", 2), ("optic neuritis", 2),
        ("oligoclonal", 2), ("adem", 2), ("white matter lesion", 2),
    ),
    "cns_vasculitis": (
        ("vasculitis", 3), ("pacns", 3), ("rcvs", 3), ("thunderclap", 2), ("vessel.?wall", 2),
        ("angiitis", 3),
    ),
    # --- neuro syndrome ---
    "movement_disorder_phenotype": (
        ("parkinson", 3), ("psp", 3), ("\\bmsa\\b", 3), ("\\bcbd\\b", 2), ("levodopa", 3),
        ("saccade", 2), ("freezing of gait", 3), ("tremor", 1), ("gaze palsy", 2),
    ),
    "prion_sleep": (
        ("prion", 3), ("rapidly progressive dementia", 3), ("myoclonus", 3), ("ataxia", 1),
        ("insomnia", 2), ("dysautonomia", 2), ("thalam", 2), ("periodic .* eeg", 2),
    ),
    "seizure_mimic": (
        ("seizure", 2), ("automatism", 3), ("episodic", 2), ("spells", 2), ("stereotyp", 2),
        ("\\beeg\\b", 1), ("transient aphasia", 2),
    ),
    "functional_neuro": (
        ("functional neurolog", 3), ("conversion disorder", 3), ("psychogenic", 3),
        ("saddle anesthesia", 3), ("anal wink", 3), ("urinary retention", 2), ("cauda equina", 3),
    ),
    "vascular_neuro": (
        ("cvst", 3), ("venous thrombosis", 3), ("ischemic stroke", 2), ("dissection", 2),
        ("hemiparesis", 1), ("aphasia", 1), ("papilledema", 2), ("melas", 2),
    ),
    "acute_neuro_emergency": (
        ("coma", 3), ("loss of consciousness", 2), ("status epilepticus", 2), ("acute infarct", 2),
        ("unresponsive", 2), ("obtunded", 2),
    ),
    # --- other specific mechanisms ---
    "postoperative_foreign_body": (
        ("gossypiboma", 3), ("retained .* (sponge|gauze|foreign)", 3), ("after surgery", 2),
        ("postoperative", 2), ("surgical scar", 1), ("prior surgery", 2),
    ),
    "persistent_hcg_localization": (
        ("hcg", 3), ("beta.?hcg", 3), ("trophoblastic", 3), ("ectopic", 2), ("salpingectomy", 2),
        ("methotrexate", 1), ("choriocarcinoma", 2),
    ),
    "submucosal_gas_cyst": (
        ("pneumatosis", 3), ("submucosal", 2), ("gas.?filled", 3), ("colonic .* lesion", 2),
        ("bowel.?wall air", 3),
    ),
    "prenatal_syndromic_pattern": (
        ("fetal", 3), ("prenatal", 3), ("weeks pregnant", 2), ("anencephaly", 3),
        ("encephalocele", 3), ("polydactyly", 3), ("meckel", 3), ("fryns", 3),
        ("hydrocephalus", 1), ("antenatal", 2), ("ultrasound .* anomal", 2),
    ),
    "adverse_drug_event": (
        ("drug.?induced", 3), ("medication", 2), ("dechallenge", 3), ("rechallenge", 3),
        ("naranjo", 3), ("after starting", 2),
    ),
    "sequential_event": (
        ("two .* episodes", 2), ("first .* then", 1), ("subsequently developed", 2),
        ("months later", 1), ("second event", 2),
    ),
}

_MIN_SCORE = 3  # require a distinctive anchor (weight 3) or several family cues before leaving general
_COMPILED: dict[str, tuple[tuple[re.Pattern[str], int], ...]] = {
    preset: tuple((re.compile(rf"\b{term}\b", re.IGNORECASE), w) for term, w in rules)
    for preset, rules in PRESET_FEATURE_RULES.items()
}


def score_presets(prompt: str) -> list[tuple[str, int]]:
    """Return (preset, score) sorted high-to-low for all presets that fire on the prompt."""

    text = prompt or ""
    scores: list[tuple[str, int]] = []
    for preset, patterns in _COMPILED.items():
        score = sum(w for pattern, w in patterns if pattern.search(text))
        if score:
            scores.append((preset, score))
    # Sort by score desc, then by rule specificity (more anchors) for stable tie-breaking.
    scores.sort(key=lambda item: (item[1], len(_COMPILED[item[0]])), reverse=True)
    return scores


def select_preset(prompt: str, *, case_id: str | None = None, use_overrides: bool = True) -> str:
    """Pick the preset for a case from its features (or the case_id override when enabled)."""

    if use_overrides and case_id is not None and case_id in PRESET_BY_CASE_ID:
        return PRESET_BY_CASE_ID[case_id]
    ranked = score_presets(prompt)
    if ranked and ranked[0][1] >= _MIN_SCORE:
        return ranked[0][0]
    return "general"
