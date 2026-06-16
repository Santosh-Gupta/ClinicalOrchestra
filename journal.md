# Agent Journal

A living journal for agents (and humans) who work on ClinicalHarness. Its purpose is not to log
*what* was changed — git and the `docs/` write-ups do that — but to distill *what we learned*: the
deep principles about what makes a diagnostic harness effective, and what makes a good diagnostic
plan for the hardest cases.

Write here when you understand something you wish you'd known at the start. Be concrete: cite the
case that taught you. Be honest: record what failed and what you're still unsure about. Two
audiences should both get depth from this — **a top diagnostician** and **a serious
information-retrieval engineer** — because the hardest part of this problem lives exactly where
those two disciplines meet.

How to use it: read Parts I–III before touching the harness. Add a dated entry at the bottom when
you finish a meaningful chunk of work. Promote durable lessons up into Parts I–III; leave the
session narrative in the log.

This journal is the *why-it-matters* narrative. Its companion, **[docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md)**,
is the authoritative **list of commitments** — the decisions you must not silently revert, each with
its rationale and a do-not-revert clause. When you make a significant decision, record it in *both*:
the lesson here, the commitment + code anchors there.

---

## Part I — Principles of an effective diagnostic harness

**1. The scorer is part of the harness, not a neutral observer.**
We spent effort "fixing" cases that were already correct — the lexical scorer rejected *metastatic
melanoma* vs *metastatic malignant melanoma (masseteric metastasis)* because the strings differed.
It also *passed* a wrong answer ("anti-NMDA vs NPSLE, pending") because the key string "NPSLE"
appeared inside a hedge. **Diagnostic equivalence is a judgment, not a string operation.** Until the
measurement instrument is trustworthy you are optimizing noise. Build the judge first; treat a
suspicious pass *and* a suspicious fail as bugs to investigate.

**2. Failures are not one thing — separate the mechanisms before fixing anything.**
The same "fail" came from at least five different causes: scorer artifact, garbage retrieval,
*biased* retrieval, cognitive anchoring, and an underdetermined prompt. Each needs a different fix,
and a fix for one does nothing for another. The single highest-leverage analytic move is to read
the model's actual reasoning + the retrieved evidence for each failure and *classify the mechanism*
before writing a line of code.

**3. Retrieval can hurt as easily as help — and it is not free even when it's good.**
Two layers to this, both measured:
- *Bad retrieval distracts.* A topically "relevant" case report of the *wrong* mimic pulls the
  model toward the wrong answer. Garbage evidence (generic queries returned "viscosupplementation
  for knee osteoarthritis" for a cardiac angiosarcoma case) and biased evidence (a single-sided
  query "AML eosinophilia inv(16)" retrieves only inv(16) literature and manufactures false
  confidence) are both real. Fixes: **query the contrast between competing hypotheses, not the
  topic** ("A versus B distinguishing features"); filter by overlap with the case's discriminating
  vocabulary; re-query when a pass returns only off-topic hits.
- *Even good retrieval hurts when the model already knows the answer.* A controlled ablation
  (10 cases Flash passes closed-book, retrieval the only variable) went **9/10 closed-book → 7/10
  with retrieval** — two cases regressed *because* the retrieved literature surfaced a more
  common/famous mimic (renal leiomyosarcoma → sarcomatoid RCC; CADASIL → PACNS), and zero
  already-correct cases improved. **So retrieval must be gated on need, not applied
  unconditionally.** The control signal is already in hand: self-consistency *agreement*. High
  closed-book agreement → trust the model, skip/down-weight retrieval; low agreement / unstable
  differential → retrieve. Retrieval is a treatment with side effects; dose it where the diagnosis
  is uncertain, not everywhere.

**4. Retrieval that the reader can ignore is theater.**
If the final answer doesn't have to cite the snippet that changed its mind, you cannot tell whether
retrieval did anything. Force grounding: every claimed discriminator should point to the evidence
that supports it, and a checker should verify the snippet actually says so. (Not yet built — see
`docs/evolution_ideas`. It's the most under-rated item on the list.)

**5. Encode principles, not answers.**
We have 50+ per-case "presets". The ones that *work* are all instances of ~8 reusable clinical
heuristics (see Part II). Per-case gates keyed by case ID are lookup tables wearing a lab coat: they
inflate the score on the cases you tuned and transfer to nothing. The real engineering is to select
*feature-indexed principles* ("a single positive antibody does not override the phenotype") from the
case's findings, not from its identity. If a gate names the answer, you've left the harness and
entered the answer key.

**6. Measure variance, and separate it from bias.**
At temperature 0 the model still flips run-to-run on borderline cases. A single-run pass count is
noisy at ±3. Self-consistency (sample k times, cluster, majority-vote) does two things: it recovers
true variance, and — more importantly — it *exposes* systematic bias. A case where 4/5 samples
confidently give the *wrong* mimic is not noisy; it's anchored, and more sampling won't save it.
**Agreement fraction is your triage signal**: low agreement → retrieve/sample more; high agreement +
wrong → fix the reasoning or accept it's out of reach.

**7. You cannot claim improvement without a control and an ablation.**
The harness is tuned on the cases it's scored on — the most dangerous form of self-deception in this
work. You need (a) a held-out set of cases the model already passes, to prove you didn't *regress*
them (we caught a gate that flipped a previously-correct answer), and (b) component on/off ablations
to know *which* part earned the gain. Without these, "18/22" is a number about your test set, not
about the harness.

**8. Data quality is upstream of everything.**
Two of the hardest "model failures" were broken prompts: a lupus case with the ANA/anti-dsDNA
*deleted* (and an MRI finding fabricated), and a neurofibroma case with the entire histology
withheld. No reasoning can recover information that isn't in the prompt. Distinguish *hard for the
model* from *impossible from the text* — a "solvability probe" (can a strong model with full
reasoning reach the key from the prompt alone?) is a cheap, essential guard. Garbage-in is not a
harness problem you can out-engineer.

**9. Prefer the strongest available judge, but make judging robust.**
A stronger judge (Pro) is stricter on borderline equivalence and catches commitment failures — but
it's also slower and flakier, and a silent timeout that falls back to a lexical scorer turns a true
pass into a fail. Always fall back judge → *secondary judge* → lexical, never judge → lexical.
Better still, give the judge a rubric (same entity? lineage? species? acceptable qualifier?) and a
small human-labeled calibration set so you *know* its error rate instead of trusting it.

---

## Part II — What makes a good diagnostic plan for the hardest cases

These are the reusable principles behind the gates that actually moved cases. They are written as a
diagnostician would state them, but each is also a *retrieval and reasoning specification*.

**1. Build the problem representation before the differential.**
Compress the case into semantic qualifiers (acute/chronic, focal/diffuse, the distinctive finding,
the host). The differential should be generated from this abstraction, not from the first salient
word — anchoring begins at the moment of first representation.

**2. The benchmark case is selected to be atypical — so the common answer is more often the trap.**
This is the single most useful prior for hard sets. The familiar/prevalent/famous diagnosis
(MOGAD over MS, anti-NMDA over lupus psychosis, inv(16) over t(8;21), DLBCL over myeloid sarcoma,
the commonly-reported sibling species over the actual one) is exactly what these cases are built to
punish. Generate the lead hypothesis, then *deliberately argue the strongest rarer alternative* and
make the case decide between them.

**3. Reason to the discriminator, not to the diagnosis.**
A good plan names the one finding or test that separates the top two hypotheses and goes and gets
it. "What would distinguish A from B, and is it present?" beats "what is most likely?" Almost every
rescue in this repo came from forcing this comparison.

**4. A single positive test does not override the phenotype.**
A low-titer/transient MOG antibody does not make MS into MOGAD; eosinophilia does not make t(8;21)
into inv(16). Weight the whole gestalt (time course, distribution, the rest of the panel) over one
seductive positive. Conversely, a single *negative* test rarely excludes (negative CSF cytology,
negative IGRA): "the test was negative" and "the disease is absent" are different claims.

**5. Match your specificity to your evidence — in both directions.**
Don't stop at the category when the case hands you the discriminator (don't say "fungal infection"
when arthroconidia + sequencing name the species; don't say "spindle-cell sarcoma" when the IHC
names the subtype). Equally, don't claim a species/subtype the evidence doesn't support. Species ≠
genus, subtype ≠ disease, lineage matters: these are where confident wrong answers live.

**6. When one finding is unexplained, suspect a second process.**
The hardest cases are often two things at once (a vascular tumor *and* an invasive fungus; an
overlap syndrome). If your unifying diagnosis leaves a salient finding unexplained, the unexplained
finding is a clue, not noise — consider a synchronous/second pathology rather than force-fitting.

**7. Separate the axes of the question.**
Many misses were one decision masquerading as two collapsed together: clinical/morphologic diagnosis
vs the underlying base histology; colonization vs species identification; the syndrome
(autoimmune encephalitis) vs the antibody subtype. Decide each axis on its own evidence; getting one
right does not excuse the other.

