"""Corrected challenge prompts for two transformed cases whose transformation dropped the
discriminating findings required to reach the keyed diagnosis.

Both were flagged ``refined_needs_spotcheck`` in NeurologyBM. The corrections restore, from the
CC-BY / CC-BY-NC source articles, the objective findings a clinician needs — WITHOUT naming the
diagnosis or leaking the outcome.

- transformed_PMC12581184 (NPSLE): the transform dropped the ANA 1:1280 and anti-dsDNA >300 IU/mL
  serologies and fabricated a subcortical white-matter MRI finding (source MRI/CT were negative).
- next_transformed_PMC11066795 (intrarenal neurofibroma): the transform withheld ALL nephrectomy
  histopathology (the prompt left histology "pending"), making a pathological diagnosis
  impossible. Restored the gross + microscopic + IHC findings.

See docs/dataset_prompt_fixes_20260613.md for the before/after rationale.
"""

CORRECTED_PROMPTS: dict[str, str] = {
    "transformed_PMC12581184": (
        "A 19-year-old previously healthy female presented with a 5-day history of acute-onset "
        "psychosis (paranoia, auditory hallucinations, insomnia) with marked disorganization and "
        "severely reduced oral intake. She was severely malnourished (BMI 14.3 kg/m^2). Examination "
        "revealed no fever, normal vital signs, and no focal neurological deficits. CBC, CMP, TSH, "
        "and urine toxicology were unremarkable. CSF analysis showed a mild lymphocytic pleocytosis "
        "(WBC 17 cells/uL), protein 52 mg/dL, normal glucose, and negative bacterial cultures. An "
        "infectious workup (HSV, VZV, HIV, syphilis serologies, and CSF viral PCRs) was negative; "
        "she had a remote history of treated ehrlichiosis with tick exposure. Two brain MRIs and "
        "two head CTs were negative for acute intracranial pathology. Serologic testing returned a "
        "positive antinuclear antibody (ANA) at 1:1280 titer and a markedly elevated anti-double-"
        "stranded DNA (anti-dsDNA) antibody at >300 IU/mL. What is the most likely diagnosis, and "
        "what is the most appropriate next step in management?"
    ),
    "next_transformed_PMC11066795": (
        "A 53-year-old male with hypertension (10 years), diabetes mellitus (20 years), and ischemic "
        "heart disease (prior PCI) was found to have an elevated serum creatinine (1.6 mg/dL) on "
        "routine diabetes follow-up; prior creatinine was normal. He denied hematuria, flank pain, "
        "weight loss, anorexia, or decreased intake, and had no prior urologic surgery or family "
        "history of kidney tumors. Abdominal ultrasound showed a large, well-defined hypoechoic "
        "medullary lesion with internal heterogeneity and minimal vascularity (~6.7 x 7.4 cm) "
        "abutting the inner left renal cortex. Non-contrast CT showed a well-defined rounded soft-"
        "tissue mass (6.7 x 6.4 x 7.9 cm) in the lower left renal medulla. Gadolinium MRI showed a "
        "well-defined rounded lesion, hypointense on T1 and heterogeneously hyperintense on T2, in "
        "the lower medulla with mild calyceal dilatation and mild heterogeneous, delayed-phase "
        "enhancement; two small para-aortic lymph nodes (largest 1.2 cm) were noted, with no distant "
        "metastasis on chest imaging. Because the mass was suspicious for malignancy, the patient "
        "underwent left radical nephrectomy with removal of the para-aortic lymph nodes. Gross "
        "examination showed a 6 x 6 x 5 cm well-circumscribed, encapsulated tumor with yellowish cut "
        "surfaces, confined to the lower pole and not invading Gerota's fascia. Microscopy showed a "
        "spindle-cell tumor with serpentine, wavy nuclei arranged in a fascicular pattern. "
        "Immunohistochemistry: tumor cells focally positive for S100 and negative for smooth muscle "
        "actin (SMA) and desmin. The para-aortic lymph nodes were free of malignancy. What is the "
        "most likely pathological diagnosis, and what is the most appropriate next step in management?"
    ),
}
