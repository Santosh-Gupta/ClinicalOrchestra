# Design: context-isolated scaled retrieval (2026-06-14)

## Problem

To retrieve at the scale doctors need ("check hundreds or thousands of papers"), we cannot pour raw
paper text into the main diagnostic context — it bloats the window, costs money, and drowns signal.
And the long-query failure (see `hard24_gap_analysis`) shows naive batch retrieval already misses.

## Principle

**Push each paper's text into its own throwaway context; return only the distilled, diagnosis-
relevant note (or nothing).** The main thread holds a small, growing evidence ledger, never raw text.

## Components

1. **Per-paper extractor** — `paper_analysis.analyze_paper` (IMPLEMENTED). One Flash call per paper,
   given the paper + the *current diagnostic state*, returns `{relevant, relevant_excerpt,
   discriminators, supports, refutes, proposed_queries}` or `relevant=false`. Strict: most papers are
   irrelevant and return nothing. Raw text dies with the sub-call's context.
2. **Parallel screen** — `paper_analysis.analyze_papers` (IMPLEMENTED). Bounded thread pool over
   papers; the shared NCBI rate-limit lock and model 429/RPM/TPM limiter keep us within account
   ceilings. Returns only the relevant analyses. This is what scales to hundreds/thousands.
3. **Standing query-strategist loop** (DESIGN). A long-running agent that watches the evolving
   differential + the `proposed_queries` flowing back from extractors, dedupes against queries
   already run (reuse the `_normalized_query_set` convergence guard from adaptive rounds), keeps
   issuing new focused queries, and stops when the differential is resolved or new queries stop
   producing relevant papers. It is the adaptive-rounds `more_retrieval_needed` signal promoted into
   its own continuous process.
4. **Evidence ledger** (DESIGN). The compact, deduplicated store the main diagnostic thread reads:
   discriminators + supports/refutes + citations (PMID/DOI/title), capped and ranked by relevance.
   Feeds both the final answer and the cited report (`key_papers`).

## Control flow (target)

```
queries ──> NCBI search (rate-limited) ──> N paper stubs
   ^                                            │  fan out, bounded pool
   │                                            ▼
   │                                   per-paper Flash extractor  ── relevant? ──no──> drop
   │                                            │ yes
   │   proposed_queries  <───────── compact note (excerpt, discriminators, citation)
   │   (query strategist)                       │
   └──── new focused queries <──────────────────┴──> evidence ledger ──> main diagnostic thread
```

## Why this also improves accuracy (not just scale)

- Targeted extraction means the main thread sees discriminators, not abstracts — less anchoring on a
  paper's headline diagnosis.
- `proposed_queries` from papers create a *literature-driven* query expansion the case author cannot
  pre-empt (e.g. a review that says "consider SLC6A1" spawns the gene query).
- Strict relevance gating raises signal-to-noise versus dumping top-k abstracts.

## Integration points (next implementer)

- Wire `analyze_papers` as an optional evidence path in `collect_pubmed_evidence` (flag
  `--paper-extractor` / `config.use_paper_extractor`), replacing the single batch `distill` with
  per-paper screening when retrieving large `articles_per_query`.
- Feed `PaperAnalysis.proposed_queries` into `build_followup_queries` / the next round's query set.
- Persist the evidence ledger per case for the cited report and for audit.

## Open questions

- Cost/latency budget per case at high paper counts (Flash is cheap + 2500 concurrent — model the
  expected calls). - Dedup of near-duplicate papers before extraction to save calls.
- Full-text (PMC) vs abstract-only screening tiers (screen on abstract, fetch full text only for the
  papers that pass).
