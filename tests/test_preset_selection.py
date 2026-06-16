import unittest

from clinical_harness.preset_selection import (
    PRESET_BY_CASE_ID,
    PRESET_FAMILY,
    score_presets,
    select_preset,
)


class PresetSelectionTests(unittest.TestCase):
    def test_override_takes_precedence(self) -> None:
        # A known case keeps its hand-tuned preset regardless of prompt features.
        self.assertEqual(
            select_preset("totally unrelated text", case_id="transformed_PMC12581184"),
            "neuro_psych",
        )

    def test_override_can_be_disabled(self) -> None:
        # With overrides off, selection is feature-driven even for a known case_id.
        chosen = select_preset(
            "A man with a renal mass; biopsy shows spindle cells, query leiomyosarcoma.",
            case_id="transformed_PMC12581184",
            use_overrides=False,
        )
        self.assertEqual(PRESET_FAMILY[chosen], "tumor_subtype")

    def test_feature_selection_for_unknown_case(self) -> None:
        prompt = (
            "A 19-year-old woman with acute psychosis, paranoia, and catatonia; "
            "ANA positive, query lupus versus anti-NMDA encephalitis."
        )
        self.assertEqual(select_preset(prompt, case_id="brand_new_case"), "neuro_psych")

    def test_infection_routing(self) -> None:
        prompt = "Neutropenic child after chemotherapy with invasive mold; hyphae on microscopy."
        chosen = select_preset(prompt, case_id="new_x")
        self.assertEqual(PRESET_FAMILY[chosen], "infection")

    def test_weak_signal_falls_back_to_general(self) -> None:
        self.assertEqual(select_preset("A patient felt unwell for a few days.", case_id="z"), "general")

    def test_emergency_department_does_not_trigger_acute_neuro(self) -> None:
        # Regression: the bare word "emergency" must not route ER visits to acute_neuro_emergency.
        scores = dict(score_presets("She presented to the emergency department with a rash."))
        self.assertNotIn("acute_neuro_emergency", scores)

    def test_every_preset_has_a_family(self) -> None:
        for preset in set(PRESET_BY_CASE_ID.values()):
            self.assertIn(preset, PRESET_FAMILY, f"{preset} missing from PRESET_FAMILY")


if __name__ == "__main__":
    unittest.main()
