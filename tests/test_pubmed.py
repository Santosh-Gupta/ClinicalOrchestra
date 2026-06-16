import unittest

from clinical_harness.pubmed import parse_pubmed_xml


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <PubDate><Year>2025</Year></PubDate>
          </JournalIssue>
          <Title>Journal of Neurology Cases</Title>
        </Journal>
        <ArticleTitle>Autoimmune encephalitis presenting as psychosis</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Autoimmune encephalitis can mimic psychiatric disease.</AbstractText>
          <AbstractText Label="CASE">A patient presented with psychosis and seizures.</AbstractText>
        </Abstract>
        <PublicationTypeList>
          <PublicationType>Case Reports</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.0000/example</ArticleId>
        <ArticleId IdType="pmc">PMC1234567</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


class PubMedParseTests(unittest.TestCase):
    def test_parse_pubmed_xml(self) -> None:
        articles = parse_pubmed_xml(SAMPLE_XML)

        self.assertEqual(len(articles), 1)
        article = articles[0]
        self.assertEqual(article.pmid, "12345")
        self.assertEqual(article.title, "Autoimmune encephalitis presenting as psychosis")
        self.assertEqual(article.journal, "Journal of Neurology Cases")
        self.assertEqual(article.publication_year, "2025")
        self.assertEqual(article.publication_types, ("Case Reports",))
        self.assertEqual(article.doi, "10.0000/example")
        self.assertEqual(article.pmcid, "PMC1234567")
        self.assertIn("BACKGROUND:", article.abstract or "")
        self.assertEqual(article.url, "https://pubmed.ncbi.nlm.nih.gov/12345/")


if __name__ == "__main__":
    unittest.main()
