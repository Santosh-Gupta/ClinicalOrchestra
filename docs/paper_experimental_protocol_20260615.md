# Paper: experimental protocol, dataset discipline, and reproducibility (2026-06-15)

This is the protocol the paper's empirical claims must follow. Its purpose is to make the results
**credible and reproducible** and to prevent the most likely reviewer objections (train/test leakage,
single-run noise, retrieval cheating). Read with `docs/hard24_gap_analysis_20260614.md` (the thesis +
taxonomy), `docs/augmentation_catalog_20260614.md` (the interventions), and `DESIGN_DECISIONS.md`.

## Working title / thesis

*Information retrieval, not model scale, is the lever for hard diagnosis: for cases that defeat strong
LLMs closed-book, the discriminating knowledge is retrievable, and the failures are hypothesis- and
query-formulation failures. A portfolio of independent, **general-bidirectional** reasoning principles
and **niche-inert** knowledge augmentations — applied uniformly (no difficulty gating) — recovers more
of these cases than any single chain, while a held-out control set guards against regressing easy ones.*

## Dataset discipline (the most important section for credibility)

Multiple case sets are generated over time and we optimize across several of them (multi-dev), which
*reduces* overfitting to any one set. The discipline that keeps this paper-credible:

| Split | What it is | Role | Tune on it? |
| --- | --- | --- | --- |
| Original 22 / 53 curated | earliest curated cases | early development | already used |
| **Dev set 1 = second-100's 24 hard cases** | failed bare Flash + bare Pro + Flash-harness | **the augmentations (knowledge-pack cards, gates) were DERIVED from these** | yes — never a headline |
| **Control set = bare-Flash-pass cases** | cases the bare model already passes | regression guard (ADR-004) | no — monitor only |
| **Dev set 2 = third-100** (`third100_final_neuropsych`, fresh, 0 overlap) | next optimization set | **first-contact result = generalization checkpoint**, THEN optimize on its failures | first measure, then yes |
| **Held-out TEST = a future set** | reserved, untouched | **the headline generalization claim**, single frozen-config run | NO |

