# Roadmap

ClinicalOrchestra should grow in layers. Each layer should be useful and testable before the next is added.

## Phase 0: PubMed Search Foundation

Status: started.

- PubMed search CLI.
- Abstract retrieval via EFetch.
- Structured JSON output.
- Unit tests for XML parsing.

Next improvements:

- save search results to `runs/`
- add run manifests
- add PMID fetch by id
- add query templates for neurology syndromes

## Phase 1: Case Attempt Runner

Goal: run a single benchmark case through a reproducible workflow.

Tasks:

- define `ClinicalCase` schema
- load cases from JSON
- create problem representation manually or via LLM
- generate PubMed queries
- collect evidence
- produce a final structured answer
- write a run trace

## Phase 2: Evidence Filtering

Goal: reduce noisy retrieval.

Tasks:

- rank PubMed results by case relevance
- detect original-source leakage
- extract candidate diagnoses from abstracts
- cluster duplicate diagnoses and aliases
- add citation-backed evidence summaries

## Phase 3: LLM Orchestration

Goal: compare orchestration strategies.

Strategies:

- single model with retrieval
- query generator + evidence extractor + diagnosis synthesizer
- multi-agent differential diagnosis
- specialist agents by neurology subspecialty
- counterfactual evidence checking

## Phase 4: Benchmark Harness

Goal: evaluate many cases reproducibly.

Tasks:

- batch case runner
- closed-book vs PubMed-only vs web-enabled modes
- answer alias matching
- LLM-as-judge with audit samples
- cost/latency reporting
- leaderboard tables

## Phase 5: Integration With NeurologyBM

Goal: use NeurologyBM as a benchmark source and ClinicalOrchestra as an attempt engine.

Tasks:

- import NeurologyBM case schema
- preserve train/eval split boundaries
- support source-excluded retrieval
- evaluate retrieval benefit by case difficulty

## Non-Goals For Now

- clinical deployment
- patient-specific advice
- autonomous treatment recommendation
- training on retrieval logs
- scraping proprietary challenge sites into git
