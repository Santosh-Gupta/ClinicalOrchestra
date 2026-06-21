# ClinicalHarness Viewer — Architecture & Roadmap

This document is the design contract and the staged plan. It is written so a
different agent/LLM can take ownership without re-deriving the decisions. Read
the repo-level [`AGENTS.md`](../AGENTS.md) first — the viewer is a subproject and
follows the same "don't silently revert a documented decision" rule. For a
review checklist, also read [`REVIEW_HANDOFF.md`](REVIEW_HANDOFF.md).

---

## 1. Goal

Give a human (or a reviewing agent) a **Codex / Claude-Code-style window into a
diagnosis run**: watch the harness form hypotheses, plan queries, retrieve
literature, synthesize discriminators, commit to a diagnosis, and get judged —
as a live, inspectable, replayable trace. Diagnostic reasoning is the product;
this is the instrument that makes it observable.

Design tenets:

- **One event schema, many sources.** Replay-from-disk and live-from-process
  both normalize to the same `Event`. The UI never knows which it's watching.
- **The harness stays pure.** `clinical_harness` is stdlib-only by deliberate
  decision. The viewer is a separate package with its own deps; live mode will
  add only a plain optional callback to the harness, never a hard dependency.
- **Graceful degradation.** A results-only run still produces a coherent (if
  sparse) trace. Missing artifacts never break the view.
- **The contract is the schema.** `backend/clinical_viewer/events.py` and
  `frontend/src/types.ts` are the seam. Extend by adding an `EventType` + a
  payload shape + a renderer — never by special-casing a stage in three places.
- **Public and advanced editions may diverge deliberately.** The public demo is
  optimized for visitors starting one case and watching it unfold; the advanced
  UI is optimized for local run/case review. Keep the edition split explicit in
  `frontend/src/edition.ts` and `App.tsx`, rather than relying on a pile of
  backend capability flags.

## 2. The data the harness leaves behind

Per rich case (from `benchmark retrieval-guided-eval`), in `runs/<run>/`:

| Artifact | Contents |
| --- | --- |
| `<case>.queries.json` | generated queries, each with `round_index`, `intent`, `generated_by`, `source` |
| `<case>.evidence.json` | retrieved records: `query_id`, rank, pmid/pmcid/doi, title, journal, abstract/full-text snippets, source scope, relevance, exclusion flags |
| `<case>.synthesis.json` | per synthesis-round: `useful_discriminators`, `more_retrieval_needed`, `differential_resolved`, notes |
| `<case>.retrieval_response.json` | final model `content`: `problem_representation`, `final_diagnosis`, `etiology`, `discriminator_summary`, `key_papers`, `confidence` |
| `<case>.report.md` | human-readable report |
| `retrieval_guided_results.jsonl` | one row per case: judge `score`, `judge_match_type`, `judge_rationale`, `expected_diagnosis`, `model_final_diagnosis` |

The simpler `case run` path additionally writes an append-only `events.jsonl`
ledger (`ledger.py`) — the closest existing thing to a native event stream and
the model for the live emitter. The viewer discovers these root-level ledgers
and replays their case loading, problem representation, generated queries,
PubMed executions, evidence recording/exclusion, and structured answer events.

**Known gap:** older `evidence.json` records do not reliably carry round
attribution, so the replay adapter attaches evidence cards to the first
retrieval round while preserving `query_id` when present. Native/live event
ledgers know the round at emit time. Until then, treat per-round evidence
grouping in replay as approximate.

## 3. The unified Event schema (the contract)

See `events.py` for the authoritative definition. An `Event` is:

```
id, seq, ts?, run_id, case_id, round?, type, actor, title, summary?, status, payload
```

- **`type`** ∈ `EventType` — the stage (`query_generated`, `evidence_retrieved`,
  `synthesis`, `answer`, `judge`, …).
- **`actor`** — conceptual sub-agent (`planner`, `retriever`, `synthesizer`,
  `diagnostician`, `judge`, `runner`, `system`); drives icon/colour.
- **`status`** — `ok`/`running`/`warn`/`error`/`pass`/`fail`/`info`; drives badges.
- **`payload`** — free-form, type-specific. Renderers read it leniently so old
  events survive schema growth.

## 4. Backend

FastAPI app (`app.py`) over a thin file layer (`runs.py`) and the replay adapter
(`adapters/replay.py`). All run/case ids are validated against path traversal.
The SSE endpoint currently *replays* a finished timeline with a configurable
delay — that is what gives replay mode its "unfolding" feel — and is the same
endpoint live mode will serve real-time events from.

## 5. Frontend

