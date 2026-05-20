# Quickstart

ClinicalOrchestra currently provides a PubMed search CLI backed by NCBI E-Utilities. The goal is to make the first retrieval step reliable before adding LLM orchestration.

## Install

```bash
cd /Users/santoshg/Coding/ClinicalOrchestra
python3 -m pip install -e .
```

The current package uses only the Python standard library.

## Configure NCBI Access

NCBI asks automated clients to identify themselves. Set a real contact email for any nontrivial run:

```bash
export NCBI_EMAIL="you@example.com"
```

Optionally set an API key:

```bash
export NCBI_API_KEY="..."
```

The client defaults to a conservative request interval.

## Run A Search

```bash
clinical-orchestra pubmed search \
  "autoimmune encephalitis psychosis catatonia case report" \
  --limit 10
```

Return structured JSON:

```bash
clinical-orchestra pubmed search \
  "MOGAD seizure case report" \
  --limit 5 \
  --format json
```

Sort by publication date:

```bash
clinical-orchestra pubmed search \
  "new onset refractory status epilepticus case report" \
  --limit 10 \
  --sort pub+date
```

## TLS Caveat

If the local Python certificate store is broken, use the explicit local escape hatch:

```bash
clinical-orchestra pubmed search \
  "anti NMDA receptor encephalitis case report" \
  --limit 5 \
  --insecure
```

Do not use `--insecure` in production runs.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
