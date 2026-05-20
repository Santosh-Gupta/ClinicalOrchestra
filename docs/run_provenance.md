# Run Provenance

ClinicalOrchestra should be reproducible from run manifests. Every benchmark attempt should leave enough trace data to understand what the model saw, what it searched, what evidence it used, and why it produced an answer.

## Run Manifest

Each future run should record:

- run id
- timestamp
- git commit
- evaluation mode
- benchmark case id
- model ids and API versions
- tool list
- allowed sources
- search queries
- retrieved evidence ids
- prompts sent to LLMs
- model outputs
- scoring outputs
- cost and latency summary

## Evidence Record

Every retrieved evidence item should include:

```json
{
  "evidence_id": "pubmed:40952037",
  "source_api": "pubmed",
  "query": "autoimmune encephalitis psychosis catatonia case report",
  "rank": 1,
  "pmid": "40952037",
  "doi": "10.1177/00912174251380668",
  "title": "...",
  "journal": "...",
  "publication_year": "2025",
  "url": "https://pubmed.ncbi.nlm.nih.gov/40952037/",
  "retrieved_at": "2026-05-20T00:00:00Z",
  "license_status": "metadata_or_abstract_only"
}
```

## Query Trace

Store generated and executed queries separately:

```json
{
  "query_id": "q1",
  "generated_by": "manual|llm|template",
  "query": "...",
  "source": "pubmed",
  "intent": "find similar case reports",
  "executed": true,
  "result_count": 52
}
```

## Reasoning Trace

Do not rely only on a final answer. Store:

- problem representation
- differential diagnoses
- supporting evidence
- refuting evidence
- final diagnosis
- confidence
- next tests
- citations used

For APIs that do not expose hidden chain-of-thought, store the model-visible rationale or structured justification instead.

## Reproducibility Principle

A run should be replayable as closely as possible. External APIs and search indexes change, so manifests should preserve retrieved content summaries and identifiers, not just the query text.
