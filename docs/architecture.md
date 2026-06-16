# Architecture

ClinicalHarness is intended to evaluate whether a tool-using model can solve hard diagnosis cases by combining retrieval and reasoning.

ClinicalHarness owns the diagnosis-attempt engine. The sibling NeurologyBM repo owns dataset and benchmark creation, including source licensing, benchmark item construction, and split manifests. ClinicalHarness should consume NeurologyBM exports rather than independently building benchmark datasets.

## Core Objects

- `ClinicalCase`: the benchmark prompt, answer key, allowed tools, and metadata.
- `ProblemRepresentation`: a compact, model-visible summary of demographics, tempo, localization, and key findings.
- `SearchQuery`: a generated or manually supplied search string with source constraints.
- `EvidenceRecord`: a retrieved article, abstract, guideline, or web result with provenance.
- `CandidateDiagnosis`: a possible diagnosis, aliases, supporting evidence, refuting evidence, and confidence.
- `StructuredAnswer`: final diagnosis, localization, differential, next tests, citations, and confidence.
- `RunManifest`: run id, mode, case id, artifact paths, source controls, status, and environment metadata.
- `ModelCallRecord`: provider, model, role, prompt id, response id, token counts, cost estimate, latency, and error state.

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
- PMC full text for open-access articles: initial ESearch/EFetch/JATS parsing is implemented
- Crossref for DOI metadata
- Semantic Scholar for citation/context graphs
- General web search for allowed challenge workflows
- LLM APIs for query generation, evidence extraction, synthesis, and judging

## Evaluation Modes

- `closed_book`: no retrieval; model answers from prompt only.
- `pubmed_only`: PubMed abstracts only.
- `pubmed_only_source_excluded`: PubMed abstracts with records matching declared source PMID, DOI, or title excluded.
- `open_literature`: PubMed plus PMC full text and citation metadata.
- `web_enabled`: general search plus web pages where allowed.

Each mode should be reproducible from a run manifest.

## Current Runner

The current `clinical-harness case run` command loads one JSON case, creates `runs/<run_id>/`, writes an append-only event log, generates template PubMed queries, optionally retrieves PubMed abstracts, and writes a low-confidence placeholder structured answer. PMC search/fetch exists as a CLI substrate, but the case runner does not yet use PMC full text. It does not call LLM APIs.

See [Project Split](project_split.md) for the shared case interface and coordination rules with NeurologyBM.
