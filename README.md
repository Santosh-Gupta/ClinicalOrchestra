# ClinicalOrchestra

ClinicalOrchestra is a research repo for attempting hard diagnosis case challenges with an orchestrated set of tools: literature search, retrieval, evidence synthesis, and later LLM-based differential diagnosis.

This is not a clinical decision support system. It is for benchmark research and model/tool evaluation.

## First Slice: PubMed Search

The initial implementation wraps NCBI E-Utilities for PubMed:

- `ESearch` for PMID discovery
- `EFetch` for article titles and abstracts
- structured JSON output for downstream evidence synthesis

Set a contact email before doing nontrivial runs:

```bash
export NCBI_EMAIL="you@example.com"
```

Install locally:

```bash
cd /Users/santoshg/Coding/ClinicalOrchestra
python3 -m pip install -e .
```

Search PubMed:

```bash
clinical-orchestra pubmed search "autoimmune encephalitis psychosis catatonia" --limit 10
```

Return JSON:

```bash
clinical-orchestra pubmed search "MOGAD seizure case report" --limit 5 --format json
```

If the local Python certificate store is broken, there is an explicit local-only escape hatch:

```bash
clinical-orchestra pubmed search "anti NMDA receptor encephalitis case report" --limit 5 --insecure
```

Do not use `--insecure` in production runs.

## Intended Architecture

The project will grow into a staged reasoning pipeline:

1. Ingest a hard case prompt.
2. Generate search queries from the clinical problem representation.
3. Search PubMed and other allowed sources.
4. Fetch abstracts/full text where permitted.
5. Extract evidence into structured candidate diagnoses.
6. Ask LLMs to produce differentials, localization, next tests, and final diagnosis.
7. Score outputs against benchmark answer keys.

The first version only implements step 3 and the PubMed part of step 4.

## Licensing And Source Rules

- PubMed metadata and abstracts are not automatically training data.
- For final benchmarking, locked or licensed challenge text can be used internally only when access terms permit it.
- For public benchmark release or training data, use source-specific licensing and permissions.
- Store provenance for every retrieved item: API, query, PMID, DOI, publication type, journal, date, and URL.

## Development

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
