# Design Decisions (ADR registry) — READ BEFORE CHANGING HARNESS BEHAVIOR

This is the **authoritative record of why the harness is the way it is.** Multiple agents — some on
different LLMs — work on this repo. This file exists so a decision that was made deliberately, often
backed by an experiment, is not silently reverted by someone who didn't see the evidence.

## Governance (how to use this file)

1. **Before** removing, weakening, or "simplifying" any behavior below, read its ADR. Most of these
   look removable until you know the case that forced them.
2. If you still believe a decision is wrong, **do not silently revert it.** Add a *new* ADR that
   supersedes the old one: state the new evidence, mark the old one `Superseded by ADR-NNN`, and
   change the code. The trail must survive.
3. Every ADR names its **code anchors** (files/functions/tests) and a **⚠️ Do-not-revert-unless**
   condition. If a test enforces the decision, breaking it should fail CI.
4. Companion reading: `journal.md` (the *why-it-matters* narrative + lessons) and the dated `docs/`
   write-ups (the *full analysis* behind several ADRs). This file is the *index of commitments*.

Status legend: **Accepted** (in force), **Designed** (agreed direction, not yet built), **Superseded**.

## Index

- Evaluation methodology: ADR-001..006
- Retrieval & diagnostic reasoning: ADR-010..017
- Concurrency, rate limiting & resilience: ADR-020..024
- Eval integrity & clinician-facing output: ADR-030..031
- Architecture direction (designed): ADR-040..042
- Data generation guardrails (cross-repo): ADR-050
- Documentation & memory model: ADR-060

---

## Evaluation methodology

### ADR-001 — The scorer is part of the harness: LLM judge with a lexical pre-pass. (Accepted)
**Context:** string-match scoring both over- and under-counts (synonyms, qualifier differences).
**Decision:** score with a cheap lexical pass first, then an LLM judge for non-trivial matches;
`score` is the judge-or-lexical verdict of record, `lexical_score` retained for transparency.
**Rationale:** diagnosis equivalence is semantic. **Consequences:** judge has ~4-point run-to-run
variance (see ADR-005). **Anchors:** `judge.py`, `retrieval_guided_eval._score_fields`.
**⚠️ Do not revert** to lexical-only scoring — it silently mis-ranks every experiment.

### ADR-002 — Three-stage eval protocol with the judge held fixed. (Accepted)
**Context:** measuring "does the harness help" needs a floor and a ceiling.
**Decision:** (1) bare weak model (Flash) → (2) strong model (Pro) on the failures → (3) weak model
+ harness on the cases both fail cold. The **judge model is held fixed (Flash) across all stages**;
only the answer model / harness varies. **Rationale:** isolates the harness's contribution from raw
model strength; the double-failure set is the strongest test of added capability. **Anchors:**
`baseline_eval.py`, `docs/hard24_gap_analysis_20260614.md`. **⚠️ Do not** let the judge differ
between stages being compared — it confounds the result.

### ADR-003 — A "bare, no-harness" baseline is a first-class mode. (Accepted)
**Context:** "with harness" is meaningless without a "without harness" measured on identical cases +
scorer. **Decision:** `benchmark baseline-eval` sends only the case prompt (no retrieval, gates,
checklist, rounds). **Anchors:** `baseline_eval.py`, `cli.py:baseline-eval`. **⚠️ Do not** fold this
into the harness path; the whole point is that it shares nothing but the scorer.

### ADR-004 — Keep a control set of easy (already-passing) cases; check it on every change. (Accepted)
**Context:** an ablation proved retrieval *regresses* easy cases (9/10 → 7/10) by anchoring the
model on a relevant-but-wrong retrieved entity. **Decision:** "helps the hard cases" and "doesn't
break the easy ones" are separate claims; every harness change is checked against both.
**Anchors:** `docs/evolution_ideas_20260613.md` (control results). **⚠️ Do not** report a lift number
without the control arm.

### ADR-005 — Judge variance is real (~4 pts); pass *rates* over single runs for any headline number. (Accepted)
**Context:** re-scoring identical answers shifted 67→71 passes. **Decision:** treat single-run
pass/fail as noisy; multi-seed / majority judging is the path to a publication-grade figure.
**Status note:** acknowledged, multi-seed not yet default. **⚠️ Do not** over-interpret a 1–3 case
difference as signal.

### ADR-006 — Confirm solvable-vs-flawed before crediting/blaming the harness. (Accepted)
**Context:** some "failures" are under-determined cases (the deciding discriminator was stripped from
the prompt), not harness limits. **Decision:** before treating a miss as a harness failure, confirm
the correct path is reachable from the prompt. First-pass scan: 23/24 hard cases reachable.
**Anchors:** `docs/hard24_gap_analysis_20260614.md`. **⚠️ Do not** tune the harness against a flawed
case — fix the data instead (see ADR-050).

---

## Retrieval & diagnostic reasoning

