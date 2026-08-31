# Neurology & Psychiatry Ranked-Differential Benchmark (68 cases)

`neuro_psych_68_challenges.jsonl` is the contamination-reduced stress set discussed in the exploratory
write-up and archived paper draft. Each line is one diagnostic challenge derived from a single strictly
**CC-BY** open-access case report published after a conservative cutoff gate for the evaluated models. This
reduces the ordinary pretraining-memorization route; it does not prove that no provider pipeline ever exposed a
model to the case.

The 68 rows were selected from cases that an earlier closed-book DeepSeek V4 Flash run failed. DeepSeek Flash
is therefore 0/68 by construction. Use this as a **failure-selected rescue/error-analysis set**, not as a neutral
model leaderboard or an estimate of population-level clinical accuracy.

## Format (one JSON object per line)

| field | meaning |
|---|---|
| `case_id` | stable identifier |
| `challenge_prompt` | the redacted case presentation (diagnosis and any give-away removed) |
| `answer_key` | the gold diagnosis with matching aliases |
| `pmcid`, `doi` | provenance of the source case report (for re-audit) |
| `title` | source paper title |
| `license_key` | license of the source (CC-BY) |
| `postcutoff` | passed the project's conservative publication-date gate |
| `source_kind`, `wave` | construction metadata |

## How it was built

Published case reports → LLM-rewritten into challenges that withhold the diagnosis but keep the deciding
evidence → audited for **determinacy** (every discriminator needed for the gold is present in the prompt,
checked against the full source) and **leakage** (the prompt does not give the answer away), with
source-grounded repair or drop. Score the full ranked differential (top-1 through top-5); credit a diagnosis
appearing at any rank `<= n`. See the project write-up (`docs/writeup.md`) for the current public framing and
the archived paper draft (`docs/workshop_submission/`) for fuller construction and scoring details.

For retrieval-assisted runs, exclude the source article itself using its DOI/PMCID/title and record whether the
exclusion succeeded. Otherwise retrieval can leak the published answer independently of pretraining exposure.

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
