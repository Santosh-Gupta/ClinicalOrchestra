# Run Provenance

ClinicalHarness should be reproducible from run manifests. Every benchmark attempt should leave enough trace data to understand what the model saw, what it searched, what evidence it used, and why it produced an answer.

## Run Directory

The current single-case runner writes:

```text
runs/<run_id>/manifest.json
runs/<run_id>/events.jsonl
runs/<run_id>/queries.jsonl
runs/<run_id>/evidence.jsonl
runs/<run_id>/answer.json
```

`scores.json` will be added when scoring exists.

## Run Manifest

Each future run should record:

- run id
- timestamp
- status
- git commit
- evaluation mode
- benchmark case id
- case path
- model ids and API versions
- tool list
- allowed sources
- search queries
- retrieved evidence ids
- prompts sent to LLMs
- model outputs
- scoring outputs
- cost and latency summary
- source-exclusion decisions and original-source retrieval flags
- NeurologyBM case metadata when the run uses a NeurologyBM export

## Evidence Record

Every retrieved evidence item should include:

```json
{
  "evidence_id": "pubmed:40952037",
  "source_api": "pubmed",
  "query": "autoimmune encephalitis psychosis catatonia case report",
  "rank": 1,
  "pmid": "40952037",
  "pmcid": null,
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

Run traces are evaluation artifacts, not training data. Do not use retrieval logs, model rationales, or locked-source case text as a future training corpus unless the underlying source licenses and access terms explicitly permit that use.

## Live Guided Eval: 2026-06-13

Run target: all 53 public case challenges that previously failed DeepSeek V4 Pro, from:

`/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/all_public_deepseek_v4_pro_failed_manifest_20260613.jsonl`

Mode: guided direct-answer prompt with learned ClinicalHarness presets. This was not yet the full retrieval controller; no PubMed/PMC retrieval evidence was injected.

Command shape, with credentials redacted:

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem \
MODEL_TIMEOUT_SECONDS=45 \
DEEPSEEK_API_KEY=REDACTED \
PYTHONPATH=src \
python3 -m clinical_harness.cli benchmark guided-eval \
  --model deepseek-v4-flash \
  --skip-existing \
  --progress \
  --out-dir runs/guided_eval_all53_deepseek_v4_flash_20260613
```

Artifacts:

- `runs/guided_eval_all53_deepseek_v4_flash_20260613/guided_results.tsv`
- `runs/guided_eval_all53_deepseek_v4_flash_20260613/guided_results.jsonl`
- one prompt and one response JSON file per case

Result:

- 53 cases completed
- 20 lexical passes
- 33 lexical fails
- 0 not-run/error rows

Cohort split:

- original refined 30-case Pro-failed cohort: 10 pass, 20 fail
- next100 23-case Pro-failed cohort: 10 pass, 13 fail

Interpretation:

- Prompt-only ClinicalHarness presets can rescue a meaningful minority of Pro-failed cases, especially some vascular neuro, seizure mimic, CNS vasculitis, sellar xanthogranuloma, ocular infection/inflammation, postoperative foreign-body, and selected tumor cases.
- Prompt-only presets remain weak for rare pathology marker tables, organism-level mold identification, cytogenetic subtype calls, persistent hCG localization, autoimmune encephalitis subtype discipline, and some functional-neuro red-flag cases.
- Next harness milestone should be an actual retrieval/discriminator controller: generate guarded concept queries, retrieve PubMed/PMC sources, distill short evidence notes, then force a differential update against those notes before final answer.

## Retrieval-Guided Probe: 2026-06-13

Mode: `benchmark retrieval-guided-eval`.

Command shape, with credentials redacted:

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem \
MODEL_TIMEOUT_SECONDS=60 \
DEEPSEEK_API_KEY=REDACTED \
PYTHONPATH=src \
python3 -m clinical_harness.cli benchmark retrieval-guided-eval \
  --case-id native_PMC3122590 \
  --case-id transformed_PMC10025825 \
  --case-id transformed_PMC10409533 \
  --case-id transformed_PMC7678886 \
  --out-dir runs/retrieval_guided_mixed4_20260613 \
  --model deepseek-v4-flash \
  --progress \
  --articles-per-query 3 \
  --max-queries 2 \
  --sleep 0.34
```

Artifacts:

- `runs/retrieval_guided_mixed4_20260613/retrieval_guided_results.tsv`
- one `*.queries.json`, `*.evidence.json`, `*.retrieval_prompt.txt`, and `*.retrieval_response.json` per case

Result:

- 4 cases completed
- 4 lexical passes after derived-alias scoring was added for PCNSL / primary CNS lymphoma
- initial raw substring scoring produced 3 lexical passes and 1 semantic pass that was undercounted

Case notes:

- `native_PMC3122590`: rescued from pseudoepitheliomatous keratotic and micaceous balanitis to cutaneous horn after PubMed retrieval plus a morphology/base-histology finalization gate.
- `transformed_PMC10025825`: rescued to epithelioid leiomyosarcoma after gynecologic epithelioid tumor IHC retrieval.
- `transformed_PMC7678886`: rescued to seronegative/probable autoimmune encephalitis after antibody-subtype discipline and retrieval.
- `transformed_PMC10409533`: answered primary CNS lymphoma / PCNSL, aligned with the expected likely primary CNS lymphoma. This required derived-alias scoring; future scoring should still add a judge for broader semantic equivalence.

Infrastructure note: sustained NCBI runs should set `NCBI_EMAIL` or pass `--email` so NCBI can contact the tool owner about automated traffic.

## Retrieval-Guided 33 Prompt-Failure Rerun: 2026-06-13

Target: the 33 cases that failed the prompt-only `guided-eval` all-53 run in `runs/guided_eval_all53_deepseek_v4_flash_20260613/guided_results.tsv`.

Subset manifest:

`runs/retrieval_guided_33_prompt_failures_manifest_20260613.jsonl`

Command shape, with credentials redacted:

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem \
MODEL_TIMEOUT_SECONDS=60 \
DEEPSEEK_API_KEY=REDACTED \
PYTHONPATH=src \
python3 -m clinical_harness.cli benchmark retrieval-guided-eval \
  --manifest runs/retrieval_guided_33_prompt_failures_manifest_20260613.jsonl \
  --out-dir runs/retrieval_guided_33_prompt_failures_20260613 \
  --model deepseek-v4-flash \
  --progress \
  --articles-per-query 3 \
  --max-queries 2 \
  --sleep 0.34
```

