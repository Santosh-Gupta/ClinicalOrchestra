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
