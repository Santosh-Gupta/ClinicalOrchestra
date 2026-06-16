import unittest

from clinical_harness.consensus import consensus_diagnosis


class ConsensusTests(unittest.TestCase):
    def test_majority_wins(self) -> None:
        r = consensus_diagnosis([
            "Myeloid sarcoma",
            "Myeloid sarcoma (granulocytic sarcoma)",
            "Diffuse large B-cell lymphoma",
            "Myeloid sarcoma",
        ])
        self.assertIn("yeloid sarcoma", r.consensus)
        self.assertEqual(r.cluster_size, 3)
        self.assertEqual(r.n_samples, 4)
        self.assertAlmostEqual(r.agreement, 0.75)

    def test_qualifier_variants_cluster_together(self) -> None:
        # Grade/stage/"provisional" qualifiers must not split equivalent answers (string-level).
        r = consensus_diagnosis([
            "Esophageal carcinosarcoma",
            "Provisional esophageal carcinosarcoma (spindle cell squamous carcinoma)",
            "esophageal carcinosarcoma, high grade",
        ])
        self.assertEqual(r.cluster_size, 3)
        self.assertAlmostEqual(r.agreement, 1.0)

    def test_representative_is_most_specific(self) -> None:
        r = consensus_diagnosis([
            "Neurofibroma",
            "Intrarenal neurofibroma (benign peripheral nerve sheath tumor)",
        ])
        self.assertEqual(r.cluster_size, 2)
        self.assertIn("neurofibroma", r.consensus.lower())
        self.assertIn("intrarenal", r.consensus.lower())  # picks the more specific phrasing

    def test_empty_samples_lower_agreement(self) -> None:
        r = consensus_diagnosis(["Hibernoma", "", "Hibernoma"])
        self.assertEqual(r.n_samples, 3)
        self.assertEqual(r.cluster_size, 2)
        self.assertAlmostEqual(r.agreement, 2 / 3)

    def test_all_empty_returns_none(self) -> None:
        r = consensus_diagnosis(["", "  ", ""])
        self.assertIsNone(r.consensus)
        self.assertEqual(r.agreement, 0.0)

    def test_distinct_entities_split(self) -> None:
        r = consensus_diagnosis([
            "Kaposi sarcoma",
            "Pulmonary angiosarcoma",
            "Invasive aspergillosis",
        ])
        # three different entities -> no majority above 1
        self.assertEqual(r.cluster_size, 1)
        self.assertAlmostEqual(r.agreement, 1 / 3)


if __name__ == "__main__":
    unittest.main()
