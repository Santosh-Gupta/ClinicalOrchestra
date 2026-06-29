# Operator Runbook — running the harness end-to-end

**Audience:** an incoming agent (any LLM) taking over the harness. This is the turnkey procedure for
the recurring job: *a new benchmark batch arrives → validate it → run the 3-stage eval → analyze the
outputs → propose changes*. Read [AGENTS.md](../AGENTS.md) first for the non-negotiable rules
(don't silently revert documented decisions; record ADRs/journal entries). This doc is the "how to
actually operate it" companion to that.

Sibling repo: **NeurologyBM** (`../NeurologyBM`, public remote `DiagnosticBenchmarking`) *generates*
the case challenges. This repo *evaluates* them. Boundaries in [project_split.md](project_split.md).

---

## 0. Environment setup

Secrets live in `./.env.local` (gitignored — never commit). It defines:

```
DEEPSEEK_API_KEY=...     # answerer + judge (DeepSeek v4 Flash / Pro)
DEEPSEEK_MODEL=...       # default model when --model is omitted (deepseek-v4-flash)
NCBI_API_KEY=...         # PubMed/PMC E-utilities (higher rate limit)
NCBI_EMAIL=...           # NCBI contact email (required for nontrivial runs)
```

Load them into the shell before any run:

```bash
cd /Users/santoshg/Coding/ClinicalHarness
set -a; . ./.env.local; set +a
```

Invoke the CLI either way:

- Console script (after `pip install -e .`): `clinical-harness ...` (alias: `clinical-orchestra`)
- No install / vendored: `PYTHONPATH=src python3.11 -m clinical_harness.cli ...`
  (the `clinical_harness.cli:main` entry point — use `python3.11`, see the Python gotcha below).

> **Python gotcha:** the repo requires **Python ≥3.11**, but the machine's `python3` is **3.8** — under
> it, imports fail with `'type' object is not subscriptable` (3.8 can't subscript `dict[...]`/`X | Y` at
> runtime). Use **`python3.11`** explicitly (e.g. `PYTHONPATH=src python3.11 -m clinical_harness.cli …`,
> `python3.11 -m unittest …`). The CLI needs only stdlib + the package.
>
> **Node gotcha (see user memory):** the *system* Node is v14 and Homebrew is broken — for the viewer
> frontend, vendor a modern Node rather than relying on system Node.

Models: `deepseek-v4-flash` (cheap answerer + the judge, held fixed), `deepseek-v4-pro` (stronger
filter). Judge is **always** `deepseek-v4-flash` for comparability across stages.

---

## 1. A new batch arrived from NeurologyBM — validate it FIRST

> **If the batch is *raw* (no gold), refine it first.** A `*_raw_challenges_*.jsonl` from the data
> agent carries `challenge_prompt` + `answer_rest` (raw trailing article text) but **no
> `answer_key.diagnosis`** — it can't be scored. The data agent's Pro refinement pass tends to die on
> `Response ended prematurely` (connection drops on large payloads). Unblock it yourself on the robust
> **Flash** path (no install of NeurologyBM needed; just `pip install --user requests` for the python3.11
> you run it with):
>
> ```bash
> cd ../NeurologyBM && set -a; . ../ClinicalHarness/.env.local; set +a
> PYTHONPATH=src python3.11 -c "import sys; from neurologybm.cli import main; sys.exit(main())" \
>   refine-public-challenges --manifest <raw>.jsonl --out <refined_dir> \
>   --model deepseek-v4-flash --run --concurrency 6 \
>   --max-article-chars 20000 --api-retries 6 --api-retry-sleep 5
> ```
>
> This writes `<refined_dir>/<run_id>/refined_cases.jsonl` with the full structured schema
> (`answer_key.diagnosis` + self-audits: adequacy/fidelity/leakage/solvability, `status` ∈
> `refined_needs_spotcheck` / `not_solvable` / …). Drop `status=not_solvable`, then feed the rest to
> `validate-cases` below. Smaller `--max-article-chars` and Flash are what beat the premature-end
> failures; re-refine weak extractions on Pro only if quality looks off.

Never evaluate a raw batch. ~27% of historical cases were *broken* (answer not reachable from the
prompt, or the gold isn't a clinical diagnosis). The NeurologyBM validator catches these. From the
**NeurologyBM** repo:

```bash
cd ../NeurologyBM
set -a; . ../ClinicalHarness/.env.local; set +a   # same DeepSeek/NCBI keys
neurologybm validate-cases --manifest <ready_manifest>.jsonl \
  --out data/pmc/processed/case_validation/<batch>_<date> --mend
```

This writes `validation.jsonl`, `mended_manifest.jsonl` (originals + add_result mends, drops removed),
and `summary.json`. Evaluate the **mended manifest** (or the data agent's downstream `*_strict_*.jsonl`
handoff, which is the same kept set). The validator flags
four broken classes — see
[NeurologyBM `docs/public/next_batch_creation_guide.md`](../../NeurologyBM/docs/public/next_batch_creation_guide.md):
`under_determined` (add the withheld result, **gold unchanged** — never relax the gold),
`gold_not_a_diagnosis` (drop), `prompt_refutes_gold` (drop/reframe), `gold_overspecific`
(add the subtype discriminator, or relabel-to-parent for human review, or drop).

**Sanity-check the strict file before trusting it** (the data agent is not always high quality):

```python
import json
rows=[json.loads(l) for l in open("<strict>.jsonl")]
# unique case_ids; challenge_prompt present; gold under answer_key.diagnosis
for r in rows:
    assert r["challenge_prompt"].strip()
    assert (r["answer_key"]["diagnosis"]).strip()
```

Gold lives at `answer_key.diagnosis` (aliases at `answer_key.aliases`).

---

## 2. The three-stage eval protocol (the core job)

Locked protocol (ADR; journal 2026-06-14): **(1) bare Flash → (2) bare Pro on Flash's failures →
(3) Flash + harness on the Pro double-failures.** Stage 1 = floor, Stage 2 = ceiling + solvability
filter (a case even Pro fails cold is likely flawed), Stage 3 = the harness's lift on winnable cases.
Work in a per-checkpoint dir, e.g. `data/eval/<checkpoint>/`.

### Stage 1 — bare Flash (no harness)

```bash
clinical-harness benchmark baseline-eval \
  --manifest data/eval/<checkpoint>/<strict>.jsonl \
  --out-dir  data/eval/<checkpoint>/stage1_bare_flash \
  --model deepseek-v4-flash --judge --judge-model deepseek-v4-flash \
  --concurrency 4 --skip-existing --progress
```

### Stage 2 — bare Pro, on Stage-1 failures only

Build a manifest of the Stage-1 `fail`/`not_run` cases, then:

```bash
clinical-harness benchmark baseline-eval \
  --manifest data/eval/<checkpoint>/stage1_flash_failures.jsonl \
  --out-dir  data/eval/<checkpoint>/stage2_bare_pro \
  --model deepseek-v4-pro --judge --judge-model deepseek-v4-flash \
  --concurrency 1 --skip-existing --progress
```

### Stage 3 — Flash + full harness, on the Stage-2 double-failures

Standing directive: **massively increase retrieval, with per-paper Flash extraction** (`--paper-extractor`)
so volume doesn't dilute the main context. Defaults are the honest-benchmark config (eval_mode on →
never reads the source paper, ADR-030; gates on; knowledge-pack on; adaptive rounds on).

```bash
clinical-harness benchmark retrieval-guided-eval \
  --manifest data/eval/<checkpoint>/stage3_harness.jsonl \
  --out-dir  data/eval/<checkpoint>/stage3_flash_harness \
  --model deepseek-v4-flash --judge --judge-model deepseek-v4-flash \
  --paper-extractor --use-full-text \
  --max-queries 4 --articles-per-query 6 --max-rounds 3 --min-rounds 1 \
  --concurrency 3 --skip-existing --progress
```

Long-running. Launch in the background and poll the `.log`; the model client handles 429/5xx backoff
and a shared NCBI rate-lock, so concurrency is safe within the account ceiling.

> **⚠️ The subset-overwrite trap.** A `--case-id`/subset re-run **overwrites** the aggregate
> `retrieval_guided_results.jsonl` with only the subset rows. To retry one failed case *and* keep the
> aggregate, re-run the **full manifest with `--skip-existing`** — it reuses existing response files
> and only hits the missing case. (Both eval commands share this behavior.)

---

## 3. Analyze the outputs

Each stage writes `retrieval_guided_results.jsonl` (one row per case; shared schema across all three
stages so they're directly comparable) plus per-case prompts/responses and, for Stage 3, retrieval
artifacts + case reports.

**Per-row fields that matter:** `score` (`pass`/`fail`/`not_run`), `ranked_differential` (top-5),
`gold_rank` (1–5 if the gold is in the top-5, else `None` — monotonic, conjunction-aware),
`expected_diagnosis`/gold, `judge_rationale`, `evidence_count`.

**Scoring:** models emit a **top-5 ranked differential**; report **pass@1 … pass@5** (`summarize_*`
emits these). End-to-end = Stage-1 passes + Stage-2 passes + Stage-3 harness passes, over the full N.

**The interpretive lens (the project thesis):**
- The bottleneck is usually **SELECTION, not retrieval** — the right entity is in the evidence/top-5
  but mis-ranked (`gold_rank` 2–5). Check `gold_rank` distribution before blaming retrieval.
- Triage every residual (pass@5-fail) case into one of: **IR failure** (right entity never retrieved —
  low `evidence_count`, niche mechanism), **reasoning failure** (entity present/retrievable but
  anchored away or a stated discriminator dropped), or **broken case** (gold not fairly determinable
  from the prompt → kick back to NeurologyBM `validate-cases`, don't "fix" by relaxing scoring).
  See [wave89_checkpoint_triage_20260616.md](wave89_checkpoint_triage_20260616.md) for a worked example.
- **Measurement wall:** at small N (~30) with ±2–3-case judge variance, single-fix deltas (+1/+2) are
  noise. Do **not** trust a one-run improvement. Validate headline comparisons with **multi-seed**
  (3–5 runs, mean±range) or larger N before claiming a lift.

**Inspect a single run visually** with the Agent-Trace Viewer (problem rep → queries → PubMed/PMC
calls → evidence → synthesis → prompt packet → model response → judge): see
[../viewer/README.md](../viewer/README.md). Launch backend (`cd viewer/backend && python -m
clinical_viewer`) + frontend (`cd viewer/frontend && npm run dev`, open http://localhost:5173). Pass
`--viewer-url http://127.0.0.1:8000` to an eval to **live-stream** events into the UI; it's purely
observational — if the UI is down the run still writes the same JSONL ledgers for later replay.

---

## 4. Think of changes — the rules for improvements

- **No difficulty gate.** One system robust across all cases. An improvement must be **GENERAL**
  (bidirectional/Bayesian — helps without hurting easy cases) or **NICHE** (inert when irrelevant).
  If neither fits, the miss is an IR failure or a reasoning failure — fix that, don't special-case.
- **Always check the control set** of easy cases (ADR-004): "helps the hard cases" and "doesn't break
  the easy ones" are separate claims. Biased gates have regressed easy cases before (e.g.
  ALS→Aceruloplasminemia).
- **Gates are bidirectional, base-rates-first** (`UNIVERSAL_FINALIZATION_GATES` in
  `retrieval_guided_eval.py`): base rates override de-anchoring/specificity, not the reverse.
- **Retrieval volume hurts *without* extraction** (dilution → hedging). Increase breadth only with
  per-paper extraction on. Self-prompt reasoning levers (commit / self-consistency / re-rank) tested
  **flat** — don't re-litigate without multi-seed evidence.
- **Broken-case fixes belong in NeurologyBM**, not the scorer. If a discriminator needed for the gold
  is in the source but missing from the prompt, the case is broken → `validate-cases --mend` adds the
  withheld result (**gold preserved**). Never relax the gold to make a case pass.
- **Reasoning-token budget (ADR-017):** reasoning models spend completion tokens on hidden reasoning →
  empty `content` if `max_tokens` too low. Keep ≥8192 (12000 for the final answer). If you see empty
  outputs with `finish_reason=length`, raise `max_tokens` in that code path.

Record any significant change as an **ADR** in [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) and durable
lessons in [journal.md](../journal.md). A decision recorded only in a commit is invisible to the next
agent.

---

## 5. Validate before you finish

```bash
PYTHONPATH=src python3.11 -m unittest discover -s tests     # harness (134 tests; use 3.11, not system 3.8)
cd ../NeurologyBM && PYTHONPATH=src python3.11 -m pytest tests/ -q   # benchmark generator
```

## Quick reference — file/key locations

| What | Where |
|---|---|
| Secrets | `ClinicalHarness/.env.local` (gitignored) |
| Eval outputs | `ClinicalHarness/data/eval/<checkpoint>/stageN_*/retrieval_guided_results.jsonl` |
| Harness core | `src/clinical_harness/retrieval_guided_eval.py`, `baseline_eval.py`, `paper_analysis.py` |
| Viewer (UI) | `ClinicalHarness/viewer/` (backend `clinical_viewer`, frontend Vite/React) |
| New batches | `NeurologyBM/data/pmc/processed/case_validation/<batch>/*_strict_*.jsonl` |
| Batch validator | `NeurologyBM/src/neurologybm/case_validation.py` + `neurologybm validate-cases` |
| Decisions trail | `docs/DESIGN_DECISIONS.md` (ADRs), `journal.md` (lessons) |
