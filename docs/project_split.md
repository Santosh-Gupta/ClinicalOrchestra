# Project Split

ClinicalHarness and NeurologyBM are separate but coupled projects.

## Ownership

| Track | Repo | Owner role | Primary output |
| --- | --- | --- | --- |
| Dataset and benchmark creation | `/Users/santoshg/Coding/NeurologyBM` | Dataset/Benchmark Agent | License-audited neurology benchmark candidates, benchmark items, split manifests, source registry, dataset paper artifacts |
| Diagnosis-agent system | `/Users/santoshg/Coding/ClinicalHarness` | Diagnosis Agent | Reproducible case-attempt runner, retrieval and evidence ledger, model orchestration, scoring, cost/latency reports |

The Dataset/Benchmark Agent should not build the diagnosis orchestration stack beyond the minimal harness needed for closed-book baseline evaluation. The Diagnosis Agent should not build or publish benchmark datasets independently of NeurologyBM's license and split decisions.

## Shared Interface

ClinicalHarness should eventually consume benchmark exports with these fields:

```json
{
  "case_id": "neurologybm:...",
  "prompt": "...",
  "answer_key": {
    "final_diagnosis": "...",
    "aliases": [],
    "localization": "...",
    "key_findings": []
  },
  "metadata": {
    "source_family": "...",
    "source_bucket": "...",
    "license_tier": "public_benchmark|noncommercial_benchmark|internal_only|pointer_only",
    "split": "dev|test|external_locked",
    "pmid": null,
    "pmcid": null,
    "doi": null,
    "source_title": null,
    "source_url": null
  }
}
```

ClinicalHarness must preserve these fields in every run manifest so retrieval leakage and train/eval separation remain auditable.

## Coordination Rules

- NeurologyBM decides whether a case can be public, noncommercial, internal-only, or pointer-only.
- ClinicalHarness decides how to attempt a case under a declared evaluation mode.
- Locked-source prompts and answer keys stay out of git unless redistribution rights are resolved.
- A run trace is not training data.
- If ClinicalHarness retrieves the original source article during an attempt, the run must record that fact.
- If a case has `pmid`, `pmcid`, `doi`, or source title metadata, source-excluded modes must block or flag matching evidence.

## Near-Term ClinicalHarness Priorities

1. Define serializable case, evidence, answer, model-call, and run-manifest schemas.
2. Add an append-only run ledger under `runs/`.
3. Add a single-case runner that can work without LLM calls.
4. Add provider-agnostic model routing config for cheap, mid, and strong model roles.
5. Add source-exclusion checks.
6. Add batch evaluation only after the single-case run trace is stable.

