# Architecture

ClinicalOrchestra is intended to evaluate whether a tool-using model can solve hard diagnosis cases by combining retrieval and reasoning.

## Core Objects

- `ClinicalCase`: the benchmark prompt, answer key, allowed tools, and metadata.
- `SearchQuery`: a generated or manually supplied search string with source constraints.
- `EvidenceRecord`: a retrieved article, abstract, guideline, or web result with provenance.
- `CandidateDiagnosis`: a possible diagnosis, aliases, supporting evidence, refuting evidence, and confidence.
- `RunTrace`: every query, API call, retrieved record, model response, and scoring decision.

## Retrieval Stages

1. `problem_representation`: compress the case into age, tempo, syndrome, localization, key positives, key negatives, and red flags.
2. `query_generation`: create high-recall and high-precision queries.
3. `literature_search`: run PubMed and later other APIs.
4. `evidence_filtering`: rank articles by diagnosis relevance and source quality.
5. `diagnostic_synthesis`: map evidence to differential diagnoses.
6. `answer_generation`: produce final diagnosis, localization, differential, and next tests.
7. `scoring`: compare against benchmark answer and rubric.

## Near-Term API Targets

- PubMed / NCBI E-Utilities
- PMC full text for open-access articles
- Crossref for DOI metadata
- Semantic Scholar for citation/context graphs
- General web search for allowed challenge workflows
- LLM APIs for query generation, evidence extraction, synthesis, and judging

## Evaluation Modes

- `closed_book`: no retrieval; model answers from prompt only.
- `pubmed_only`: PubMed abstracts only.
- `open_literature`: PubMed plus PMC full text and citation metadata.
- `web_enabled`: general search plus web pages where allowed.

Each mode should be reproducible from a run manifest.