Vite + React + TS. `EventCard.tsx` switches on `type` to render bodies (a
problem-representation paragraph, a query's intent, a paper with its PubMed
link, a synthesis's discriminators, the final answer with key papers, the
judge's rationale). `types.ts` mirrors `events.py` by hand; when the schema
settles, generate it from `/openapi.json`.

There are two frontend editions:

- **Advanced** is the local reviewer UI: three-pane shell (`runs · cases ·
  trace`), collapsible side panels, artifact chips, filters, save/export, and
  full New Case controls for dry-run/retrieval/model/judge when backend env vars
  allow them.
- **Public** is compiled by Docker with `VITE_VIEWER_EDITION=public`: no left
  runs/cases panels, a prominent main-panel **New Case** entry point, a minimal
  case form, and a split trace body. Retrieval events render in the left lane;
  everything else renders in the right reasoning lane. A top working banner and
  a bottom-of-reasoning-lane working banner stay visible until
  `case_completed`.

Public new-case submissions hide title, aliases, dry-run, retrieval, model, and
judge controls. They request retrieval and model execution, but the backend
still enforces `CLINICAL_VIEWER_ALLOW_RETRIEVAL` and
`CLINICAL_VIEWER_ALLOW_MODEL_RUNS`. If the user does not supply a correct
answer, the harness treats the case as unscored and suppresses judge events
instead of comparing against `"unknown"`.

For real viewer-submitted model runs, the backend defaults to a showcase trace
profile controlled by `CLINICAL_VIEWER_SHOWCASE_TRACE=true`: model evidence
distillation, a minimum of three retrieval rounds capped by the submitted
`max_rounds`, PMC full-text enrichment for top PMCID hits, and per-paper
screening before final answer. This is intentionally about demonstration and
observability; benchmark-optimal configs can remain leaner. The experimental
multi-angle ensemble remains opt-in via `CLINICAL_VIEWER_SHOWCASE_ENSEMBLE=true`
because it adds many calls and is not an accuracy default. The viewer filters
showcase config kwargs against the installed `HarnessConfig` fields so a public
deploy does not fail when local experimental harness fields are absent.

## 6. Roadmap — simple → advanced

### Stage 0 — MVP (done)
Replay viewer: run/case browser, reconstructed timelines, SSE "replay",
per-type cards, judge verdicts. Works against the existing 60+ runs.

### Stage 0.5 — Public hosted demo (done)
- Docker builds the public frontend edition and serves it with the FastAPI API
  from one web service.
- Render deployment works with `/api/health` as the health check and optional
  `/data` disk persistence for user-generated runs/traces.
- Public UI starts from **New Case**, removes the run/case browser, splits
  retrieval and reasoning into separate lanes, and keeps dynamic working
  indicators visible during long model calls.
- Public model runs use a richer showcase trace profile: evidence distillation,
  forced bounded minimum rounds, PMC full text, and paper screening.
- Public cases without a correct answer are unscored: the final answer remains
  visible and saveable, but no fake judge failure is emitted.

### Stage 1 — Live mode (done for MVP)
1. **Done:** `retrieval_guided_eval.run_retrieval_guided_manifest_eval` accepts
   an optional `emitter: Callable[[dict], None] | None`. The harness core still
   has zero viewer/FastAPI dependency; it emits plain Event-shaped dictionaries
   at the case, round, query, retrieval, synthesis, answer, judge, and completion
   boundaries.
2. **Done:** each emitted event is mirrored to `<run>/<case>.events.jsonl`, and
   the replay adapter prefers that native event ledger when present.
3. **Done:** the FastAPI backend exposes `POST /api/live/events`, publishes to
   `adapters/live.bus`, and the existing SSE endpoint subscribes to active
   in-flight cases before falling back to disk replay.
4. **Done:** the frontend discovers live-only cases, badges active/growing
   traces, auto-refreshes active runs, and subscribes to selected live cases so
   incoming events merge into the visible trace.
5. **Done:** timeline responses label whether the trace source is `native`,
   `live`, or `replay`, so reviewers know whether they are seeing the full event
   ledger or an older artifact reconstruction.

### Stage 2 — Richer reasoning trace
- **Done baseline:** capture and render the prompts and raw visible model
  responses per stage (the `model_call` event now covers optional subagents;
  final-answer calls use `model_response`) — token counts and latency when
  returned by the provider.
- **Done baseline:** first-class **retrieval tool-call events** capture PubMed
  search parameters, query translation, returned PMIDs, PMC full-text fetches,
  output evidence IDs, and article provenance.
- Next: extend tool-call semantics beyond PubMed/PMC retrieval to every external
  lookup and future interactive control-plane action.
- Show the **hypothesis set evolving** across rounds (differential diff view):
  what each new paper added, confirmed, or refuted.
- Surface **retrieval-guard violations** (`diagnostic_harness.RetrievalGuardViolation`)
  inline — the eval-mode source-exclusion story is a first-class safety signal.

### Stage 3 — Multi-agent & comparison
- Render the **multi-agent ensemble** (independent angle-agents + consolidating
  coordinator, per `docs/multi_agent_design_20260614.md`) as parallel swimlanes.
- **Run-vs-run diff**: pick two runs (or two configs) and compare the same case
  side by side — where did the trajectories diverge, and at which event.
- Aggregate **dashboards**: pass-rate by preset, failure taxonomy
  (`wrong_entity`, anchor risks), high-variance cases across repeated runs.

### Stage 4 — Interactive & control plane
- **Launch / re-run** a case from the UI (POST to a controlled runner) and watch
  it live.
- **Annotations**: mark an event as the point of failure; export a case study to
  `docs/` (feeding the existing failure-deepdive workflow).
- Auth + a hosted deployment story (the `docs/` failure trackers suggest this
  will be shared across reviewers).

## 7. Constraints & gotchas for the next agent

- **Never disable source exclusion** to make a trace prettier (ADR-030). If you
  visualize retrieval, visualize the exclusions too.
- **Node 18+** is required for the frontend; this machine had Node 14 + broken
  Homebrew, so Node 20 is vendored under `viewer/.toolchain/` (git-ignored).
- Keep `events.py` ↔ `types.ts` in sync until codegen exists.
- The harness is the source of truth for *what* happens; the viewer must not
  invent semantics the harness doesn't have. If a trace needs data the harness
  doesn't emit, add it to the harness (with an ADR), don't fake it in the adapter.
- Be careful with public-demo scoring semantics: a missing correct answer means
  "not benchmarked", not "expected diagnosis is unknown".