**8. Commit — but state what would change your mind.**
A differential is a step, not an answer. "A vs B, pending testing" is a non-answer both clinically
and to a scorer. Commit to the single most likely entity, *and* name the test result that would
overturn it. (Committing to one entity while awaiting confirmation of *that* entity is fine; hedging
between two different entities is not.)

**9. Don't reason past the data — but notice when the data was withheld.**
If the prompt genuinely lacks the discriminator (no serology, histology "pending"), the honest
output is the best-supported read *plus the specific next test*, and a flag that the case may be
underdetermined. A good diagnostician knows the difference between "I don't know" and "this can't be
known from what I was given."

---

## Part III — Failure taxonomy (a field guide)

When a case fails, classify it before fixing it:

| Class | Signature | Fix lives in |
| --- | --- | --- |
| Scorer false negative | model answer is clinically right, marked fail | the judge (equivalence, qualifiers, synonyms) |
| Scorer false positive | hedged/partial answer marked pass on a substring | the judge (commitment rule) |
| Retrieval failure | evidence is off-topic / random | query construction + relevance filter |
| Retrieval bias | evidence all favors one mimic | symmetric contrast queries |
| Anchoring | committed to the common/familiar entity; evidence was usable | reasoning: forced strongest-alternative + discriminator |
| Specificity miss | right category, wrong species/subtype/lineage | specificity gate + species-level retrieval |
| Conflated axes | colonization-vs-ID, syndrome-vs-subtype merged | separate-the-decisions gate |
| Commitment failure | lists differentials, won't pick | commitment instruction + self-consistency |
| Variance | flips run-to-run; correct answer is the mode | self-consistency (recovers it) |
| Systematic bias | flips run-to-run; wrong answer is the mode | reasoning/retrieval fix, or accept out-of-reach |
| Underdetermined prompt | even a strong model can't reach the key from the text | the dataset, not the harness |

The most expensive mistake is treating a class with the wrong tool — e.g. adding gates to a variance
problem, or sampling harder on a systematic-bias problem.

---

## Entry log

### 2026-06-13 — scorer, retrieval, gates, data quality, self-consistency, ablations

Picked up at "19 of 22 remaining failures." First real finding: ~3 of those weren't failures, they
were scorer artifacts — which reframed the whole problem (Principle I.1). Built an LLM
diagnostic-equivalence judge; it later also caught a *false positive* (hedge substring match),
forcing the commitment rule (II.8).

Classified the genuine failures by mechanism (Part III) and found the dominant ones were anchoring
on the familiar mimic and biased/garbage retrieval. Generalizable fixes — relevance filtering,
symmetric mimic-contrast queries, and principle-style finalization gates — took the harness from an
effective 3/22 to roughly 15–20/22 depending on judge and run variance.

Two "failures" turned out to be **broken prompts**: a lupus case with ANA/anti-dsDNA deleted and an
MRI finding fabricated, and a neurofibroma case with the histology withheld. Reconstructed both from
the open-access sources and propagated the fix to the canonical dataset. This was the clearest
lesson of the session: *data quality is upstream of all reasoning* (I.8). Recommended a
post-transform validator so the pipeline can't silently drop the discriminating findings.

Self-consistency sampling (III: variance vs bias) was the most conceptually useful addition — not
because it raised the score, but because it *told us which residual failures are fixable*. Two
high-variance cases recovered; two others were revealed as confidently-wrong (the model never
reaches *Saprochaete clavata*; it says *telangiectatic osteosarcoma* 4/5 times). Those are honest
"not yet / maybe never with this model" cases, not noise.

Open questions for the next agent:
- Do the gates generalize, or are they lookup? The control + ablation run was built to answer this;
  read its result before trusting any single pass number.
- The borderline answer key "lipoma … with hibernoma component" vs the model's "hibernoma" — is the
  key right? Judge models disagreed. Worth a clinician's eye.
- Per-case presets badly want to become feature-indexed principles (Evolution idea #2). Until then,
  the harness can't help a case it hasn't been hand-tuned for — which is the whole game for the
  *next* 100 cases.

### 2026-06-14 — the two broken prompts were a generator bug, so we fixed the generator

Traced both flawed cases to NeurologyBM's DeepSeek-v4-Pro refinement step (`public_refine.py`), and
generalized the lesson into three failure modes a transform pipeline must be guarded against:
**omission** (dropping the discriminator — NPSLE lost its ANA/anti-dsDNA), **fabrication/value
drift** (inventing the MRI finding, altering the CSF numbers), and **unsolvability** (asking for a
pathological diagnosis with histology "pending"). The deepest point: the model's *own* adequacy
self-audit said `is_self_contained: True` for **both** defective cases. **A generator cannot be
trusted to audit itself** — you need deterministic checks against the source (every required finding
must appear in the prompt; every distinctive numeric value in the prompt must appear in the source)
and, ideally, an independent solvability probe (a blind model must be able to reach the answer from
the prompt alone). Both are now implemented in `public_refine.py` with new `not_solvable` /
`needs_fidelity_review` statuses. Corollary for harness work: **when a case looks unsolvable, suspect
the data before adding a gate** — a gate that "fixes" an underdetermined prompt is just memorizing
the answer key. This is Principle I.8 earned the hard way, now pushed upstream into the generator.

### 2026-06-14 — control + ablation: gates earn their keep, retrieval has side effects

Ran the experiment Principle I.7 demands. Two clean results: (1) **gates are load-bearing** — 6
gate-dependent cases went 4/6 with gates vs **0/6** with `--no-gates`, retrieval held constant, so
the principle-gates do real reasoning work rather than laundering a retrieved answer. (2)
**retrieval is double-edged** — on cases Flash already passes closed-book, adding retrieval went
9/10 → 7/10, with two confirmed regressions toward common mimics and zero gains. Promoted the
second into Principle I.3: *retrieval is a treatment with side effects; dose it on need.* The
actionable synthesis for the next agent is to gate retrieval on self-consistency agreement —
trust the model when it's internally consistent closed-book, retrieve only when the differential is
unstable. Also: keep the control set (`runs/control_manifest_flashpass.jsonl`) as a permanent
regression guard — every harness change should be checked against it, because "helps the 22 hard
cases" and "doesn't break the easy ones" are different claims.

### 2026-06-14 — generalized the gates: feature-indexed preset selection

Before benchmarking 100 *new* cases, closed the biggest overfitting hole: the harness mapped each
known `case_id` to a hand-tuned preset (`PRESET_BY_CASE_ID`), so any unseen case fell through to the
weak `general` path — the one the control ablation showed *regressing* easy cases. New module
`preset_selection.py` selects a preset from the case's **features** (vocabulary in the redacted
challenge prompt, never the answer key) via a weighted keyword table, grounded in the preset
checklists. Validated against 33 hand-labeled cases with overrides off: **79% exact, 91%
family-level agreement** — and all 3 residual misses fail *safe* (2 fall to `general`, 1 picks a
clinically-defensible alternative). Design: the 22 tuned cases keep their override for continuity;
unknown cases (the incoming 100) auto-route by features; `--feature-presets-only` forces pure
feature selection to measure generalization on the known set.

Lesson promoted to Principle I.5: **encoding the reasoning principle is what generalizes; encoding
the answer (per-case presets) does not.** Two authoring traps worth remembering for the next agent:
generic tokens silently dominate (the bare word "emergency" matched "emergency department"
everywhere and mis-routed cases to `acute_neuro_emergency`; "vision" hijacked optic-glioma routing)
— anchor on *syndrome-specific* vocabulary and validate against held-out labels at the family level,
because exact-preset agreement is the wrong bar when most presets are single-case. Open question:
re-run the control + ablation once the 100 new cases land, this time with feature selection as the
only routing — that measures whether the principle families transfer or were quietly overfit.

### 2026-06-14 — adaptive retrieval rounds (agent decides depth)

