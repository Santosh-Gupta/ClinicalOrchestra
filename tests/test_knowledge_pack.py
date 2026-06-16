import unittest

from clinical_harness.knowledge_pack import KNOWLEDGE_CARDS, match_cards


class KnowledgePackTests(unittest.TestCase):
    def test_matches_slc6a1_phenotype(self) -> None:
        text = ("A child with typical absence seizures at 3 Hz spike and wave and mild cognitive "
                "deficit; MRI normal.")
        cards = match_cards(text, max_cards=3)
        self.assertTrue(any("SLC6A1" in c.entity for c in cards))

    def test_matches_drug_induced_parkinsonism_on_datscan(self) -> None:
        text = "Parkinsonism with tremor; DaTscan was normal; patient on valproate."
        cards = match_cards(text)
        self.assertTrue(any("Drug-induced parkinsonism" in c.entity for c in cards))

    def test_unrelated_case_matches_nothing(self) -> None:
        text = "A 30-year-old with a sprained ankle after a fall playing basketball."
        self.assertEqual(match_cards(text), ())

    def test_precision_requires_a_phrase_match_not_single_word(self) -> None:
        # "tremor" alone (one generic word) must not pull in tremor-related cards.
        self.assertEqual(match_cards("The patient had a mild tremor."), ())

    def test_cards_have_source_and_confirmatory_test(self) -> None:
        for c in KNOWLEDGE_CARDS:
            self.assertTrue(c.confirmatory_test)
            self.assertTrue(c.triggers)
            self.assertTrue(c.source_pmcid or c.source_pmid)

    def test_prompt_dict_shape(self) -> None:
        d = KNOWLEDGE_CARDS[0].to_prompt_dict()
        for k in ("consider_entity", "discriminator_vs_near_neighbors", "confirmatory_test", "raised_by"):
            self.assertIn(k, d)


if __name__ == "__main__":
    unittest.main()
