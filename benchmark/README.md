# Neurology & Psychiatry Ranked-Differential Benchmark (68 cases)

`neuro_psych_68_challenges.jsonl` is the contamination-controlled hard set used in the paper
*Ranked Differential Diagnosis Across Frontier LLMs*. Each line is one diagnostic challenge derived from a
single strictly **CC-BY** open-access case report published **after** every evaluated model's training
cutoff, so it cannot have been seen in pretraining.

## Format (one JSON object per line)

| field | meaning |
|---|---|
| `case_id` | stable identifier |
| `challenge_prompt` | the redacted case presentation (diagnosis and any give-away removed) |
| `answer_key` | the gold diagnosis with matching aliases |
| `pmcid`, `doi` | provenance of the source case report (for re-audit) |
| `title` | source paper title |
| `license_key` | license of the source (CC-BY) |
| `postcutoff` | confirmed published after model cutoffs |
| `source_kind`, `wave` | construction metadata |

## How it was built

Published case reports → LLM-rewritten into challenges that withhold the diagnosis but keep the deciding
evidence → audited for **determinacy** (every discriminator needed for the gold is present in the prompt,
checked against the full source) and **leakage** (the prompt does not give the answer away), with
source-grounded repair or drop. Score the full ranked differential (top-1 through top-5); credit a diagnosis
appearing at any rank `<= n`. See the paper (`docs/workshop_submission/`) for construction and scoring
details.

This is a research benchmark for evaluating diagnostic reasoning, **not** a clinical decision-support tool.

## Development cases (`development_cases_359.jsonl`) — NOT the evaluation set

358 earlier development challenges used while building and tuning ClinicalHarness, released for transparency
and reuse. **These are not the evaluation benchmark and were not all held to the same bar:** unlike the
68-case set, they were not uniformly proofread, source-mended, or contamination-filtered, and they are not
guaranteed post-cutoff. Treat them as raw development material, not a clean benchmark.

Each case carries a `review_status` indicating how far it got through vetting — filter on it for your use:

| `review_status` | count | meaning |
|---|--:|---|
| `refined_needs_spotcheck` | 245 | refined; pending a final spot check |
| `needs_fidelity_review` | 44 | flagged: faithfulness to source not yet cleared |
| `needs_determinacy_validation` | 21 | flagged: determinacy not yet validated |
| `needs_leakage_review` | 3 | flagged: possible answer leakage, not yet cleared |
| `not_solvable` | 40 | known-defective: the diagnosis is not reachable from the prompt |
| `not_self_contained` | 5 | known-defective: required information is missing |

All 358 are CC-BY with source provenance (PMCID/DOI), same field format as the evaluation set (plus
`review_status`). The evaluated benchmark is `neuro_psych_68_challenges.jsonl` above.
