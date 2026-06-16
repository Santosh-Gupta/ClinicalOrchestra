import unittest

from clinical_harness.pmc import normalize_pmcid, parse_pmc_xml


SAMPLE_PMC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<pmc-articleset>
  <article article-type="case-report">
    <front>
      <journal-meta>
        <journal-title-group>
          <journal-title>Journal of Open Neurology</journal-title>
        </journal-title-group>
      </journal-meta>
      <article-meta>
        <article-id pub-id-type="pmc">7654321</article-id>
        <article-id pub-id-type="pmid">12345</article-id>
        <article-id pub-id-type="doi">10.0000/pmc-example</article-id>
        <title-group>
          <article-title>Seronegative autoimmune encephalitis case report</article-title>
        </title-group>
        <pub-date><year>2026</year></pub-date>
        <permissions>
          <license license-type="open-access" />
        </permissions>
        <abstract>
          <p>A patient developed subacute seizures and psychiatric symptoms.</p>
        </abstract>
      </article-meta>
    </front>
    <body>
      <sec>
        <title>Case presentation</title>
        <p>The patient had CSF pleocytosis, seizures, and a normal MRI.</p>
      </sec>
      <sec>
        <title>Discussion</title>
        <p>Seronegative autoimmune encephalitis can meet clinical criteria.</p>
      </sec>
    </body>
  </article>
</pmc-articleset>
"""


class PmcParseTests(unittest.TestCase):
    def test_normalize_pmcid(self) -> None:
        self.assertEqual(normalize_pmcid("123"), "PMC123")
        self.assertEqual(normalize_pmcid("PMC123"), "PMC123")
        self.assertEqual(normalize_pmcid("pmc123"), "PMC123")

    def test_parse_pmc_xml(self) -> None:
        articles = parse_pmc_xml(SAMPLE_PMC_XML)

        self.assertEqual(len(articles), 1)
        article = articles[0]
        self.assertEqual(article.pmcid, "PMC7654321")
        self.assertEqual(article.pmid, "12345")
        self.assertEqual(article.doi, "10.0000/pmc-example")
        self.assertEqual(article.title, "Seronegative autoimmune encephalitis case report")
        self.assertEqual(article.journal, "Journal of Open Neurology")
        self.assertEqual(article.publication_year, "2026")
        self.assertEqual(article.license_type, "open-access")
        self.assertIn("subacute seizures", article.abstract or "")
        self.assertEqual(len(article.sections), 2)
        self.assertEqual(article.sections[0].title, "Case presentation")
        self.assertIn("CSF pleocytosis", article.sections[0].text)
        self.assertEqual(article.url, "https://pmc.ncbi.nlm.nih.gov/articles/PMC7654321/")


if __name__ == "__main__":
    unittest.main()
