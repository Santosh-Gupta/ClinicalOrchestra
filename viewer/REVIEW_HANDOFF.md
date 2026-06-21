# Viewer Review Handoff

This note is for an external LLM/code reviewer taking a fresh look at the
ClinicalHarness viewer and public demo.

## Current state

- The viewer is an isolated subproject under `viewer/`.
- The backend is FastAPI (`viewer/backend`) and serves both `/api/*` and the
  built React app in production.
- The frontend is Vite + React + TypeScript (`viewer/frontend`).
- Docker builds the frontend with `VITE_VIEWER_EDITION=public`; local dev
  defaults to the advanced edition unless `VITE_VIEWER_EDITION=public` is set.
- The public Render demo uses one web service and `/api/health` for health
  checks.

## Public edition

The public edition is intentionally not just the advanced UI with a few controls
hidden. It has its own demo-oriented workflow:

- no left Runs or Cases panels;
- prominent main-panel **New Case** button;
- new-case form accepts case text and optional correct answer only;
- title, aliases, dry-run, retrieval, model, and judge controls are hidden;
- PubMed retrieval is always requested by the public form, but the backend still
  decides whether retrieval is allowed from environment variables;
- real public model runs default to a richer showcase trace profile: evidence
  distillation, a bounded minimum number of retrieval rounds, PMC full-text
  enrichment, and per-paper screening;
- trace body is split into Retrieval and Reasoning lanes;
- working indicators remain visible until `case_completed`, including during
  long model calls after final prompt assembly.

If no correct answer is provided, the run is unscored. The viewer should not
emit a judge card or display a failure against `"unknown"`.

## Advanced edition

The advanced edition keeps the original reviewer tooling:

- Runs panel;
- Cases panel;
- full trace panel;
- collapsible side panels;
- trace filters and search;
- artifact chips;
- Save and Export MD;
- advanced New Case controls for dry run, retrieval, model, and judge when
  backend env vars allow them.

## Backend behavior to review

- `clinical_harness.retrieval_guided_eval` emits native Event-shaped trace
  records and writes `<case>.events.jsonl`.
- `viewer/backend/clinical_viewer/adapters/replay.py` prefers native event
  ledgers and falls back to reconstructed timelines from older artifacts.
- `viewer/backend/clinical_viewer/app.py` exposes:
  - `/api/health`
  - `/api/runs`
  - `/api/runs/{run}/cases`
  - `/api/runs/{run}/cases/{case}/timeline`
  - `/api/runs/{run}/cases/{case}/stream`
  - `/api/runs/{run}/cases/{case}/save`
  - `/api/new-case`
  - `/api/live/events`
- User-generated cases and saved traces live under
  `viewer/user_generated/` locally or `CLINICAL_VIEWER_USER_GENERATED` in
  hosted deployments. Public/demo deployments clean old generated run, case,
  and trace directories after `CLINICAL_VIEWER_USER_GENERATED_TTL_SECONDS`
  seconds by default.

## Environment knobs

- `CLINICAL_VIEWER_ALLOW_RETRIEVAL=true` allows public submissions to call
  PubMed/PMC retrieval.
- `CLINICAL_VIEWER_ALLOW_MODEL_RUNS=true` allows public submissions to call the
  model.
- `NCBI_EMAIL` and optional `NCBI_API_KEY` configure NCBI E-Utilities.
- `DEEPSEEK_API_KEY`, optional `DEEPSEEK_BASE_URL`, and optional
  `DEEPSEEK_MODEL` configure DeepSeek.
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` are OpenAI-compatible
  fallbacks.
- `CLINICAL_VIEWER_SHOWCASE_TRACE=true` enables the richer public-demo trace
  profile for real viewer-submitted model runs. It is on by default.
- `CLINICAL_VIEWER_SHOWCASE_MIN_ROUNDS=3` controls the minimum retrieval rounds,
  capped by the submitted `max_rounds`.
- `CLINICAL_VIEWER_SHOWCASE_PAPER_CONCURRENCY=4` bounds per-paper screening
  concurrency.
- `CLINICAL_VIEWER_SHOWCASE_ENSEMBLE=false` leaves the multi-angle ensemble
  opt-in because it adds several model calls and is not an accuracy default.
  It is ignored unless the installed harness version supports `use_ensemble`.
- `CLINICAL_VIEWER_USER_GENERATED_TTL_SECONDS=1800` bounds public-demo disk
  usage by deleting old generated runs/cases/traces. Use `0` only for private
  installs that should retain artifacts.

## Suggested review focus

1. Public edition UX correctness: no stale advanced controls, no title field,
   no answer-alias box, clear New Case entry point, and trace lanes split
   correctly.
2. Long-running state: working indicators should stay visible until
   `case_completed`.
3. Showcase trace depth: real public model runs should pass
   `distill_evidence=True`, `use_full_text=True`, `use_paper_extractor=True`,
   and a bounded minimum round count to the harness.
4. Scoring semantics: no judge event for public cases without a correct answer.
5. Data safety: user-generated artifacts should remain under
   `viewer/user_generated/` or configured hosted storage and should not be
   committed.
6. Event schema compatibility: `events.py`, `types.ts`, replay adapter, and
   `EventCard.tsx` should remain lenient for older traces.
7. Deployment: Docker public build, Render health check, and environment
   variables should match the docs.

## Useful checks

```bash
cd viewer/backend
python -m pytest tests/test_replay.py tests/test_live.py
```

```bash
cd viewer/frontend
VITE_VIEWER_EDITION=public npm run build
npm run build
```

Use the vendored Node 20 if the system Node is too old:

```bash
export PATH="$(pwd)/../.toolchain/node-v20.18.1-darwin-arm64/bin:$PATH"
```