### ADR-010 — Feature-indexed preset selection, NOT per-case_id memorization. (Accepted)
**Context:** mapping `case_id`→preset made the tuned set look good but does not generalize; new cases
fell to the weak `general` path. **Decision:** select the preset from the case's *features* (redacted
prompt vocabulary, never the answer key); keep the original 22 `case_id` overrides for continuity;
`--feature-presets-only` forces pure feature selection. Validated 91% family-agreement on 33 labeled
cases, all misses fail safe. **Anchors:** `preset_selection.py`, `tests/test_preset_selection.py`.
**⚠️ Do not** re-introduce case_id→preset as the primary path; that is memorization.

### ADR-011 — Universal finalization gates apply to EVERY case, independent of preset. (Accepted)
**Context:** the 4 drug-cause cases in the hard-24 were never routed to the `adverse_drug_event`
preset, so its principle never fired. **A principle gated behind a router you don't control is a
principle you don't have.** **Decision:** `UNIVERSAL_FINALIZATION_GATES` (anti-anchoring,
iatrogenic-first, treatable-can't-miss/HSV, commit-to-specific-entity, second-pathology) prepend to
every case's gates. **Anchors:** `retrieval_guided_eval.UNIVERSAL_FINALIZATION_GATES`,
`finalization_gates_for`, `tests/...`. **⚠️ Do not** move these back behind presets, and do not
delete one without a case showing it caused a wrong answer.

### ADR-012 — Adaptive retrieval rounds: max_rounds is a CAP, the agent decides depth. (Accepted)
**Context:** a fixed round count is wrong for variable case difficulty. **Decision:** `max_rounds` =
safety cap, `min_rounds` = floor; between them the distillation subagent's sufficiency judgment
(`differential_resolved` / `more_retrieval_needed`) drives continuation, with a **convergence guard**
(must propose a genuinely new query, else stop). `--no-adaptive-rounds` keeps the legacy fixed path
for ablations. **Anchors:** `should_run_another_round`, `tests AdaptiveRoundsTests`. **⚠️ Do not**
hard-code a fixed round count as the only path.

### ADR-013 — Retrieval should be gated on need (designed); retrieval is not free. (Designed)
**Context:** ADR-004's regression — good retrieval still hurts cases the model already knows.
**Decision (direction):** gate retrieval on self-consistency agreement — trust the model when
internally consistent closed-book; retrieve when the differential is unstable. **Anchors:**
`journal.md` Principle I.3. **⚠️ Do not** assume "always retrieve" is safe.

### ADR-014 — Query focusing: cap to ≤8 meaningful terms; broaden progressively on zero results. (Accepted)
**Context:** PubMed ANDs every term; long natural-language queries return **zero** hits and the
harness then "fails" with no evidence, invisibly. Verified live. **Decision:** `_focus_query` caps to
8 meaningful terms; `collect_pubmed_evidence` broadens on empty/off-topic (targeted broadener → 2-term
minimal). **Anchors:** `_focus_query`, `_minimal_query`, `_broaden_query`, `tests QueryFocusTests`.
**⚠️ Do not** send long sentence-queries to PubMed, and do not treat a zero-result query as a
negative finding — it's a bug.

### ADR-015 — Contrast and phenotype→gene query patterns. (Accepted)
**Context:** `A mimicking B` surfaces the misdiagnosis literature; `<phenotype> gene` surfaces the
named gene without knowing it. **Decision:** keep contrast queries (`use_contrast_queries`) and favor
these patterns. **Anchors:** `_anchor_contrast_query`. **⚠️ Do not** remove contrast queries; they
directly attack anchoring (ADR-011).

### ADR-016 — Relevance-filter retrieved evidence against case anchor terms. (Accepted)
**Context:** generic queries pull methodology/unrelated papers that anchor the model.
**Decision:** filter/suppress zero-relevance evidence; re-query when a pass is all off-topic.
`--no-relevance-filter` for ablation. **Anchors:** `_article_relevance`, `case_anchor_terms`.
**⚠️ Do not** feed unfiltered top-k abstracts into the final prompt.

### ADR-017 — Reasoning-model completion budget must be generous (≥8192). (Accepted)
**Context:** `deepseek-v4-pro` spent its *entire* 4096-token budget on hidden reasoning and returned
**empty content** (`finish_reason=length`) — which scores as a wrong answer. A silent, severe
failure mode. **Decision:** answer/baseline calls use ≥8192 (configurable `--max-tokens`).
**Anchors:** `_generate_final_answer` (8192), `baseline_eval max_tokens=8192`, `diagnostic_ensemble`
(angle + consolidation calls at 8192). **⚠️ Do not** lower the budget to "save tokens"; you will
silently truncate the hardest cases to empty answers. This tax applies to **every** model call you
add, not just the final answer — the ensemble angle agents hit it at 2048 and truncated to empty.

---

## Concurrency, rate limiting & resilience

### ADR-020 — Case-level concurrency via a bounded thread pool; results in manifest order. (Accepted)
**Context:** cases are independent and I/O-bound. **Decision:** `--concurrency N` ThreadPoolExecutor;
results reassembled into **manifest order, not completion order** (regression-tested). Default 1 =
unchanged sequential. **Anchors:** `run_retrieval_guided_manifest_eval` dispatch, `tests
ConcurrencyTests`. **⚠️ Do not** emit results in completion order; downstream diffing depends on order.

