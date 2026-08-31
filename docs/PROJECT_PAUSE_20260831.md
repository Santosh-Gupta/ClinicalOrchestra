# Project pause and blog-post pivot

Date: 2026-08-31

ClinicalHarness is paused as a paper project. The current public-facing artifact is the blog-style write-up at
[`docs/writeup.md`](writeup.md), supported by the README, released benchmark files, trace viewer, and archived
methods/results docs.

## Why this is not being submitted as a paper now

The work remains useful, but the author does not consider the benchmark and harness robust enough to defend as
an iron-clad paper without further expert review and additional expensive validation.

The central issue is benchmark construction. Turning a case report into a fair diagnostic challenge requires
withholding the answer while preserving everything a doctor would need to diagnose the patient. That assumption
is weaker than expected: case reports often narrate a known diagnosis and may omit, defer, or contextualize key
diagnostic information outside the self-contained vignette. Filling those gaps with LLMs creates circularity:
the same kind of model being evaluated constrains what the benchmark constructor can notice, preserve, or flag
as insufficient.

A stronger pipeline may be possible, likely involving multi-source grounding, formal criteria checks,
independent high-quality model review, and expert clinician adjudication. That would require more time and API
budget than the current project should spend before release.

## What is still worth releasing

- The 68-case post-cutoff neurology/psychiatry stress set as an exploratory artifact, with source provenance
  and an explicit warning that it was selected from DeepSeek V4 Flash failures rather than neutrally sampled.
- The larger development set as raw material, clearly marked by `review_status`.
- The model-result pattern: ranked differentials reveal behavior that top-1-only scoring hides.
- The harness lesson: retrieval can help weaker or knowledge-gap cases but can hurt strong models when it
  freely re-ranks or crowds out the model's own correct candidates.
- The trace viewer and run artifacts as infrastructure for people who want to audit or extend the idea.

## How to describe the project publicly

Use this framing:

> ClinicalHarness is an exploratory, paused benchmark-and-harness project for open-ended clinical diagnosis.
> It is good enough to show interesting patterns and open problems, but not a definitive model leaderboard or
> clinically validated benchmark.

Avoid these claims:

- Do not call the results a definitive ranking of frontier models.
- Do not claim the case challenges are all expert-validated.
- Do not claim the retrieval harness is clinically reliable.
- Do not imply the archived LM4Sci draft is the active deliverable.
- Do not tune, revise, or revive the paper without first addressing benchmark determinacy with stronger review.

## If the paper path is revived

Before treating the archived workshop draft as active again:

1. Re-run current model versions; the old leaderboard is dated.
2. Expert-review the 68-case benchmark for leakage, determinacy, and diagnosis/gold support.
3. Separate benchmark-construction errors from model failures.
4. Revalidate any harness claim with within-run judging and per-cutoff harm analysis.
5. Keep the blog/write-up caveats unless the new evidence genuinely removes them.