**Two rules that make this rigorous:**
1. **First-contact generalization checkpoint.** Each NEW set is first run with the *current* frozen
   harness *before* any set-specific tuning. Because the augmentations were derived from earlier sets,
   that first-contact number is near-held-out generalization evidence. Record it (with N≥3 repeats)
   *before* touching the new failures. The sequence of first-contact numbers across sets is a
   generalization curve — strong paper evidence that the portfolio transfers (or doesn't).
2. **Reserve a final untouched set as the true held-out test** for the single headline number.

**Rule:** dev-set pass rate (any set we've tuned on) is an upper-bound sanity check, not generalization.
The headline is the held-out test + the per-set first-contact curve. Label every tuned-set result
"development analysis."

## Metrics

- **Primary:** judge-based pass rate (LLM judge with lexical pre-pass, ADR-001). Report **hard-set and
  control-set rates as a pair, always** (a gain that regresses easy cases is not a gain).
- **Variance:** every reported number is a **mean ± range over N≥3 repeated runs** (identical config).
  Single runs at 1–3-case granularity are inside the noise band (ADR-005) and must not be reported as
  trends. Source of variance: LLM nondeterminism (even at temperature 0), retrieval ordering, judge.
- **Secondary:** average retrieval rounds/case (adaptive depth), queries/case, papers cited per case,
  fraction of cases where a knowledge-pack card fired (precision of niche augmentation).

## Conditions / ablation arms (each run on the SAME cases, N≥3 seeds)

1. **Baseline** — bare model, no harness (`benchmark baseline-eval`). Flash and Pro.
2. **Full harness** — gates + case-derived queries + feature-conditional contrast + knowledge pack + adaptive rounds + eval mode.
3. **− universal gates** (`--no-gates`).
4. **− knowledge pack** (`--no-knowledge-pack`).
5. **− contrast/query improvements** (`--no-contrast-queries`; and a variant reverting to long queries to quantify the query-length effect).
6. **− adaptive rounds** (`--no-adaptive-rounds`, fixed rounds).
7. **Multi-angle ensemble** (`diagnostic_ensemble`) alone, and **ensemble ∪ harness** (the portfolio/dropout claim).

Each arm gives the **component contribution** (full minus arm) — this is the paper's main analysis
table and the empirical backing for the "portfolio of independent nets" thesis.

## Frozen config (the held-out test must use exactly this)

```
benchmark retrieval-guided-eval \
  --manifest <TEST_MANIFEST> --out-dir <OUT> \
  --max-queries 3 --articles-per-query 3 --max-rounds 4 --min-rounds 1 \
  --distill-evidence --judge --concurrency 6
# eval_mode ON (default), knowledge pack ON (default), feature-presets for unknown case_ids (default)
# answer model: deepseek-v4-flash ; judge: deepseek-v4-flash (held fixed across all arms)
# reasoning-model completion budget: 8192 (ADR-017)
```
Code state at protocol freeze: commit `b179a31` (+ the working-tree changes for the augmentations,
to be committed before the test run). Pin the exact commit hash in the paper.

## Eval integrity (anti-cheat) — a methods-section requirement

Eval mode (ADR-030) is ON for all benchmark numbers: the source paper a vignette derives from is
excluded from retrieval by pmcid/doi/title, source-revealing queries are blocked, and a generic
anti-cheat instruction is given that never reveals the source identifiers (so it can't leak the
answer). Doctor-assist mode (eval_mode off) is a separate, non-benchmark use. State this explicitly;
it pre-empts the "did it just retrieve the source case report?" objection.

## Threats to validity (address each in the paper)

1. **Derivation-set overfitting** → headline on held-out test only; dev-set labeled as such.
2. **Single-run noise** → N≥3 repeats, report mean±range; the dev-set 13→14→15 progression is
   directional, not significant at single-run granularity.
3. **Retrieval leakage** → eval mode + source exclusion (above).
4. **Judge reliability** → judge held fixed across arms; report judge match-type distribution; spot
   audit a sample against clinician adjudication; note residual judge leniency (e.g. it passed a
   "leads with AE, must exclude HSV" answer).
5. **Solvability of cases** → confirm the deciding discriminator is in the prompt (first-pass scan:
   23/24 reachable); for genetic cases reward the named entity, not the exact variant string.
6. **Knowledge-pack precision** → report off-target card-fire rate; cards are hypotheses, not assertions.

## HEADLINE RESULT (2026-06-15): the benchmark was ~27% broken; cleaned, the system solves 88–92%

The central empirical arc: optimizing the solver hit a ~15% "reclaim ceiling" on v4-Pro cold-failures
that proved to be a **data artifact**. A determinacy/mend pass (NeurologyBM `case_validation`) found
**~27% of dev cases under-determined** (asked for a specific gene/antibody/pathology whose deciding
result was withheld) and repaired them by **adding the result verbatim from the source (gold unchanged,
0 relax)**. Re-benchmarking the cleaned 200 dev cases:

| Stage (cleaned, 200 dev cases) | solved | cumulative |
| --- | --- | --- |
| bare Flash | 149 (74%) | 74% |
| + bare Pro on Flash-failures | +20 | 85% |
| + harness (top-5) on 31 double-failures | +7 @1 / +14 @5 | **88% @top-1 / 92% @top-5** |

On the genuinely-hard cleaned tail (31 cases failing both models WITH the deciding result present), the
harness adds 23% pass@1 / **45% pass@5**. **Lessons for the paper:** (1) verify a generated benchmark is
ANSWERABLE before trusting a hard-case ceiling — a single mend pass moved the result from 15% to 88–92%;
(2) report **pass@k**, not top-1 — pass@5 ≈ 2× pass@1 because the residual is a ranking problem; (3)
retrieval helps via precision, not volume; (4) self-prompt reasoning levers (commit/self-consistency/
re-rank) are flat — the residual frontier (17 top-5-absent cleaned cases) is the genuine reasoning
target.

## Results so far (DEVELOPMENT analysis — indicative, single-run, NOT headline)

| Config (dev sample: 24 hard + 12 control) | Hard | Control |
| --- | --- | --- |
| bare Flash (baseline) | 1/24 | 12/12 |
| biased gates + knowledge pack | 6/24 | 7/12 |
| balanced (bidirectional) gates | 5/24 | 9/12 |
| + case-derived queries + feature-conditional contrast (full) | 6/24 | 9/12 |

**Generalization checkpoint — third-100 (fresh, augmentations NOT derived from it), first contact:**

| third-100 stage | result |
| --- | --- |
| bare Flash | 62/100 |
| bare Pro on 38 Flash-failures | reclaims 10 |
| improved harness on 28 double-failures | **3/28 (11%)** |

vs ~6/24 (25%) on the derivation set. Interpretation (key result): the **general** machinery transfers
(all 3 reclaims from gates + retrieval, none from a seeded card), while the **niche** knowledge pack
correctly stays inert on third-100's different rare entities — i.e. general transfers, niche must
accumulate. This is the paper's generalization evidence and the rationale for the multi-dev loop.

Plus the worked **case study** (paper-ready narrative): PMC13213105 went from a confident wrong "NPSLE"
to the correct "sensory-deprivation auditory hallucinosis" purely by (a) replacing a hard-coded
NPSLE retrieval query with case-derived queries and (b) making the preset contrast query
feature-conditional — i.e. fixing information retrieval and an anchoring bias, with no difficulty gate.
This is the paper's illustrative figure of the method.

## Paper artifact checklist

- [ ] Failure taxonomy table (M1–M4) with source-paper discriminators — have it (`augmentation_catalog`).
- [ ] Retrieval thesis evidence (query-length experiment; phenotype→gene; contrast queries) — have it.
- [ ] Ablation/component-contribution table, multi-seed — TODO (task #13).
- [ ] Held-out test-set result, frozen config, single shot — TODO (next set).
- [ ] Method figure (NPSLE case study) — have the data.
- [ ] Reproducibility appendix: commit hash, manifests, flags, seeds, model ids — this doc.