### ADR-021 — Concurrency limit ≠ rate limit; defend each backend its own way. (Accepted)
**Context:** DeepSeek caps *concurrency* (500 pro / 2500 flash, HTTP 429 over); NCBI caps *rate*
(~3/s no-key, ~10/s key) at the *account* level; OpenAI/Anthropic cap RPM **and** TPM.
**Decision:** DeepSeek = reactive (bounded pool + 429 backoff); NCBI = a lock held across the request
spacing so the global rate holds regardless of worker count; future RPM/TPM providers = a proactive
sliding-window limiter. **Anchors:** `ncbi._respect_rate_limit` (lock), `model_client` 429 retry,
`ratelimit.py`. **⚠️ Do not** use one "concurrency" knob for both; do not remove the NCBI lock under
concurrency (you will get banned).

### ADR-022 — Pluggable RateLimiter seam; no-op by default, shared singleton when active. (Accepted)
**Context:** future providers need proactive RPM/TPM throttling; DeepSeek does not. **Decision:**
`model_client` calls `rate_limiter.acquire(tokens=...)` before every request; default `NoOpRateLimiter`
(DeepSeek), `SlidingWindowRateLimiter` when `MODEL_MAX_RPM`/`MODEL_MAX_TPM` are set, as a **process-wide
singleton** (account-level limits must be shared across answer/judge/workers). **Anchors:**
`ratelimit.py`, `model_client._env_rate_limiter`, `tests test_ratelimit`. **⚠️ Do not** make the
limiter per-client; that silently allows N× the real limit.

### ADR-023 — Retry transient connection faults (not just HTTPError). (Accepted)
**Context:** `RemoteDisconnected` (server closed connection) is not an `HTTPError`/`URLError`; it
crashed a full concurrent run. **Decision:** both clients retry `(HTTPException, ConnectionError,
OSError, TimeoutError, …)` with backoff. **Anchors:** `ncbi._TRANSIENT_NETWORK_ERRORS`, `model_client`
except clause. **⚠️ Do not** narrow these back to `HTTPError` only.

### ADR-024 — Per-case isolation: one case's failure must not abort the batch. (Accepted)
**Context:** under concurrency, one unhandled worker exception killed all 27 cases.
**Decision:** `_safe_run_case` wraps each case; a failure becomes an error row and the run continues.
**Anchors:** `_safe_run_case`, `tests test_one_bad_case_does_not_abort_the_batch`. **⚠️ Do not** call
the raw per-case function directly in the dispatch loop.

---

## Eval integrity & clinician-facing output

### ADR-030 — First-class eval mode (anti-cheat) that protects the answer WITHOUT naming it. (Accepted)
**Context:** benchmark vignettes derive from a real paper; reading it = cheating. But injecting the
source title/DOI as "avoid this" would *leak the diagnosis*. **Decision:** `config.eval_mode` (default
on): filter the source paper from retrieval (pmcid/doi/title), block source-revealing queries, and add
a **generic** anti-cheat instruction that never reveals the identifiers (`redacted_blocked_shortcuts`
shows placeholders). `--no-eval-mode` = doctor-assist mode (reading the real source is legitimate).
**Anchors:** `source_exclusion_decision(eval_mode=)`, `_query_hits_source_shortcut` gate,
`tests EvalModeTests`. **⚠️ Do not** put raw source identifiers into the model prompt, and do not
disable source exclusion during benchmarking.

