# Quickstart

ClinicalHarness currently provides PubMed and PMC retrieval CLIs backed by NCBI E-Utilities, plus a deterministic single-case runner that writes reproducible run artifacts.

## Install

```bash
cd /Users/santoshg/Coding/ClinicalHarness
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
clinical-harness pubmed search \
  "autoimmune encephalitis psychosis catatonia case report" \
  --limit 10
```

Return structured JSON:

```bash
clinical-harness pubmed search \
  "MOGAD seizure case report" \
  --limit 5 \
  --format json
```

Sort by publication date:

```bash
clinical-harness pubmed search \
  "new onset refractory status epilepticus case report" \
  --limit 10 \
  --sort pub+date
```

## Search And Fetch PMC

Search PMC and fetch matching full-text XML sections:

```bash
clinical-harness pmc search \
  "seronegative autoimmune encephalitis criteria" \
  --limit 3
```

Fetch known PMC full text:

```bash
clinical-harness pmc fetch PMC3122590 --format json
```

## Run A Synthetic Case

Generate run artifacts without external API calls:

```bash
clinical-harness case run examples/cases/synthetic_neuro_case.json \
  --mode pubmed_only \
  --no-retrieve \
  --out runs
```

Run the same case with PubMed retrieval:

```bash
clinical-harness case run examples/cases/synthetic_neuro_case.json \
  --mode pubmed_only \
  --email you@example.com \
  --limit 5 \
  --out runs
```

The runner writes `manifest.json`, `events.jsonl`, `queries.jsonl`, `evidence.jsonl`, and `answer.json` under `runs/<run_id>/`.

## TLS Caveat

If the local Python certificate store is broken, use the explicit local escape hatch:

```bash
clinical-harness pubmed search \
  "anti NMDA receptor encephalitis case report" \
  --limit 5 \
  --insecure
```

Do not use `--insecure` in production runs.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