One case had an `IncompleteRead` model API error and was rerun with `MODEL_TIMEOUT_SECONDS=120`; the final TSV was rebuilt with `--skip-existing --no-retrieve`.

Artifacts:

- `runs/retrieval_guided_33_prompt_failures_20260613/retrieval_guided_results.tsv`
- one `*.queries.json`, `*.evidence.json`, `*.retrieval_prompt.txt`, and `*.retrieval_response.json` per case

Final conservative score:

- 33 cases completed
- 11 pass
- 22 fail
- 0 not-run/error rows

Rescued cases:

- `native_PMC3122590`: cutaneous horn
- `transformed_PMC10025825`: epithelioid leiomyosarcoma
- `transformed_PMC10409533`: primary CNS lymphoma / PCNSL
- `transformed_PMC10765173`: xanthogranulomatous osteomyelitis of temporal bone
- `transformed_PMC4291137`: chronic suppurative osteomyelitis of anterior maxilla
- `transformed_PMC7678886`: probable seronegative autoimmune encephalitis
- `transformed_PMC8143662`: suspected tethered cord syndrome
- `transformed_PMC8244580`: primary pericardial angiosarcoma
- `next_native_PMC12710301`: Scopulariopsis/Microascus invasive fungal sinusitis with CNS involvement
- `next_native_PMC7944237`: Fryns syndrome
- `next_native_PMC5590213`: extrauterine gestational choriocarcinoma

Observed next failure clusters:

- fixed preset queries are not enough for many rare pathology cases; they need case-feature-derived query generation and marker-table extraction
- mold identification still confuses genera/species when the query template over-prioritizes Microascus/Scopulariopsis
- demyelination/neuropsych/prion cases need stronger finalization gates against familiar anchors
- several remaining rows are near misses or partials, so a judge scorer is needed before treating lexical fail as definitive fail

## Controller Upgrade After 33-Case Rerun: 2026-06-13

Implemented after reviewing the 22 residual failures:

- case-feature query generation from case-visible markers, antibodies, cytogenetics, drugs, organisms, organs, cancers, and morphology
- multi-round retrieval via `--max-rounds`
- deterministic synthesis artifacts for every retrieval-guided run
- optional model-subagent evidence distillation via `--distill-evidence`
- optional PMC full-text snippet enrichment via `--use-full-text`
- final prompt now includes `evidence_synthesis`, `anchor_mimic_pair`, `retrieval_rounds_allowed`, and `retrieval_rounds_completed`

Command shape for a stronger residual-failure rerun:

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem \
MODEL_TIMEOUT_SECONDS=120 \
DEEPSEEK_API_KEY=REDACTED \
PYTHONPATH=src \
python3 -m clinical_harness.cli benchmark retrieval-guided-eval \
  --manifest runs/retrieval_guided_22_remaining_failures_manifest_20260613.jsonl \
  --out-dir runs/retrieval_guided_22_multiround_distilled_20260613 \
  --model deepseek-v4-flash \
  --progress \
  --max-rounds 2 \
  --max-queries 3 \
  --articles-per-query 3 \
  --distill-evidence \
  --use-full-text \
  --sleep 0.34
```

Operational note: `--distill-evidence` uses the configured model client as a subagent before final diagnosis. `--use-full-text` fetches available PMC full text for top evidence items and injects compact snippets, not whole papers. This should help pathology, mold, cytogenetic, and management-algorithm cases without letting context size explode.

## Multiround Distilled Residual Rerun: 2026-06-13

Target: the 22 failures left after the first retrieval-guided rerun.

Artifacts:

- `runs/retrieval_guided_22_multiround_distilled_20260613/retrieval_guided_results.tsv`
- one `*.queries.json`, `*.evidence.json`, `*.synthesis.json`, `*.retrieval_prompt.txt`, and `*.retrieval_response.json` per case

Final conservative score:

- 22 cases completed
- 3 pass
- 19 fail
- 0 not-run/error rows after retrying one malformed model JSON response

Newly rescued cases:

- `transformed_PMC10901880`: hibernoma
- `transformed_PMC2413251`: secondary aneurysmal bone cyst due to an underlying malignant vascular tumor
- `next_transformed_PMC9332052`: ampullary large-cell neuroendocrine carcinoma

Combined with the first retrieval-guided 33-case rerun, the retrieval harness has now rescued 14 of the 33 prompt-only failures, leaving 19 conservative lexical failures.

Remaining failure pattern:

- pathology-heavy cases still often retrieve useful sources but stop at a broad lineage diagnosis rather than the required subtype
- infection cases still over-weight organism or syndrome familiarity and miss species-level or colonization-versus-infection nuance
- neuroinflammatory and neuropsychiatric cases still anchor on familiar mimics such as MOGAD or anti-NMDA encephalitis when the answer requires a less common discriminator
- a judge scorer is still needed because lexical scoring is conservative, but the current table should be treated as the operational benchmark until semantic adjudication exists