Replaced fixed-count retrieval with agent-decided depth. `max_rounds` is now a safety *cap* and
`min_rounds` a floor; between them the distillation subagent's own sufficiency judgment drives
continuation. The distill prompt now asks an explicit question — *can a clinician confidently
discriminate the lead diagnosis from its top mimic and satisfy the finalization gates?* — and emits
`differential_resolved` / `remaining_uncertainty`. It runs another round only when the differential
is unresolved AND it proposes a genuinely NEW query (a convergence guard, keyed off normalized
`previous_queries`, so it can't loop forever asking for evidence it already retrieved). `--no-adaptive-rounds`
preserves the legacy fixed heuristic for ablations. Lesson for tuning: the right stop signal is
"is the discriminator in hand?", not a query count — let depth scale with case difficulty, but
require every extra round to name the specific gap it will close (open-ended "need more" must not
buy a round). Worth an ablation once the next benchmark lands: adaptive vs fixed-2, measuring
accuracy and average rounds/case.

### 2026-06-14 — concurrency: parallel case evaluation with per-backend safety

Added `--concurrency` to retrieval-guided eval: independent cases run on a bounded `ThreadPoolExecutor`
(threads, because the work is HTTP-bound). Default 1 = unchanged sequential behavior. Results are
collected back into **manifest order**, not completion order (regression-tested), so concurrency
never changes the output, only the wall-clock.

The real work was making the shared clients safe at high fan-out — the lesson being that
**concurrency limits live in different places per backend, so you cannot use one knob**:
- *NCBI* enforces ~3/s (no key) / ~10/s (key) at the *account* level. Many threads share one
  `NcbiClient`, so its rate spacing is now serialized under a lock held across the sleep — global
  rate stays correct regardless of worker count. (NCBI effectively becomes the throughput floor;
  that's intended — we must not get banned.)
- *DeepSeek* allows 500 (pro) / 2500 (flash) concurrent at the account level and returns HTTP 429
  over it. The model client now retries 429/5xx with exponential backoff + full jitter (honoring
  `Retry-After`), so transient cap hits self-heal instead of failing a case.
Eager-initialized the answer client before dispatch so workers share one thread-safe client rather
than racing on lazy init (a nested-closure assignment would also have shadowed it — watch for that
when refactoring loops into closures).

**Concurrency limit ≠ rate limit — and they need opposite defenses.** DeepSeek caps *concurrency*
(in-flight requests), which you defend *reactively*: bound the pool, retry 429. OpenAI/Anthropic-style
providers cap *requests-per-minute and tokens-per-minute*, which you must defend *proactively*: space
and token-budget requests before sending, or you get 429s regardless of how few are in flight. Added
a `ratelimit.py` seam for the proactive case: the model client calls `rate_limiter.acquire(tokens=...)`
before every request; default is `NoOpRateLimiter` (DeepSeek), and `SlidingWindowRateLimiter` enforces
RPM/TPM when `MODEL_MAX_RPM`/`MODEL_MAX_TPM` are set. Critical subtlety: rate caps are *account-level*,
so the limiter is a process-wide singleton shared across the answer client, judge client, and all
worker threads — a per-client limiter would silently allow N× the real limit. Token budgeting uses a
cheap char/4 + reserved-completion estimate; swap in a real tokenizer when a provider's TPM is tight.

Open follow-ups: (1) live-validate concurrency against the real APIs once the Flash run frees NCBI
(separate processes have separate rate-limiters, so don't run two retrieval jobs at once). (2) The
next parallelism axis for the "thousands of papers" goal is *within* a case — fan out queries /
full-text fetches — which will need the same account-level NCBI budget shared across cases (a
process-wide limiter, not per-client), so revisit the locking model before going there.

### 2026-06-14 — three-stage eval protocol + a bare baseline mode

Locked the evaluation protocol (was running it out of order before): **(1) bare model, no harness**
→ **(2) stronger model filters the failures** → **(3) same weak model WITH the harness**. Stage 1
defines the floor, Stage 2 the ceiling and a *solvability filter* (cases even the strong model fails
cold are likely flawed/unsolvable — exclude them before crediting/blaming the harness), Stage 3
measures the harness's lift over the floor on the cases that are actually winnable. Concretely:
bare Flash → Pro on Flash's failures → Flash+harness. Added `benchmark baseline-eval` (new
`baseline_eval.py`) for stages 1–2: it sends only the redacted case prompt (no retrieval, gates,
checklist, or rounds), reuses the same lexical+judge scoring and `RetrievalGuidedEvalRow` schema so
all three stages are directly comparable, and supports concurrency. Lesson: **"with harness" only
means something against a "without harness" floor measured on the identical cases and scorer** —
build the bare baseline as a first-class mode, not an afterthought (this is Principle I.7's control,
made routine).

**Future idea (parked) — a standing query-strategist agent.** Today the distill subagent decides
`more_retrieval_needed` and proposes `additional_queries` once per round. The next evolution is a
*separate, cheap Flash agent* that continuously monitors the diagnostic run's state (current
differential, evidence gathered, unresolved discriminators) and keeps proposing new search
directions — i.e. promote adaptive-rounds query generation into its own ongoing agent rather than a
per-round side-output. Pairs naturally with within-case retrieval concurrency (fan out its proposed
queries in parallel under the shared NCBI budget).

### 2026-06-14 — the 24 hard cases: the most powerful evolution yet (paper-grade)

The three-stage protocol left 24 cases that defeated bare Flash, bare Pro, AND Flash+harness — our
richest data. Reverse-engineering them produced the central thesis of this project and a wave of
changes. Full analysis: `docs/hard24_gap_analysis_20260614.md`; designs in `docs/scaled_retrieval_*`
and `docs/multi_agent_*`.

**THE THESIS (this is the paper's spine).** *For these hard cases the diagnostic information is
largely retrievable from PubMed; the failures are hypothesis-formation and query-formulation
failures, not knowledge-availability failures.* Proven live: `valproate risperidone interaction` →
top hit is literally a paper on catatonia from that interaction (the exact missed answer);
`infectious encephalitis mimicking autoimmune encephalitis` surfaces the misdiagnosis literature for
the HSV case the model called autoimmune; `myoclonic atonic epilepsy gene` surfaces reviews naming
SLC6A1. The model had the *reach* and didn't use it. **This reframes the product: we are optimizing
information retrieval for a clinician, not replacing the clinician** — which is also why the cited
report (papers + how each contributed) is the primary deliverable, not the diagnosis string.

**THE FAILURE TAXONOMY (24 cases).** M1 anchoring on the famous entity when the textbook clue is
stripped (15); M2 missed iatrogenic/drug-interaction cause (4); M3 under-commitment / "cause unknown"
instead of the specific gene/entity (2+); M4 missed comorbidity / unexcluded second pathology (3).

**LESSON FOR HARNESS/AGENT DEVELOPERS — load-bearing principles must be UNIVERSAL, not gated behind a
router.** The single most damning finding: we *had* an `adverse_drug_event` preset, yet none of the 4
drug-cause cases were routed to it, so the principle never fired. A principle that only applies when
a classifier happens to pick the right bucket is a principle you don't really have. Fix shipped: a
`UNIVERSAL_FINALIZATION_GATES` layer applied to *every* case regardless of preset — anti-anchoring
("name the rarer entity that fits when the classic clue is absent"), iatrogenic-first (drug timeline
before intrinsic disease), treatable-can't-miss-first (exclude HSV before autoimmune encephalitis,
even without fever/classic MRI), commit-to-the-specific-entity, and second-pathology/comorbidity.
Promote to **Principle I.5** corollary: *encode the universal principles universally; reserve presets
for genuinely entity-specific discriminators.*

**LESSON FOR INFORMATION-RETRIEVAL ENGINEERS — query length is a silent killer.** PubMed ANDs every
term; a 10-term natural-language query returns **zero** results, and the harness then "fails" with no
evidence — invisibly. Long queries were almost certainly a major hidden cause of harness misses. Fix
shipped: cap queries to ≤8 meaningful terms (`_focus_query`), and broaden progressively on zero
results (targeted broadener → 2-term minimal). Corollary heuristics that worked empirically:
*contrast queries* ("A mimicking B", "B vs A distinguishing features") surface the misdiagnosis
literature directly; *phenotype→gene* queries ("<phenotype> gene / genetic causes") reach the named
gene without knowing it. New **Principle**: a zero-result query is a bug, not an answer — detect and
broaden; prefer few high-signal terms over a faithful sentence.

**LESSON FOR DOCTORS (and the paper's clinical message).** Every one of the 24 is a teaching case in
de-anchoring: the published vignette becomes hard precisely when the pathognomonic clue is removed,
which is also what real atypical presentations do. The durable clinical habits the data rewards:
build a medication timeline before naming a disease; exclude the treatable emergency (HSV) before the
fashionable diagnosis (autoimmune encephalitis); ask "could this be two diagnoses?"; and for a
recognizable phenotype, push to the named entity rather than settling for "genetic, unknown." The
harness is, in effect, an externalized, retrieval-backed version of these habits.

**ARCHITECTURE DIRECTION (designed, partially built).** (a) *Context-isolated scaled retrieval*
(`paper_analysis.py`, built + tested): each paper is screened in its own throwaway Flash context and
returns only a compact relevant note or nothing, so we can read thousands of papers without bloating
the main thread; papers propose their own follow-up queries, creating literature-driven query
expansion the case author can't pre-empt. (b) *Multi-angle ensemble* (designed): independent Flash
agents argue distinct framings — localization, tempo, exposure/iatrogenic, can't-miss, molecular,
common-mimic-skeptic — feeding a coordinator that consolidates. This is diagnostic "dropout": it
*structurally forces* the angles the single chain skipped, which is exactly where the 24 failed. Gate
the ensemble on difficulty (self-consistency agreement) so easy cases stay cheap.

**EVAL INTEGRITY (built).** First-class eval mode: in eval mode the harness must never retrieve/read
the source paper (pmcid/doi/title filter + a generic anti-cheat instruction that never reveals the
identifiers, so it can't leak the answer); off for the doctor use case, where reading the actual
source report is legitimate. The principle: *the anti-cheat guard must protect the answer without
naming it.*

**OPEN / NEXT (for whoever continues).** (1) Quantify solvable-vs-flawed across the 24 — fetch each
source abstract and decide whether the deciding discriminator was even in the prompt; the genetic
cases may be under-determined (variant withheld), in which case scoring should reward the named
entity, not the variant string. This is the honest denominator for any "harness lift" claim in the
paper. (2) Re-run the hard-24 with the universal gates + query fixes to measure their lift, then the
full 100 against the control set to confirm no easy-case regression. (3) Build the case-specific
"stored knowledge pack" (retrieval-augmented cards for the rare entities) — the niche knowledge that
can't live in weights or context. (4) Implement the multi-agent ensemble per its design doc.

### 2026-06-14 — validating the evolution: gates nudge, the ensemble forces, the veto is a knob

Two empirical follow-ups to the hard-24 work.

**Universal gates re-run on the 24:** reclaimed 1/24 — and it was the HSV can't-miss case, where the
answer shifted from a flat "autoimmune encephalitis" to "must first exclude HSV" with next-step CSF
PCR + empiric acyclovir. Honest read: 1/24 is within judge noise (Principle: never over-read a 1–3
case delta), but the *mechanism* is real and it's the highest-stakes case. **Gates nudge the model;
they don't structurally force the skipped angle.** The cited reports worked well (24 reports, ~57 real
PubMed citations with plausible "how it contributed" notes) — the deliverable is landing.

**Multi-agent ensemble (`diagnostic_ensemble.py`, built + tested):** the decisive finding is that
**angle decomposition surfaces the right hypothesis the single chain misses** — a dedicated `cant_miss`
agent independently produced "HSV encephalitis, start acyclovir," and `exposure_iatrogenic` produced
the valproate-toxicity line, on cases the whole single-chain pipeline (Flash, Pro, and gated harness)
got wrong. That is the core thesis of the ensemble, confirmed.

But two lessons, both promoted:
- **The reasoning-token tax (Principle, generalize) applies to EVERY model call, not just the final
  answer.** The angle agents truncated to empty at 2048 tokens — the same `finish_reason=length` →
  empty-content failure that bit the Pro baseline. Any new sub-agent call must budget ≥8192. This is
  now stated in ADR-017 as a universal rule.
- **The can't-miss veto is a precision/recall knob, and you cannot tune it on one case.** A strong veto
  reclaimed HSV but reflexively led with HSV on a drug-encephalopathy case; grounding it ("case-supported
  AND not better explained") fixed the drug case but let HSV slip. With run-to-run variance on top,
  single-case prompt tuning *oscillates*. **New Principle: calibrate consolidation/veto behavior against
  the full hard set + the control set, never against the anecdote in front of you** — and recognize that
  veto strength is partly a product safety decision (missing HSV is worse than an extra workup), not a
  pure accuracy parameter. The more robust design is to surface case-grounded can't-miss entities as
  co-leading "must exclude" items in the cited report rather than forcing one diagnosis string to carry
  the safety call.

**The complementarity result (the most important number of the day).** Scored over all 24:
gated harness 1/24, ensemble 1/24 — **but they reclaim DIFFERENT cases.** The gated harness got HSV
(can't-miss angle baked into a universal gate); the ensemble got Mowat-Wilson syndrome (a rare genetic
entity, via the dedicated `molecular_test` angle) which the harness missed. **The two techniques are
disjoint, not redundant — exactly the dropout thesis: each angle is insurance against the others'
blind spots, and the union beats any single one.** This reframes the strategy: stop hunting for the
one technique that cracks many of the 24 (these are brutally hard — several are rare genes that are
near-impossible to name cold), and instead *combine* complementary techniques (gates + ensemble +
literature-driven retrieval, difficulty-gated) and measure the union. Sobering honest note for the
paper: on the hardest tail, incremental techniques give incremental, complementary reclaims — the
headline isn't "X solves the hard cases," it's "the information is retrievable and a portfolio of
independent reasoning angles recovers more of it than any single chain."

Net: the evolution's pieces are built and individually validated; the next real work is *calibration on
the full set* and *combining* the complementary techniques (ensemble ∪ gated-harness ∪ retrieval, with
the control set guarding easy cases), not more single-case fiddling. Wiring the ensemble +
scaled-retrieval into the eval loop, difficulty-gated, is the path to a defensible headline number.

### 2026-06-14 — reading the source papers changed the augmentation strategy

Finally did what I should have first: fetched the **original source papers** for the 24 (PMC abstracts)
and read the *real* discriminator each author used. Catalog: `docs/augmentation_catalog_20260614.md`.
This was far more actionable than gold-vs-answer alone, and it reshaped the work.

**The dominant pattern is "right family, wrong member."** On the 9 genetic cases the model named a
*near-neighbor* gene (SPG7-for-DJ1, FXTAS-for-SCA12, CDKL5-for-SPG4, Fryns-for-ASNS, mitochondrial-for-
ATP1A3). It's not ignorant of the domain; it under-resolves within it. And the papers literally state
the rule that resolves it ("suspect SLC6A1 in typical absence + mild cognitive, normal MRI"). So the
fix is **specific, retrievable knowledge**, not a bigger model.

**Built two augmentation layers, both grounded in the source discriminators:**
- *General gates* (every case): seek the **refuting test** (a normal DaTscan beats a fitting story; a
  transient/low-titer antibody or evolving imaging argues against autoimmune closure; antithyroid
  antibodies → SREAT); the **referral/prior label is a hypothesis** (a new symptom in a known rare
  disease is its complication — the RVCL-S case); **gene disambiguation**; **dechallenge** weighting;
  **global-vs-focal + parsimony**.
- *Specific knowledge pack* (`knowledge_pack.py`): rare-entity cards (trigger→entity→discriminator→
  confirmatory test→PMID), feature-matched and injected as *hypotheses to test*. The user's "stored
  document for niche knowledge" — and the right home for the long tail.

**The hard lesson, twice over: feature matching is a precision/recall knob, and the wrong setting
hurts.** First pass injected irrelevant cards (a hypoxic-ischemic case told to "consider SLC6A1") —
that *anchors* the model, worse than nothing. A single generic word ("tremor") stacked across a card's
triggers and fired it. Fix: require a **specific** (non-generic, often multi-word) trigger, dedupe
shared tokens, and bias to **precision — a miss yields no card, not a wrong card.** Off-target
injections dropped 24→5. **Principle: any feature-matched injection into a reasoning prompt must be
precision-first, because a confident-but-wrong suggestion is an anchor, and framed as a hypothesis to
confirm/exclude, not an assertion.** Card-trigger phrasing is ongoing calibration against real prompts.

This also reinforces the dropout thesis from a new angle: gates (general) and the knowledge pack
(specific) and retrieval and the ensemble are *independent* nets over the same failures — the strategy
is the portfolio, calibrated on the full set, not any single hero technique.

**Result: the augmented harness reclaimed 6/24, up from 1/24** — and every reclaim is mechanistically
attributable (SLC6A1/ASNS/drug-induced-parkinsonism ← knowledge pack; lamotrigine-parkinsonism &
AED→vitD→hypocalcemia ← iatrogenic/refuting-test gates; mixed-overdose ← parsimony; SREAT ←
refuting-test). Well outside the ~4-pt judge band. **But two disciplines must temper the celebration:**
(1) **derivation-set caveat** — the knowledge-pack cards were seeded from these exact 24, so 6/24 proves
the *mechanism* (the knowledge is now reachable and used), not yet *generalization*; the gates and
gene-disambiguation principle should transfer, the specific cards only help carded entities, and the
honest generalization test is a held-out set. (2) **control discipline (ADR-004)** — the added prompt
content can anchor easy cases, so a regression check on bare-Flash-pass cases is mandatory before
banking the lift. Both are the difference between "we encoded the answers" and "we built something that
generalizes." Next agent: report the augmented number *alongside* the control-set number, always.

**THE CONTROL VERDICT (the most important result of the evolution).** Ran the augmented harness on 12
easy bare-Flash-pass cases: only **7/12 survived — 5 regressed.** And the regressions name the
mechanism: a rare-entity over-call (Aceruloplasminemia), a comorbidity over-call (bvFTD + a second dx),
hedging into "probable/awaiting" (too_generic), and anchoring to CVT/NPSLE. **The very augmentations
that reclaim hard cases (push to the specific/rare entity, consider a second pathology, distrust the
obvious) regress easy cases by the SAME mechanism.** Net on the samples: hard +5 (1→6), easy −5 (12→7)
— a wash here, and likely **net-negative on the full 100** if the ~40% easy-regression rate held over
the 71 easy cases. The 6/24, taken alone, was a mirage; the control check (ADR-004) caught it.

**CORRECTION (the right principle — a difficulty gate is the WRONG fix and a danger to the system).**
My first instinct was to gate the augmentations on the model's uncertainty. That is wrong: confidence
is unreliable (the model was confidently wrong on the hard cases), and more deeply, **a single
diagnostic system must be robust across all cases — there is no "hard case mode."** A difficulty gate
is exactly the brittle niche-angling that makes a system fragile. The real diagnosis came from reading
the 5 regressions: **none had a niche card injected** (the knowledge pack was correctly inert — good),
so the knowledge pack was not the culprit. **Every regression came from the general gates being a
ONE-WAY BIAS toward the rare/specific/dual** (ALS->Aceruloplasminemia, sensory-deprivation->NPSLE,
classic anti-NMDAR hedged to "probable AE"). An "improvement" that systematically pushes toward exotic
answers is not a general improvement; it is a bias that helps the rare-answer cases and hurts the
common-answer ones by the same act.

**Promote to a top principle (replaces the difficulty-gate idea): every augmentation must be either
GENERAL — and therefore BIDIRECTIONAL/Bayesian, helping common AND rare cases — or NICHE — and
therefore truly INERT when its discriminator is absent. No difficulty gates.** A general gate that only
pushes one direction is mis-built: pair it with its counterweight (base rates / Occam / "common is
common" outranks de-anchoring; parsimony outranks comorbidity; "name the specific entity" excludes
manufacturing an exotic one). A niche card that fires on a non-matching case is mis-built: raise its
matching precision until it is silent off-target (already done — 0 cards fired on the 5 regressions).
And if balancing the general gates and tightening the niche still leaves a case wrong, the failure is
elsewhere — **look at what information retrieval missed, or read the main thread's actual reasoning
trace** — do not paper over it with a meta-gate. Fix applied: rewrote `UNIVERSAL_FINALIZATION_GATES`
with "base rates first" as the overriding rule that subordinates de-anchoring and specificity; the
hard-case gains came from niche cards + refuting-test + parsimony (all preserved), so the prediction is
that balanced gates keep most of +5 and recover most of -5. Re-validating on hard-24 AND easy-12
together — and from now on those two numbers are reported as a pair, never apart.

### 2026-06-14 — balanced gates work; and one residual failure exposes the real root cause (preset anchors are non-inert niche)

Rewrote the universal gates to be **bidirectional** (base-rates/Occam OUTRANK de-anchoring; parsimony
outranks comorbidity; commit-to-specific forbids manufacturing an exotic dx). Head-to-head on the
control: biased gates = hard 6/24, easy 7/12; **balanced gates = hard 5/24, easy 9/12** — net better,
and 2 of the 3 remaining easy "misses" became near-misses (top-of-basilar: venous→**arterial ischemic**;
anosognosia: now **leads with anosognosia**), i.e. judge-specificity, not bias. No difficulty gate
needed — being properly bidirectional was the fix, exactly as the principle (ADR-034) demands.

**Then I did what the directive said for the one genuine residual regression** (sensory-deprivation
auditory hallucinations → "NPSLE"): read what retrieval fetched and read the main thread's reasoning
trace. The result is the most instructive failure of the whole project, and it's THREE failures at once:
- **IR:** every retrieved paper was about NPSLE/anti-ribosomal-P; nothing about auditory hallucinations
  or hearing loss was fetched. The query never went after the case's own distinctive features.
- **Reasoning:** the model listed the correct answer (auditory Charles Bonnet) then rejected it with a
  *false discriminator* ("hallucinations persisted despite hearing aids ⇒ not sensory deprivation" —
  clinically wrong; deafferentation hallucinations can persist despite aids).
- **Root cause (systemic):** the `neuro_psych` preset injects **NPSLE as the anchor mimic for EVERY
  neuro_psych case** (it was derived from an NPSLE case). That non-inert injection biased BOTH the
  retrieval query AND the model's anchoring toward lupus on a case with nothing to do with lupus.

**Promote to a principle (this is the user's "niche must be inert" rule, applied where it bites
hardest — PRESETS): a preset's anchor mimic / anchor risk is a NICHE injection and must be inert
unless the case's features actually support it.** A preset that hard-codes "consider NPSLE" (or any
specific mimic) for a whole family anchors every member, including the ones where it's wrong — the
same failure mode as a mis-fired knowledge card, but worse because it also steers retrieval. **Fix
direction (validate when ready):** make `ANCHOR_MIMIC_PAIRS_BY_PRESET` / `ANCHOR_RISKS_BY_PRESET`
feature-conditional (inject only when case features match the mimic), and make round-1 retrieval query
the case's OWN distinctive findings before any preset anchor, so the literature that would name the
answer actually gets fetched. This converts the presets from biased niche into inert-when-irrelevant
niche — and it's the through-line of the whole evolution: every general thing must be bidirectional,
every niche thing must be silent off-target, and what's left is fixed at the IR or reasoning layer,
never with a meta-gate.

**Implemented + validated.** Two concrete fixes: (1) `build_case_feature_queries` for neuro_psych was
literally hard-coding the NPSLE queries (the smoking gun — it ignored the case); replaced with
case-derived queries from a new presenting-`symptoms` extractor, ordered by specificity so the
discriminator leads. (2) `_anchor_contrast_query` is now feature-conditional (inert unless the case
raises the mimic). Result on the control+hard sets: **best configuration yet — hard 6/24, easy 9/12
(combined 15/36)**, recovering the hard case the balanced gates had lost, with no easy regression. And
the exemplar NPSLE case **dropped the NPSLE anchor** (now "primary psychotic disorder") with its #1
retrieved paper now *"Auditory Hallucinations on Sudden Sensorineural Hearing Loss"* — the IR fix
provably fetched the answer-naming literature. The residual gap on that case is now purely diagnostic
*reasoning* (the evidence is present; the model under-weights it) — which, per the principle, is where
it should be fixed next, not with a gate. Lesson for the next agent: when a "case-feature" path is
hard-coded to a single entity, that is a retrieval bias hiding in plain sight — grep the query builders
for hard-coded disease names before trusting them.

**Full-config outcome + honest caveats.** With both fixes (case-derived queries + feature-conditional
contrast), the **NPSLE exemplar fully SOLVES** — final dx "auditory hallucinations secondary to
bilateral sensorineural hearing loss (sensory deprivation hallucinosis)" = gold — a complete
end-to-end demo of the method (diagnose as IR/bias → fix as general/inert → solved, no gate). Best
config = hard 6/24, easy 9/12 (15/36). BUT not a clean win: (1) **3 easy regressions persist**, and one
is diagnostic: **ALS → "Neuroferritinopathy"** — the base-rate gate did NOT hold this run though it had
earlier, so the exotic-over-call bias is *reduced, not eliminated*; the gate text may not be
load-bearing enough (test by ablating it). (2) **Run-to-run variance is now a genuine confound** — the
specific reclaimed hard cases changed between runs (this run gained Mowat-Wilson, lost SREAT) and the
ALS case oscillated; at 1-3 case granularity that is inside the judge/retrieval noise band (I.x /
ADR-005). **The 13→14→15 progression is directionally real but partly noise; a defensible headline
needs multi-seed runs or the full 100, never single runs at this granularity.** The two informative
residual misses (ALS→NBIA exotic over-call; top-of-basilar→CVT venous-vs-arterial) are reasoning-layer
problems to fix at the reasoning layer, not with gates. Next: (a) ablate each gate to confirm it is
load-bearing and not just decoration; (b) move to multi-seed scoring before any headline number; (c)
fix the discriminator-weighting reasoning failures (the model ignores an arterial finding; doesn't let
"common syndrome→common disease" actually win).

### 2026-06-15 — third-100 generalization checkpoint: general transfers, niche must accumulate

Ran the frozen improved harness on a FRESH set (third-100, 0 overlap with second-100) BEFORE any
set-specific tuning — the first-contact generalization checkpoint. Pipeline: bare Flash 62/100 → bare
Pro reclaims 10/38 → **improved harness reclaims 3/28 double-failures (11%)**, vs ~6/24 (25%) on the
derivation set. The ~halving is the most informative number of the day and it decomposes cleanly:
- **The general machinery transferred.** All 3 reclaims (MOGAD overlap, copper-sulfate toxic
  poisoning, MERS reversible-splenial) came from general gates + case-derived retrieval — NOT from a
  knowledge-pack card.
- **The niche part correctly did NOT transfer.** The knowledge-pack cards were seeded from
  second-100's specific entities (SLC6A1, ASNS…); third-100 has *different* rare entities (KCTD17,
  TANGO2, DHDDS, KCNQ3, Warsaw breakage…), so the cards stayed inert — exactly as designed. The
  dropped reclaims are the seeded-card contribution falling out.

**Principle (paper spine): GENERAL improvements transfer across sets; NICHE knowledge does not — it
must accumulate.** This is *why* the multi-dev loop is the right methodology: each new set is first a
held-out-ish generalization checkpoint (records whether the general machinery transfers), then a dev
set whose residuals grow the niche coverage and occasionally reveal a new general principle. Reserve a
final untouched set as the true test. Corollary for the long tail of rare genes: carding each entity is
slow coverage growth; the scalable general lever is **phenotype→gene retrieval** (find the gene via a
review without a pre-existing card) — prioritize that over hand-carding.

Third-100 residuals (25) re-confirm second-100's failure structure (gene near-neighbor; antibody
over-commit / **missed antibody-OVERLAP syndromes** — new emphasis: MNOS, triple-overlap, Morvan all
collapsed to a single antibody or anti-NMDA; missed tumor behind a psych/tox label). The recurring,
cross-set, *general* target is the autoimmune-overlap / don't-default-to-anti-NMDA-without-NMDA-antibody
reasoning. Round-2 augmentations derived from third-100 must be validated on the NEXT set, never by
re-running third-100 (that would just show memorization, like second-100's 6/24).

### 2026-06-15 — retrieval VOLUME alone is not the lever; reasoning-aware extraction is the multiplier

Goal shifted to: pool all dev failures (no held-out yet), push toward 90-95% reclaim of v4-Pro
double-failures, mainly by massively scaling retrieval (PubMed free, Flash cheap, per-paper extraction
keeps context flat). Measured the bottleneck first: the harness retrieves ~23 papers/case but only the
**top-8 raw abstracts reach the model** — ~65% discarded by the context cap. So wired the per-paper
extractor (ADR-040) into the loop: screen every paper in its own Flash context, feed only the distilled
relevant notes (up to ~20), so breadth decouples from context.

**First scaling test was a needed reality check:** 2× breadth (~47 papers/case) with a *thin-context*
extractor gave 2/28 — no better than the 3/28 baseline (within noise; also confounded by a 2048-token
truncation bug in the extractor, now fixed). **Lesson: throwing more papers at the model does not help
if the relevance screen is naive — volume without judgment is just more noise.** The limiting factor is
the QUALITY of the per-paper relevance judgment, not the count.

That reframes the IR lever (and the paper's IR section): **massive retrieval only pays when paired with
reasoning-aware extraction.** Implemented the multiplier: a cheap preliminary clinical-assessment pass
produces the working differential (common + can't-miss + rarer mimics + the separating discriminators)
*before* retrieval, and that full reasoning is handed to EVERY per-paper screen — so a paper is judged
relevant only if it bears on THIS case's hypotheses, not the topic. The extractor also now returns
`new_entity` (a diagnosis not yet in the differential that a paper suggests), the seed for surfacing the
long tail without pre-built cards. Testing reasoning-rich + massive on the pooled 52 now. If it helps,
the next lever is interleaving: feed `new_entity`/`proposed_queries` back into additional targeted
retrieval rounds (the standing query loop) rather than a single post-hoc screen. Open question for the
90-95% target: some Pro-failures are genuinely under-determined (rare gene whose variant isn't in the
prompt) — retrieval can name the entity but not invent absent data; that is the likely hard ceiling.

**RESULT — and it overturns the volume hypothesis.** Reasoning-rich + massive (≈44 papers/case, 6×4
breadth, per-paper notes replacing top-8 abstracts) scored **6/52 (12%), WORSE than the simpler config's
~9/52 (17%)**; second-100 dropped 6→3. Diagnosis (the SLC6A1 case is the tell): the knowledge card that
previously made the model COMMIT to SLC6A1 was still in the prompt, but buried under 20 distilled notes
the model **retreated to a generic hedge** ("genetic generalized epilepsy, etiology not specified").
Third-100 (no matching cards) stayed flat. **Mechanism: massive retrieval DILUTES whatever focused
signal exists and induces hedging — it fights the commit-to-specific gate. Where a focused signal
existed (a card), the flood washed it out; where it didn't, volume added nothing.** 

**Promote to a top principle (paper-worthy negative result): for these hard cases the lever is the
PRECISION of the few decisive items that reach the model, not the VOLUME of papers screened. More
evidence past a small threshold increases hedging and decreases commitment.** Consequences: keep the
paper extractor OFF by default (net-negative as wired); the best config stays top-8 abstracts +
case-derived queries + knowledge cards + bidirectional gates. If per-paper extraction is used at scale
at all, it must feed only the TOP FEW most-decisive notes (ranked, not a flat flood) and must not
displace a high-confidence card/discriminator. The real remaining levers are precision (retrieve and
surface the ONE right paper) and reasoning (commit vs hedge under uncertainty) — not volume. Likely
hard ceiling on this pool acknowledged; do not burn compute scaling a counterproductive lever.

**CONFIRMED across 3 configs — declaring the retrieval-volume hard limit.** Pooled 52 Pro-failures:
simpler/no-extractor ~9/52 (17%); augment/top-5-decisive 7/52 (13%); massive flood 6/52 (12%). All
cluster at 12-17%, within run-to-run noise — **no retrieval-scaling variant beats the simplest config.**
The intuitive "more retrieval → better" is FALSE on this pool; the harness is on a noise-dominated
plateau ~15%. **Decision:** paper extractor stays OFF by default; the best/standard config is top-8
abstracts + case-derived queries + knowledge cards + bidirectional gates + adaptive rounds + eval mode.
The retrieval-volume lever is exhausted — per the goal's escape clause, this is a hard limit and I am
not scaling it further. Remaining theoretical levers are (a) reasoning (commit-vs-hedge under
uncertainty — the SLC6A1 generic-hedge failure) and (b) the data (a real fraction of these cases are
under-determined: the gold needs a discriminator absent from the prompt, which no retrieval can
supply). 90-95% reclaim of cases that defeat BOTH Flash and Pro cold is, on this evidence, not
reachable; the honest, paper-worthy result is the *characterization* — retrieval helps via PRECISION
(the right card/discriminator/query), is neutral-to-harmful via VOLUME (dilution → hedging), and hits a
floor set by under-determined cases — not a headline accuracy number.

### 2026-06-15 — the bottleneck is SELECTION, not retrieval: the right entity is usually already in evidence

Pushed the reasoning lever after volume failed. Commit-vs-hedge instruction (final_diagnosis must be a
committed specific entity, caveats only in the uncertainty field): reduced hedging (too_generic
failures fell to 5) but did NOT raise reclaim (8/52, noise-equal to 9/52) — because the dominant
failure became **wrong_entity (35/52)**. Committing harder just turns hedges into confident-wrong.

Then the decisive diagnostic: for the wrong/fail cases, is the GOLD entity present in the retrieved
evidence? **~15 of 19 second-100 failures: YES — the right answer was retrieved and the reasoning chose
the wrong entity anyway** (keyword heuristic, direction robust). **So the bottleneck is SELECTION /
reasoning, not information availability or retrieval volume.** This is the cleanest confirmation yet of
the project thesis (the information is retrievable) AND it kills the "massive retrieval" hypothesis from
the other side: you can't fix a selection failure by retrieving more — the answer is already on the
table and the model picks wrong.

**Promote: the remaining lever is reasoning that actually lets the retrieved discriminator OVERRIDE the
model's anchor.** The anti-anchoring gate is necessary but not winning. Candidate fixes (testing):
self-consistency (if the right entity appears in some samples, plurality may surface it; won't help if
the model is consistently anchored wrong); a structured selection step (for each candidate AND each
entity named in evidence, tally the case's specific discriminators, then commit to the best-supported
one even if not the initial lead); and the multi-angle ensemble (independent reasoners surface the
entity the single chain anchors away from — it already reclaimed a case the single chain missed).
Clinical-safety note for the paper: optimizing reclaim pushes toward commitment, but a confident-wrong
answer is more dangerous to a clinician than an honest hedge — the commit instruction trades one for
the other, so its net clinical value is not the same as its judge-score value. Keep that distinction.

### 2026-06-15 — the hard limit, established across every lever AND both models

After volume failed, I exhausted the reasoning lever and then the model-strength lever. Full sweep on
the pooled 52 v4-Pro double-failures (all within run-to-run noise of each other):

| Configuration | reclaim |
| --- | --- |
| Flash + harness (simplest best) | ~9/52 (17%) |
| Flash + commit-vs-hedge | 8/52 (15%) |
| Flash + augment extraction (top-5) | 7/52 (13%) |
| Flash + self-consistency (k=3) | 6/52 (12%) |
| Flash + massive flood (~44 papers) | 6/52 (12%) |
| **Pro + harness (strongest selector + evidence)** | **6/52 (+5 truncation errs ⇒ ≤21%)** |

**Everything plateaus at ~12–21%, with wrong_entity the dominant failure (34/52) in every config —
including Pro.** This is the decisive result: the bottleneck is NOT retrieval volume (the answer is
usually already retrieved — see prior entry), NOT finalization reasoning (commit/self-consistency flat),
and NOT answer-model strength (Pro fails the same way Flash does, on the same cases, with the same
wrong_entity signature). **The ceiling is set by the CASES** — this pool is, by construction, the residue
that defeated both Flash and Pro cold, and a large fraction are either under-determined (the deciding
discriminator is not in the prompt; retrieval can name an entity but cannot supply absent data) or
genuinely ambiguous (the gold is one defensible reading among several, so even a strong selector with
the evidence in hand picks a different defensible entity that the judge scores wrong).

**Declaring the hard limit (per the goal's escape clause): 90–95% reclaim of v4-Pro cold-failures is not
reachable by retrieval or reasoning on this pool.** The strongest evidence is the Pro+harness result —
if a far stronger reasoner *with the right evidence retrieved* cannot exceed ~20%, no amount of Flash
retrieval/reasoning scaffolding will. The multi-angle ensemble remains available but is predicted not to
beat Pro (it is an ensemble of *weaker* Flash reasoners attacking a selection problem Pro already
fails). I am not burning compute scaling levers shown flat across 6 configurations and 2 models.

**The paper's real result is the characterization, not a headline accuracy number:** (1) for hard
diagnosis the information is largely *retrievable* — failures are hypothesis/selection failures, not
availability failures; (2) retrieval helps only through PRECISION (the right card/discriminator/query),
while VOLUME is neutral-to-harmful (dilution → hedging); (3) the residual ceiling is shared across
models and is governed by case determinacy + a common wrong-entity selection bias, not by the harness.
The honest headline for clinicians/IR: a cheap model + precise retrieval reaches a strong model's
performance, and the limit beyond that is the *cases*, not the *system*.

**Standard/default config locked (best across the sweep):** Flash answerer, paper-extractor OFF,
gates + knowledge cards + case-derived queries + feature-conditional contrast + adaptive rounds +
eval mode ON, commit-vs-hedge instruction ON (caveats preserved in the uncertainty field), final-answer
budget 12000 (ADR-017, fixes Pro truncation). Next dev set → run the frozen config as the next
generalization checkpoint; do NOT re-litigate the volume lever.

### 2026-06-15 — the ceiling is partly BROKEN CASES, not reasoning: determinacy gate before augmentation

Before declaring "it's all reasoning now," checked whether the failures are even answerable. Read
Pro's actual reasoning traces vs the source papers. Two exemplars settle it:
- **Broken/under-determined (PMC11138152):** prompt gives the parkinsonism phenotype + "a PD gene
  panel was SENT for sequencing" then asks "most likely GENETIC diagnosis?" — the result is withheld.
  Gold = DJ-1; DJ-1/PRKN/PINK1 are clinically near-identical AR early-onset PD, so the gene is NOT
  inferable. Pro answered PRKN (the commonest) and noted "awaiting genetic results." A reasonable
  answer to an under-specified question. **The case is broken, not the harness.**
- **Reasoning failure (PMC3011101):** the discriminators (prior dissection, progressive vessel-wall
  change, progression on anticoagulation) ARE in the prompt; Pro still said PACNS. Genuine selection
  failure.

**Scan: ~12-14 of the 52 (≈25%) are the broken pattern — pure-genetic golds whose gene requires the
withheld sequencing result.** So the ~15% plateau is INFLATED by unanswerable cases; the true
reasoning-phase denominator is the determinable failures, on which reclaim is higher. We are partly in
the reasoning-augmentation phase, but the metric must be cleaned first.

**Promote to principle: before crediting/blaming a diagnostic system on a hard case, verify the case is
DETERMINATE — every discriminator needed for the gold must be in the prompt. "Asks for a specific
gene/antibody/pathology whose defining result is withheld" is a broken challenge and must be fixed
(add the result / relax the gold to the determinable level / reframe to the next step / drop), not
counted.** This is the refinement guardrails' solvability check, extended from histology to
molecular/antibody specificity — now a NeurologyBM pipeline (docs/failure_determinacy_analysis_20260615.md)
to run over ALL dev sets.

Two synergistic fixes shipped/queued: (a) **top-5 ranked differential + pass@k** (implemented) — credits
"the right gene is among the candidates," the honest IR measure that side-steps demanding the exact #1
gene on near-neighbor cases; (b) anti-safety **research-benchmark prompt framing** ("public published
cases, never used on a real patient, hedging scores wrong") to pull the model off the safety-driven
generic retreat. Re-testing top-5 × {normal, massive} breadth now — also re-answers "does higher
papers still hurt" under the new conditions. And the genuinely-determinable residual (dissection-type)
is the real clinical-reasoning-augmentation target: discriminator-driven re-rank (test each candidate
against the strongest case-specific finding, demote what it refutes).

### 2026-06-15 — top-5 reframes the metric; re-rank is flat; ~31% of failures are broken cases

Three results this round. (1) **Top-5 + pass@k**: pass@1=19% but **pass@5=38%** on the pooled 52 — the
IR system is ~2x better than top-1 implied; the determinable failures are largely RANKING errors (gold
in the top-5, near-neighbor at #1). Anti-safety research-benchmark prompt framing shipped to reduce the
safety-driven generic retreat. (2) **Discriminator-driven re-rank: FLAT** (pass@1 10→9) — self-directed
re-ranking doesn't break the model's anchoring, consistent with commit/self-consistency. The model
cannot be talked out of its own ranking bias by reweighting prompts. (3) **Determinacy: ~16/52 (31%) of
failures are broken cases** — built a NeurologyBM `case_validation.py` (deterministic + LLM-ready) that
flags "asks for a specific gene/antibody/pathology whose defining result is withheld"; the genetic cases
(SLC6A1, DJ-1/PARK7, KCNMA1, SPG4, ATP1A3, KCTD17, DHDDS, TANGO2, KCNQ3) dominate. Added the same
specificity check to the creator (`public_refine.validate_refinement` → `specificity_unsupported`) so
future cases don't ship the defect.

**Synthesis of the phase question the user raised:** we ARE in the reasoning phase for the determinable
cases, but the raw ~15% was inflated by ~31% broken cases. The honest pipeline is: clean the broken
cases (relax over-specified genetic golds to the determinable level / add the withheld result / reframe
to next-step), then measure pass@k on the cleaned set — that is the true reasoning denominator. And
report **pass@5, not pass@1**, as the information-retrieval metric. The remaining reasoning lever that is
NOT flat is unclear from self-prompting (commit/self-consistency/re-rank all flat); the niche cards work
but don't transfer; so the next real experiment is on the CLEANED determinable set, where signal isn't
buried under broken cases. Next op: run the LLM determinacy+repair over all dev sets, apply repairs, and
re-score pass@k on the cleaned pool.

### 2026-06-15 — built + ran the case-mend pipeline over ALL dev cases: 27% were broken

Confirmed at scale: ran the NeurologyBM `case_validation` pipeline (LLM determinacy + source-grounded
repair) over BOTH full dev manifests (200 cases). **~54/200 (27%) were under-determined and are now
mended via `add_result`** — the deciding result appended VERBATIM from the source paper (sequencing
variant, antibody serology, IHC, dechallenge response), **gold diagnosis unchanged (0 relax_gold —
clinical truth preserved per the project standard).** Examples: SLC6A1 case gets "panel revealed de
novo SLC6A1 c.1648G>A"; NPC1 gets "compound het NPC1 c.3662A>G/c.3019C>T"; LNG-IUS depression gets
"symptoms improved after device removal." 2-3 cases per set were `drop` (unfixable), 1 `reframe`.

This is the key correction to the whole evaluation: **the ~15% Pro-failure-reclaim plateau was measured
on a pool ~27% contaminated with broken (unanswerable) cases.** The mended manifests are now the clean
benchmark. Diagnostic prompt also strengthened: explicitly states the vignette is from a published,
peer-reviewed case report whose correct diagnosis is already established — zero diagnostic risk, so no
safety reason to hedge.

Re-benchmark in progress on the CLEANED cases (Flash → Pro on Flash-fails → harness-Flash on
Pro-fails), reporting pass@1..5. Expectation: bare-model pass jumps (mended cases now contain the
deciding result, so the answer is reachable), and the residual Pro-failures are a much cleaner set of
genuine reasoning failures — the honest denominator for the reasoning-augmentation phase. Lesson
promoted: **always run a determinacy/mend pass on a generated benchmark before trusting a hard-case
ceiling; a "model failure" rate is meaningless until the cases are verified answerable.**

### 2026-06-15 — THE clean headline: 88–92% end-to-end after fixing the benchmark

Ran the full 3-stage pipeline on the MENDED dev manifests (broken cases fixed by add_result, gold
preserved). The honest funnel over 200 cleaned dev cases:
- bare Flash **149/200 (74%)** (was 67% pre-mend)
- bare Pro reclaims **+20** of the 51 Flash-failures → 169/200 (85%)
- harness (top-5 best config) on the **31** genuine double-failures: **pass@1=7 (23%), pass@5=14 (45%)**
- **end-to-end solved: 176/200 (88%) at top-1, 183/200 (92%) at top-5.**

**The "~15% reclaim ceiling" was almost entirely broken-case contamination.** Once ~27% of cases are
mended to be answerable, the combined system lands at **88–92%**, in the target band. On the genuinely
hard cleaned tail (31 cases that defeat both models even with the deciding result present), the harness
adds real value: 45% pass@5 (vs the 19%/38% on the contaminated pool). 17/31 remain absent from top-5 —
the true frontier (a mix of the hardest reasoning cases and the ~5 unfixable/dropped ones).

**Top principle (the biggest lesson of the whole project): a generated benchmark's "hard-case failure
rate" is meaningless until the cases are verified ANSWERABLE. We spent many configurations chasing a
15% ceiling that was a data artifact; a single determinacy/mend pass revealed the real number is
88–92%.** Validate the benchmark before optimizing the solver. And report pass@k (an IR system's right
metric), not just top-1 — pass@5 is ~2x pass@1 because the residual is largely a ranking problem.

The reasoning-augmentation phase now has a CLEAN target: the 17 top-5-absent cleaned cases (genuine
"model has the info, reasons wrong"), measured against signal instead of broken-case noise. Self-prompt
reasoning levers (commit/self-consistency/re-rank) were all flat; the open question is whether anything
beyond niche cards moves the genuine reasoning frontier.

### 2026-06-15 — deep dive on the 17 residual failures: 6 mechanisms, and ~5 are STILL broken

Read each of the 17 top-5-absent cleaned cases (mended prompt + harness ranked-5 + reasoning trace +
source). Full write-up: `docs/reasoning_failure_deepdive_17cases_20260615.md`. They are NOT a uniform
"reasoning" bucket — six mechanisms, and crucially **~5 are still broken cases of TWO classes the
determinacy validator missed**, so the genuine reasoning tail is ~12 and the real solve-rate is even
higher than 92%.

- **Cat 1 — Comorbidity/conjunction not represented (~4).** The gold is "A AND B"; the model lists A and
  B SEPARATELY in its top-5 but never the conjunction (bvFTD+GAD65, ALS+CIDP, triple-antibody, AE+tumor).
  It already FOUND the parts. **Highest-value general fix: conjunction-aware output + score-credit when
  all components are in the top-5.** (Also caught a real titer-misread: GAD65 60 UI/mL read as "refutes
  AE.")
- **Cat 2 — Anchoring on the prototype despite contrary cues (~2).** HSV case: prompt says "consider
  infectious," top-5 is 5 non-infectious entities (DLB anchor won; can't-miss gate didn't override).
  Startle-epilepsy case: the mend added a HEXA *VUS* and the model dove to Tay-Sachs — treated a VUS as
  diagnostic. Lessons: VUS must be down-weighted; the mend can inject a red herring.
- **Cat 3 — INVALID challenge, gold is a research finding not a diagnosis (~2). NEW broken class.**
  Sources are a hemispheric-valence neuroscience study and an awake-craniotomy language-mapping paper;
  the "golds" are experimental constructs. The model reasonably gave MDD/glioma. → drop; add validator
  rule `gold_not_a_diagnosis` (source is research/methods, not a diagnostic case report).
- **Cat 4 — Prompt evidence REFUTES the gold (~1). NEW broken class.** PMC11743964: prompt says "MRI:
  no tumor recurrence" + meth-positive; gold is tumor recurrence. The model's meth-psychosis is the
  correct answer to the prompt. → validator rule `prompt_refutes_gold`.
- **Cat 5 — Genuine phenotype→gene gap (~1–2).** KCTD17: SGCE-negative M-D → KCTD17 is the literature's
  next gene; model didn't know it AND listed SGCE despite the stated negative. Fixes: phenotype→gene
  retrieval; a "respect stated negatives" gate.
- **Cat 6 — multi-axis / wrong-axis / wording near-miss (~4).** IAD anchored on movement not the anxiety
  core; multi-axis developmental profile; ketamine #1 wording near-miss.

**Top lessons promoted.** (1) Even a *cleaned* hard tail still contains broken cases of new types —
benchmark validation is iterative; add `gold_not_a_diagnosis` and `prompt_refutes_gold` to the
validator. (2) **Comorbidity/conjunction is a representation+scoring gap, not a knowledge gap** — the
single highest-value general harness fix here, because the model already finds the parts. (3) Reasoning
gates worth adding (general, grounded): respect stated-negative results; a VUS is not diagnostic;
contrary cues must override the prototype. (4) The mend pipeline must flag VUS/uncertain additions
(faithful but misleading). The genuine, irreducible reasoning frontier is now small and well-characterized.

### 2026-06-15 — Bucket A done; and we've hit the MEASUREMENT wall (must multi-seed now)

Finished the existing-data improvements. (1) NeurologyBM is handoff-ready for the next batch: the
validator flags all 3 broken classes (under_determined / gold_not_a_diagnosis / prompt_refutes_gold) +
a VUS-red-herring guard, has a `validate-cases` CLI, the creator carries the specificity check, and
`docs/next_batch_creation_guide.md` is the turnkey guide. (2) Conjunction/comorbidity scoring shipped:
monotonic (`gold_rank = best(single-string match, all-components-covered)`, keyword-gated split so it
never penalizes single entities containing "and"), plus a prompt instruction to emit conjunctions
directly. It cleanly credited the bvFTD+GAD65 case; other comorbidity golds use phrasings the splitter
doesn't catch, and broadening it is sub-noise.

**The hard, important conclusion: at N=31 with ±2-3-case judge variance, single-fix effects (+1/+2) are
indistinguishable from noise in a single run.** The conjunction re-score's apparent 14→12 was pure
judge variance (the logic is provably monotonic). **We are now measurement-limited, not idea-limited.**
Promote to a top principle: *past a point, optimizing a hard-case benchmark requires escaping the
variance floor BEFORE trusting any further fix — multi-seed (3-5 runs, mean±range) and/or larger N.
Tuning against single-run deltas at small N is fitting noise.* Concretely: (a) multi-seed the headline
comparisons on the cleaned set before claiming any further lift; (b) the next dev set (more N, fresh
generation) is the real unlock — run it through `validate-cases` first. Reasoning-gate ideas (#23:
respect-stated-negatives, VUS-not-diagnostic, contrary-cue) remain queued but should only be accepted
on multi-seed evidence, given the wall.

### 2026-06-16 — eighth + ninth wave generalization checkpoint

Two fresh batches from the data agent, both run through `validate-cases` before use (the standing
rule). **Eighth wave:** 50 cases → 15 under-determined, 11 auto-mended (`add_result`, gold preserved),
1 reframe, 3 drops → **47 strict**. **Ninth wave:** 12 cases → 4 not-determinable, 4 drops, 0 mends →
**8 strict**; notably the validator fired all three broken classes here (2 under_determined, 1
gold_not_a_diagnosis, 1 prompt_refutes_gold) and on two cases *correctly refused to fabricate* a
TB-culture / lesion-pathology confirmation rather than relaxing the gold — dropped instead. Inspection
of both strict files: prompts present, golds well-formed under `answer_key.diagnosis`, unique ids, drop
reasoning sound. The "low-quality agent" warning did not bear out for the shipped strict sets — the
validation pipeline caught and removed the genuinely broken cases.

**Combined 55-case (47+8) three-stage funnel** (`data/eval/wave89_checkpoint/`):
- Stage 1 bare Flash: **40 pass / 15 fail** (73%).
- Stage 2 bare Pro on the 15: **5 pass / 9 fail / 1 inconclusive** (PMC12237386 — persistent
  server-side `IncompleteRead(0 bytes)` on Pro after 6 retries; prompt is *small* (2054 chars) so it's
  a Pro-side connection drop, not an oversized-context issue). So **9 confirmed Flash+Pro
  double-failures + 1 inconclusive → 10 cases to Stage 3**.
- Stage 3 Flash+harness (paper-extractor + full-text, max-queries 4 / articles 6 / max-rounds 3,
  eval_mode on) on the 10: **pass@1 = 1, pass@5 = 4**; 3 of the 4 wins at gold_rank 2–3
  (present-but-mis-ranked = the SELECTION bottleneck again).

**End-to-end: pass@1 = 46/55 (84%), pass@5 = 49/55 (89%)** — in the established cleaned-set band, so
the system generalizes to fresh, un-tuned data.

**Triaged the 6 pass@5-failures** (`docs/wave89_checkpoint_triage_20260616.md`): 2 reasoning (ADEM —
textbook post-infectious multifocal-FLAIR+encephalopathy pattern present, model anchored vascular and
ADEM never entered top-5; ASMAN — prompt states the sensory discriminator, model said AMAN), 2 IR
(venous-hypertensive myelopathy with only 7 evidence items; a pulmonary sarcomatoid-carcinoma case
that was mis-scoped into a neuro batch), 2 gold-quality (a bespoke "autoimmune-thyroid focal CNS
disorder *without* encephalopathy" label where the model's SREAT answer is the same mechanism; a rare
vertebral-artery variant + dropped DKA conjunct). **Headline: even the residual failures are "right
neighbourhood" — the frontier is subtype granularity and de-anchoring, not retrieval coverage.**

**New, GENERAL benchmark-quality finding → NeurologyBM `validate-cases` gap.** The specificity check
guards withheld *results* but not gold *granularity/labeling*. Two kept-"determinable" cases carry a
gold whose distinguishing qualifier (subtype/variant name, present/absent feature, or bespoke label)
isn't fairly determinable from the prompt vs a standard parent entity. Proposed validator rule: flag &
relabel-to-parent (or drop) such golds. This is the concrete next improvement to the creation pipeline.

Operational note (re-surfaced the known trap): a `--case-id` *subset* re-run **overwrites** the
aggregate `retrieval_guided_results.jsonl` with only the subset rows. Correct re-run idiom is the
**full manifest + `--skip-existing`** (reuses existing response files, only hits the missing/failed
case, and rebuilds the complete aggregate). Used that to recover the Stage-2 tally.

<!-- Next agent: add your dated entry below. Promote durable lessons up into Parts I–III. -->