### ADR-034 — No difficulty gate. Every augmentation is general-bidirectional or niche-inert. (Accepted; supersedes the ADR-013-style gating idea for augmentations)
**Context:** augmentations that reclaimed hard cases regressed easy ones; the tempting fix was to gate
them on model confidence/difficulty. **Decision (user directive):** there is **no "hard case mode."** A
single diagnostic system must be robust across all cases; gating on difficulty is brittle niche-angling
that endangers the system (and confidence is unreliable — the model is confidently wrong on hard
cases). Instead: **(a) GENERAL improvements must be bidirectional/Bayesian** — every de-anchoring or
specificity pressure carries its counterweight (base rates / Occam / parsimony), so it helps common AND
rare cases. **(b) NICHE improvements must be truly inert off-target** — a card/feature only affects a
case whose discriminator is actually present. **(c) If a case is still wrong after (a)+(b),** the
failure is information-retrieval (inspect what evidence was missing) or diagnostic reasoning (read the
main thread's reasoning trace) — fix that, do not add a meta-gate. **Anchors:** `UNIVERSAL_FINALIZATION_GATES`
(base-rates-first), `knowledge_pack.match_cards` (precision). **⚠️ Do not** introduce a
difficulty/confidence/uncertainty gate to make an augmentation "safe"; fix the augmentation's bias or
its precision instead. (Note: need-gated *retrieval*, ADR-013, is about cost/distraction of fetching
papers, not about gating reasoning rigor by difficulty — keep that distinction.)

### ADR-035 — Preset anchor mimics/risks are niche injections and must be inert unless case features support them. (Accepted; fix pending validation)
**Context:** the one genuine easy-case regression that survived the balanced gates (sensory-deprivation
auditory hallucinations → "NPSLE") was traced (by reading retrieved evidence + the model's reasoning
trace) to the `neuro_psych` preset injecting **NPSLE as the anchor mimic for every neuro_psych case**
(it was derived from an NPSLE case). That non-inert injection biased BOTH retrieval (queried NPSLE,
fetched 4 lupus papers, none on the case's actual features) AND the model's anchoring. **Decision:** a
preset's `ANCHOR_MIMIC_PAIRS_BY_PRESET` / `ANCHOR_RISKS_BY_PRESET` are niche knowledge and fall under
ADR-034(b) — they must be **inert unless the case's features match the mimic.** Also, round-1 retrieval
must query the case's OWN distinctive findings before any preset anchor, so the answer-naming
literature is actually fetched. **Anchors:** `build_case_feature_queries` (neuro_psych), `extract_case_features` ("symptoms"),
`_distinctive_symptoms`, `ANCHOR_MIMIC_PAIRS_BY_PRESET`. **Status (partial fix implemented, validating):**
the worst offender is FIXED — `build_case_feature_queries` for `neuro_psych` was **hard-coding** the
NPSLE/anti-NMDA queries (ignoring the case); it now builds round-1 queries from the case's own
extracted presenting features (`symptoms`), ordered by specificity so the discriminating feature
(e.g. "sensorineural hearing loss") leads. A generic symptom-based fallback covers presets with no
specific extractor. **STILL preset-biased (next):** the `_anchor_contrast_query` / `ANCHOR_MIMIC_PAIRS`
contrast query is still fixed per preset (e.g. "NPSLE vs anti-NMDA" for every neuro_psych case) — make
it feature-conditional too. **⚠️ Do not** hard-code a specific mimic for a whole preset family
unconditionally — it anchors every member and steers retrieval.

### ADR-032 — Stored knowledge pack of rare-entity cards, matched by features, with high-precision gating. (Accepted)
**Context:** comparing the 24 hard cases to their *source papers* showed the dominant failure is
anchoring on a near-neighbor of a rare entity (SPG7-for-DJ1, FXTAS-for-SCA12, Fryns-for-ASNS…). That
niche discriminating knowledge cannot live in weights or a generic prompt. **Decision:**
`knowledge_pack.py` holds **cards** (trigger features → specific entity → discriminator → confirmatory
test → source PMID); `match_cards` injects the top feature-matched cards into the prompt as
"specific_entities_to_consider," framed as *hypotheses to confirm/exclude, not answers*. Matching is
**precision-first** (requires a specific, non-generic trigger; dedupes shared tokens) because a wrong
card anchors the model — a miss yields *no* card rather than a wrong one. Grow the pack from every new
hard case. **Anchors:** `knowledge_pack.py`, `tests/test_knowledge_pack.py`, prompt payload
`specific_entities_to_consider`, `--no-knowledge-pack` ablation. **⚠️ Do not** loosen matching toward
recall without measuring the anchoring cost; **do not** phrase cards as assertions (they are
hypotheses). Trigger phrasing is an ongoing calibration task — tune against real prompt wording, on
the full set, not single cases.
**MEASURED COST + the correct fix (2026-06-14):** the augmented harness reclaimed 6/24 hard cases but
**regressed 5/12 easy control cases.** Root cause (from reading the regressions): **NOT the knowledge
pack** (zero cards fired on the 5 regressions — precision matching worked), but the **general gates of
ADR-033 being a one-way bias toward rare/specific/dual answers** (ALS→Aceruloplasminemia, etc.). **The
fix is NOT a difficulty gate** — a single diagnostic system must be robust across all cases; gating on
"difficulty"/confidence is brittle niche-angling. The fix is to make every augmentation **general
(bidirectional/Bayesian — base rates outrank de-anchoring; parsimony outranks comorbidity) or niche
(truly inert off-target).** **⚠️ Do not** add a difficulty/confidence gate; **do not** ship a one-way
de-anchoring gate without its base-rate counterweight; always report the hard number beside the
control number.

### ADR-033 — The universal gates encode source-paper discriminators (refuting-test, known-disease, gene-disambiguation, dechallenge, global-vs-focal). (Accepted)
**Context:** the source-paper analysis (`docs/augmentation_catalog_20260614.md`) surfaced concrete,
recurring discriminators the model ignored. **Decision:** the universal-gate layer (ADR-011) now also
carries: *seek the refuting test* (a normal DaTscan / transient antibody / antithyroid antibody
overrides a fitting story), *the referral/prior label is a hypothesis* (new symptom in a known rare
disease = its complication), *gene disambiguation* (name the gene, not a near-neighbor), *dechallenge*
(symptoms resolving off a drug is strong evidence), *global-vs-focal + parsimony*. **Anchors:**
`UNIVERSAL_FINALIZATION_GATES`. **⚠️ Do not** delete one without a case showing it caused a wrong
answer; these are distilled from real misses, not intuition.

### ADR-031 — The cited diagnostic report is the primary deliverable. (Accepted)
**Context:** the project's purpose is *information retrieval for clinicians*, not autonomous diagnosis.
**Decision:** the model must emit `key_papers` (title / PMID / DOI / how each contributed); a per-case
`report.md` renders the diagnosis + cited papers with clickable links. **Anchors:** final-prompt
schema `key_papers`, `_write_case_report`, `tests test_case_report_lists_cited_papers`. **⚠️ Do not**
reduce the output to a bare diagnosis string; the citations are the product.

---

## Architecture direction (designed, not yet fully built)

### ADR-038 — Evaluate with a top-5 ranked differential and pass@k, not just top-1. (Accepted)
**Context:** demanding the exact #1 diagnosis under-measures an information-retrieval system and
penalizes near-neighbor-gene cases (gold DJ-1 vs answered PRKN). **Decision:** the model returns a
ranked top-5; the harness records the gold's rank and reports pass@1..pass@5. **Evidence:** on the
pooled 52, pass@1=19% but **pass@5=38%** — the right answer is often in the top-5, just mis-ranked.
**Anchors:** prompt `ranked_differential`, `_ranked_diagnoses`, `_gold_rank`, `RetrievalGuidedEvalRow.gold_rank`,
`summarize_retrieval_guided_results` (pass@k). **⚠️ Do not** report only top-1 for an IR system; report
the pass@k curve. Also: anti-safety **research-benchmark prompt framing** is ON (published/de-identified
cases, never used on a patient, hedging scored wrong) to reduce safety-driven generic retreat.

### ADR-037 — Discriminator-driven re-rank of the top-5 (the reasoning lever for the ranking error). (Accepted — measuring)
**Context:** the dominant *determinable* failure is a ranking error — the gold is in the model's top-5
but a prototypical near-neighbor is #1 (≈half the in-top-5 cases). **Decision:** an optional focused
second pass (`rerank_differential`, `--rerank`) reorders the model's OWN candidates by case-specific
discriminator match, not base-rate familiarity (it may not add/drop candidates → cannot hallucinate).
Targets lifting pass@1 toward pass@5. **Anchors:** `rerank_differential`, `HarnessConfig.use_rerank`.
**Status (measured — FLAT):** pass@1 10→9 (noise), pass@5 unchanged-within-variance. Self-directed
re-ranking does NOT break the model's ranking bias — consistent with commit/self-consistency also being
flat (the model can't be talked out of its own anchoring by reweighting prompts). Kept OFF by default;
available as an ablation arm. The ranking gap (gold in top-5, not #1) is a genuine model limitation, not
fixable by self-prompting. **⚠️ Do not** re-attempt self-directed reasoning prompts expecting a break;
the lever is flat across commit/self-consistency/re-rank.

### ADR-036 — Retrieval VOLUME is not the lever; the ceiling on hard cases is the CASES, not the system. (Accepted — do not re-litigate)
**Context:** pushed hard to reclaim v4-Pro cold-failures via massive retrieval (the intuitive lever).
**Evidence (pooled 52 Pro-failures, full sweep):** Flash+harness ~9/52; +commit 8/52; +augment-extract
7/52; +self-consistency 6/52; +massive-flood(~44 papers) 6/52; **Pro+harness 6/52 (≤21% counting 5
truncation errors)**. All within run-to-run noise; wrong_entity dominant (34/52) in every config
including Pro. **Decision:** the bottleneck is selection/case-determinacy, not retrieval volume, not
finalization reasoning, not answer-model strength (Pro fails the same way). 90–95% reclaim is not
reachable on this pool. **Standard config = Flash + gates + knowledge cards + case-derived queries +
feature-conditional contrast + adaptive rounds + eval mode + commit instruction; paper-extractor OFF;
answer budget 12000.** **⚠️ Do not** re-attempt "just scale retrieval / more papers / more queries" to
break this ceiling — six configurations and two models show it flat. The remaining real work is case
determinacy (quantify under-determined cases) and precision (the right single discriminator), not volume.

### ADR-040 — Context-isolated scaled retrieval (per-paper Flash extractor). (Wired in; measuring)
Each paper screened in its own throwaway Flash context, returns a compact relevant note or nothing →
screen many without context bloat; papers propose follow-up queries. **Motivation (measured):** the
harness already retrieves ~23 papers/case (9 queries × ~3 articles × adaptive rounds) but **only the
top-8 raw abstracts ever reach the model** (context cap) — ~65% of retrieved papers were discarded
untouched. More top-n / queries / rounds all bottleneck at that cap. The extractor decouples
papers-screened from context-used: feed up to ~20 *distilled* relevant notes instead of 8 raw
abstracts, so breadth can actually be raised. **Anchors:** `paper_analysis.py`,
`HarnessConfig.use_paper_extractor`, `--paper-extractor`, `build_retrieval_guided_final_prompt`
(`screened_relevant_evidence`), `docs/scaled_retrieval_design_20260614.md`. **Status:** wired (off by
default), measuring effect on the third-100 double-failures with raised breadth (articles-per-query 6,
max-queries 4). **⚠️ Do not** pour raw paper text into the main diagnostic context; and when raising
breadth, keep the extractor ON or you just discard more.

### ADR-041 — Multi-angle diagnostic ensemble. (HISTORICAL — superseded by ADR-046 rejection)
Independent angle-agents (localization, tempo, exposure/iatrogenic, can't-miss, molecular,
common-mimic-skeptic) → consolidating coordinator; structurally forces the angles a single chain
skips (the hard-24 failure modes). Gate on difficulty so easy cases stay cheap. **Anchors:**
`diagnostic_ensemble.py` (built, `tests/test_diagnostic_ensemble.py`), `docs/multi_agent_design_20260614.md`.
**Superseded 2026-06-23:** see ADR-046. The full 88-case A/B with `JUDGE_VOTES=3` found the ensemble
regressed pass@5 and pass@1, so this earlier design note is retained only as historical context.
**Validated 2026-06-14:** the angles *do* surface the right hypothesis the single chain missed (the
can't-miss angle independently found HSV); the **can't-miss veto is a precision/recall knob** that
oscillates under single-case tuning + run-to-run variance — it must be calibrated on the full hard set
+ control set, and veto strength is partly a *product* decision (safety recall vs answer precision).
**Complementarity (key):** over all 24, ensemble 1/24 and gated-harness 1/24 reclaim *disjoint* cases
(ensemble→Mowat-Wilson via the molecular angle; harness→HSV via the can't-miss gate). The techniques
are insurance for each other; the strategy is to **combine** them (union, difficulty-gated), not to
pick one.
**⚠️ Do not** implement consolidation as additive voting (a confident wrong angle must not win), and
**do not** tune the veto on one or two cases — it will swing. Prefer surfacing case-grounded can't-miss
items as co-leading "must exclude" entries (fits the cited report) over forcing one `final_diagnosis`
string to carry the safety call.

### ADR-042 — Standing query-strategist loop. (Designed)
A continuous agent that watches the differential + papers' proposed queries, dedupes against
already-run queries, keeps issuing focused queries until resolution. The adaptive-rounds signal
promoted into its own process. **Anchors:** `docs/scaled_retrieval_design_20260614.md`.

### ADR-044 — Max-specificity / conjunction-emission lever. (REJECTED — null vs measured variance floor)
**Context:** twelfth-wave's dominant failure was conjunction/qualifier golds — the model named the primary
component (often rank 1) but omitted a supported second component (e.g. narcolepsy + PSG-documented apnea).
**Tried:** gated `--max-specificity` / `use_max_specificity` prompt clause pushing maximal specificity and
comorbid conjunctions. **Result:** A/B (no-retrieve, temp 0, 88 cases) ALL +2 / target-failures −1 /
control +3 — **+2 is below the measured production variance floor (spread 5 across identical temp-0
re-runs; ADR-045)**, i.e. noise. It also failed mechanically (target rank-1 still omitted the conjunction).
**Flag stays OFF**; left for reproducibility. ⚠️ Do not enable without a >floor effect.

### ADR-048 — Post-cutoff sets are HELD-OUT TEST; never tune the harness on them. (Accepted — integrity)
**Decision (project owner):** the post-cutoff waves (15th, 16th, … `publication_date ≥ 2026-02-01`) are a
**held-out test set** for contamination-controlled and cross-model evaluation. They may be *scored*, but
the harness, prompts, gates, knowledge pack, presets, and validators must **never be developed, tuned, or
selected using them** — doing so is data leakage and invalidates the contamination control. All runs to
date have been eval-only (no tuning). Harness development uses the regular dev waves only. **⚠️ Do not**
look at post-cutoff failures to motivate a harness change; if a change is inspired by them, it must be
validated on the dev sets and the post-cutoff set re-scored only as a final, untouched test.
**Publication:** the failure-selected hard subset (cases that fail bare DeepSeek Flash) may be *released*
(`data/eval/publish/flash_failures_hard_cases.jsonl`, 151 cases incl. 81 post-cutoff) — releasing ≠
tuning. The remaining (Flash-solved) cases stay reserved.

### ADR-049 — Post-audit data-quality cleanup of the 81 post-cutoff hard cases. (Accepted — integrity)
**Context:** three frontier auditors (opus-4.8, gpt-5.4, gpt-5.5) reviewed the 81 post-cutoff hard cases
for leakage / insufficient starting point. They **over-flag** (70/81 flagged by ≥2; only 3 clean by all
3), so flags were treated as a triage signal, not a verdict; each was source-checked by hand.
**Decision (project owner approved, "mend as much as possible"):** apply a **mend-maximal** slate —
**13 drops, 11 mends, 0 unresolved** — to both `data/eval/crossmodel/flash_fail_postcutoff.jsonl`
(81→**68**) and `data/eval/publish/flash_failures_hard_cases.jsonl` (151→**138**). Mends are
source-grounded prompt repairs only (delete post-question outcome leaks, move a result before the
question, rephrase a diagnostic alias to descriptive findings); **no gold was relaxed, broadened, or
rewritten.** Two cases the prior pass marked DROP were converted to MENDs (PMC13167955 gratuitous PAH
label deleted; PMC13154095 "primary VF" alias rephrased) because the gold stays determinable from the
legitimate workup; the former review case (PMC13149065, EPP) was DROPPED — its only decisive
discriminator (FECH/erythrocyte protoporphyrin) is absent and adding it would leak the answer.
**Tooling:** `scripts/preview_audit_arbitration_cleanup.py` is the single source of truth (DROP_IDS +
MEND_OPERATIONS) and now has an idempotent `--apply` that backs up to `*.pre_audit_cleanup.bak`. Lane
result files were pruned to the 68-case set so scores reflect passes among **retained** cases (e.g.
GPT-5.4 50/68, V4-Pro 30/68). **This is a data-quality fix, not harness tuning (ADR-048 still holds).**
**⚠️ Caveat — pending:** the 11 mended prompts still carry their **pre-mend** judge scores (uniform
across all models, so the panel stays internally comparable); a full mended-case re-score across the
panel is owed once provider credits are restored. **Anchors:**
`docs/AUDIT_ARBITRATION_PROPOSAL_20260623.md`, `docs/AUDIT_ARBITRATION_APPROVAL_PACKET_20260623.md`.

### ADR-047 — ≥5-round lead-following retrieval. (REJECTED — null/negative; dilution reconfirmed)
**Context:** the idea of ≥5 retrieval rounds where each round follows leads from the prior round
(alternative wordings/eponyms, associated entities, concrete leads). **Built it properly:** strengthened
the distiller to propose lead-following `additional_queries`, added an evidence-derived lead fallback so
forced rounds open new angles instead of repeating a generic query, verified rounds genuinely diversify
(post-diarrheal → GBS variant → Miller Fisher → anti-GQ1b on a novel case; serotonin-syndrome → heat
stroke on a hard one). **A/B** (full retrieval, JUDGE_VOTES=3 floor≈2, 39 cases): **pass@5 −1, pass@1
−4**, avg evidence/case **16→68 (4×)**, **0 fail→pass**. The lead-following works mechanically but the 4×
evidence DILUTES and de-ranks correct rank-1s. **Reconfirms the standing thesis: retrieval VOLUME hurts;
the bottleneck is SELECTION not retrieval — even targeted lead-following doesn't escape it.** Kept the
distiller lead-following improvements (strictly better when distilling) but **do NOT force ≥5 rounds**;
adaptive 1–3 rounds remains the default. The differential-driven variant (queries learn from the main
reasoning thread, ADR-042) is untested and would need to AVOID the dilution (tighter selection /
stop-on-discriminator) to have a chance.

### ADR-046 — Multi-angle ensemble + coordinator. (REJECTED — measurably HURTS; multi-agent not the bottleneck)
**Context:** the "parallel reasoning chains + reconciler" idea (GPT-Pro-style); already built as
`diagnostic_ensemble.py` (ADR-041, 6 angle agents + skeptical coordinator) but never wired/tested.
**Tried:** wired it as a gated (`--ensemble` / `use_ensemble`) reasoning pre-pass injecting the angles'
candidates + coordinator's reconciliation into the final answerer. **A/B** (no-retrieve, **JUDGE_VOTES=3**
so the floor is ~2, 88 cases): **pass@5 90%→85% (−4), pass@1 −11** — a clear regression, well beyond the
floor; 6 pass→fail vs 2 fail→pass. **Mechanism:** the coordinator's skeptical, etiology-focused
reconciliation makes the final answer TERSER and LESS specific, de-anchoring the model off an already-
correct, more-complete rank-1 (e.g. "carotid dissection causing bilateral globus pallidus infarcts" →
"carotid dissection", dropping the gold phrase). **Verdict:** the base single-chain reasoner is already
strong; layering a multi-agent ensemble adds noise and de-anchors. Flag stays OFF. **This is the THIRD
motivated reasoning lever to fail against the floor (ADR-043 axis, ADR-044 specificity, ADR-046
ensemble) — strong evidence the harness bottleneck is NOT reasoning architecture but gold quality +
under-determination.** ⚠️ Do not enable; do not re-attempt multi-agent reasoning without a >floor lift
in hand.

### ADR-045 — The variance floor is ~5 cases / 88 (judge nondeterminism); gate all fixes on it. (Accepted)
**Measured (2026-06-19):** identical config (bare Flash + LLM judge), same 88 cases, temp 0 → pass counts
[67,72,69], **spread 5, 18% of cases flip pass↔fail** between runs (judge is stochastic; DeepSeek isn't
bit-deterministic at temp 0). temp 0.4 → spread 11. **Decision:** a harness fix must move **>~6 % of N**
(here >5 cases) to count as real; report **mean±range over ≥3 seeds**; never adopt on a single-run delta
below the floor. Both motivated reasoning levers (ADR-043 axis-breadth, ADR-044 max-specificity) were null
against it. **⚠️ Do not** trust +1/+2 deltas at small N. Tooling: `baseline-eval --temperature`.
**Mitigation that works:** **`JUDGE_VOTES=3`** (majority-vote judging, judge.py) **halves the floor** —
measured spread 5→2, flip-rate 18%→9% on the same 88 cases. Recommended default for any A/B going
forward (it makes >2-case effects measurable). Cost: 3× judge calls (cheap Flash).

### ADR-043 — Etiologic-axis-breadth differential lever. (REJECTED — population A/B was null; flag stays OFF)
**Result (2026-06-17):** tested and **rejected**. Targeted 2-case test was encouraging (hyperthermia
PMC11617243 recovered to rank 1 with a hardened "must include a toxic + acquired hypothesis" clause),
but the **population A/B** (`--no-retrieve`, temp 0, baseline vs lever on 170 cleaned dev cases) was a
wash: precipitant subset 87%→85% (**−1**), control 83%→85% (+2), overall **85%→85% (+1/170)** with 11
fail→pass and 10 pass→fail — bidirectional churn, net noise. On the *target* subset it slightly
regressed. The lever displaces correct answers (forcing spurious toxic/acquired hypotheses) about as
often as it helps. The aconitine case stayed wrong even when forced — a genuine knowledge gap, not a
breadth gap. **Lesson (promoted to journal): a lever that wins on hand-picked cases can be net-zero at
population scale; never adopt on targeted wins — the population A/B is the gate.** The flag
(`use_axis_breadth` / `--axis-breadth`) and `scripts/build_axis_experiment.py` are retained OFF for
reproducibility; **⚠️ do not flip on** — it has been measured and does not help.

<details><summary>Original (experimental) rationale</summary>

### ADR-043 (original) — Etiologic-axis-breadth differential lever. (Experimental)
**Context:** two independent waves showed the same harness-reasoning failure — the model missed an
acquired/environmental cause because all five candidates collapsed to one endogenous class *despite an
acute precipitant in the history*: tenth-wave PMC11617243 (sustained 40 °C → cerebellar ataxia; top-5 all
hereditary ataxias) and eleventh-wave PMC10740282 (perioral paresthesia "shortly after meals" → aconitine
poisoning; top-5 all endogenous "spell" causes, no toxin/ingestion hypothesis).
**Decision:** add a gated `HarnessConfig.use_axis_breadth` flag (CLI `--axis-breadth`) that injects a
**self-gating, bidirectional** clause into the final-answer prompt: *when the history has an acute
precipitant/exposure, the top-5 must span etiologic axes (genetic/acquired/toxic-exposure/infectious/
inflammatory/neoplastic/vascular); if none, ignore and rank by base rates.* This obeys the no-difficulty-gate
rule (general lever, inert when irrelevant). **Status: NOT adopted.** Per the measurement-wall principle
(single-run deltas at small N are noise), it ships OFF and must clear a **multi-seed A/B** — pass@5 on the
precipitant subset (should-help/must-not-hurt) vs the no-precipitant control (must stay inert) — before
default-on. Experiment scaffolding: `scripts/build_axis_experiment.py`, run via
`retrieval-guided-eval --no-retrieve [--axis-breadth]`. **Anchors:**
`docs/eleventh_wave_checkpoint_triage_20260617.md`, `docs/tenth_wave_checkpoint_triage_20260617.md`.

</details>

---

## Data generation guardrails (cross-repo: NeurologyBM)

### ADR-050 — Refinement must preserve discriminators, never fabricate, and stay solvable. (Accepted)
**Context:** two benchmark items were defective — one dropped the deciding serologies and fabricated
an MRI finding; one asked for a pathological diagnosis with histology "pending." The generator's own
self-audit passed both. **Decision (in NeurologyBM `public_refine.py`):** deterministic source-grounded
validators (required findings present; numeric values match source), new `not_solvable` /
`needs_fidelity_review` statuses, and an optional independent solvability probe. **A generator cannot
be trusted to audit itself.** **Anchors:** `NeurologyBM/docs/case_challenge_quality_guardrails_20260614.md`.
**⚠️ Do not** rely on the model's self-audit alone; keep the deterministic checks.

---

## Documentation & memory model

### ADR-060 — Three-layer knowledge model: this registry + journal + dated docs. (Accepted)
**Decision:** **`docs/DESIGN_DECISIONS.md`** (this file) = the index of commitments and do-not-revert
rules; **`journal.md`** = the living "what we learned" narrative and principles; **dated `docs/`
write-ups** = the full analysis/design behind individual ADRs. New significant decision → add an ADR
here *and* (if it taught a durable lesson) a journal note. **⚠️ Do not** record a decision only in a
commit message; commits are not discoverable by the next agent.
