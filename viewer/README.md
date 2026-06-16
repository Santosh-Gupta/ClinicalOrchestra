# ClinicalHarness Viewer

A Codex / Claude-Code-style UI for **watching a diagnosis run unfold** — the
clinical reasoning, query planning, literature retrieval, evidence synthesis,
final diagnosis, and the judge's verdict — as a streaming agent trace.

![ClinicalHarness Viewer trace](assets/clinical-viewer-trace.jpg)

> **Status: MVP plus native event ledgers.** It reconstructs timelines from the
> artifacts a finished run leaves in `runs/<run>/` and can "replay" them
> event-by-event. `retrieval_guided_eval` now also writes
> `<case>.events.jsonl` and accepts an optional `emitter` callback. The backend
> can ingest live events and stream active cases over SSE; the UI discovers
> active/live-only cases, watches selected live traces automatically, and labels
> every timeline as native, live, or replay reconstruction.

```
viewer/
├── ARCHITECTURE.md         # the full design + advanced roadmap + handoff
├── backend/                # FastAPI: reads runs/, serves the unified Event stream
│   └── clinical_viewer/
│       ├── events.py       # ★ the unified Event schema (the contract)
│       ├── runs.py         # discover runs & cases on disk
│       ├── app.py          # HTTP + SSE routes
│       └── adapters/
│           ├── replay.py   # ★ artifacts → events (the MVP data path)
│           └── live.py     # event-bus stub for future live streaming
└── frontend/               # Vite + React + TypeScript
    └── src/
        ├── types.ts        # mirror of events.py — keep in sync
        ├── api.ts          # typed client + SSE subscription
        ├── App.tsx         # 3-pane shell: runs · cases · trace
        └── components/EventCard.tsx  # per-event-type renderers
```

## What it shows

Three panes, like an agent-trace IDE:

1. **Runs** — every directory under `runs/`, with pass/fail tallies.
   Runs with native event ledgers show trace counts; active live cases and
   growing incomplete traces are badged.
2. **Cases** — each case in a run, with its judged score, expected diagnosis,
   native event count, and live/growing status.
3. **Trace** — the reconstructed timeline: problem representation → per-round
   query planning → retrieved papers → evidence synthesis/discriminators →
   final prompt/injected packet → visible model API response → final diagnosis
   → judge verdict. Click a card to expand it; hit **Replay** to stream the
   events in one at a time. PubMed retrieval and PMC full-text fetches appear
   as first-class `tool_call` cards with query parameters, translated PubMed
   query, returned PMIDs/PMCIDs, output evidence IDs, and returned article
   summaries. Use the trace filters to isolate model calls, retrieval,
   reasoning, judge events, warnings/errors, or search across titles,
   summaries, prompts, and payloads. The trace header summarizes event count,
   model-call count, model-response count, tool-call count, returned total,
   prompt, completion, and reasoning tokens, retrieved evidence count,
   warnings/errors, and the latest event type. It also labels the trace source:
   **native trace** for `<case>.events.jsonl`, **live trace** for active ingest,
   or **replay trace** for older artifact reconstruction.

The expanded prompt/model cards expose the raw final prompt, parsed case packet,
finalization gates, blocked retrieval shortcuts, injected evidence synthesis,
retrieved evidence, screened evidence notes, model name, latency, token usage
when returned by the provider (including cache hit/miss and reasoning-token
details where available), parsed answer JSON, raw model text on parse failures,
and the raw API response. It does not invent hidden chain-of-thought; only
returned model content and structured harness reasoning artifacts are shown.

Evidence cards expose retrieval provenance where available: evidence id, source
query id, rank, source API/scope, relevance score, PMID/PMCID/DOI, publication
types, exclusion reason, abstract snippet, and full-text snippet.

Every expanded event card also includes a collapsed **Raw event JSON** drawer so
reviewers can inspect any payload fields that do not yet have a specialized UI.
When disk artifacts exist, the trace header shows file chips for the raw event
ledger, queries, evidence, synthesis, final prompt, model response, and report;
each chip opens an in-app artifact viewer with the raw content and a direct link
to the corresponding allowlisted backend endpoint. For deterministic `case run`
outputs, the viewer also opens the root ledger artifacts: `events.jsonl`,
`queries.jsonl`, `evidence.jsonl`, `answer.json`, and `manifest.json`.

New live traces also emit `tool_call` cards for PubMed searches, PMC full-text
fetches, and `model_call` cards for each final-answer sample and for optional
subagents: evidence distillation, paper screening, initial clinical assessment, differential
reranking, judged self-consistency clustering, and judge-equivalence calls. Each
card includes the prompt, visible response, parsed JSON when available, latency,
token usage when returned, and raw API payload.

New retrieval-guided runs write `*.events.jsonl`, which the viewer uses as the
authoritative trace. Older rich runs (those produced by
`benchmark retrieval-guided-eval`, which write `*.queries.json`,
`*.evidence.json`, `*.synthesis.json`, `*.retrieval_response.json`) are still
reconstructed from artifacts. Simpler deterministic `case run` outputs are
reconstructed from their root `events.jsonl` ledger. Results-only runs degrade
gracefully to the case → rounds → judge skeleton.

## UI guide

The viewer is organized around a reviewer workflow:

1. **Pick a run.** The left rail lists discovered run directories, case counts,
   pass/fail tallies, live traces, and native event-ledger counts.
2. **Pick a case.** The cases panel shows the expected diagnosis, judge status,
   live/growing state, and event count when a native trace exists.
3. **Read the trace.** The main pane shows the diagnosis attempt as an ordered
   event stream. Cards are collapsed by default with high-signal summaries; open
   a card to inspect details and raw event JSON.

Useful controls:

- **Replay** streams the current timeline event-by-event for the unfolding
  agent-trace effect.
- **Show all** restores the full trace after replay or filtering.
- **Hide** in the Runs or Cases panel collapses that side panel so the trace can
  use more of the window. **Show Runs** and **Show Cases** restore hidden panels
  from the trace header.
- **Trace filters** isolate model calls, retrieval events, reasoning events,
  judge events, or errors. The search box matches event titles, summaries,
  prompts, and payload text.
- **Artifact chips** open raw run files in-app: event ledgers, queries, evidence,
  synthesis, final prompt, model response, reports, and deterministic-run
  ledgers where present.

How to read the cards:

- **Problem representation** shows the compact clinical framing the harness used
  before retrieval.
- **Query generated** cards show the exact literature-search strings and intent.
- **Tool call** cards show PubMed/PMC calls, returned identifiers, output
  evidence IDs, and article payloads.
- **Evidence** cards show provenance, relevance, source scope, exclusion status,
  abstract snippets, and full-text snippets when available.
- **Synthesis** cards show discriminators, uncertainty, and whether more
  retrieval was requested.
- **Prompt/model cards** show the final injected prompt packet, visible model
  response, parsed JSON, token usage, latency, and raw API payloads when saved.
- **Answer/judge** cards show the final diagnosis and scoring verdict.

The viewer deliberately shows only returned model content and structured harness
reasoning artifacts. It does not fabricate hidden chain-of-thought.

## Run it

The harness package itself is stdlib-only by design; the viewer keeps its own
dependencies isolated so it never pollutes that.

### Prerequisites

- Python 3.11+
- Node 18+ (Vite 5 requirement). **Note:** this machine shipped with Node 14 and
  a broken Homebrew, so a known-good Node 20 was vendored to
  `viewer/.toolchain/` (git-ignored). Use it via:
  `export PATH="$(pwd)/viewer/.toolchain/node-v20.18.1-darwin-arm64/bin:$PATH"`
  — or install a system Node 18+ and ignore the toolchain dir.

### Backend (terminal 1)

```bash
cd viewer/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
python -m clinical_viewer            # serves http://127.0.0.1:8000
# point at a different runs dir:  CLINICAL_HARNESS_RUNS=/path/to/runs python -m clinical_viewer
```

### Frontend (terminal 2)

```bash
cd viewer/frontend
npm install
npm run dev                          # http://localhost:5173 (proxies /api → :8000)
```

Open http://localhost:5173.

## API surface

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/api/health` | service + runs-dir status |
| GET | `/api/runs` | `RunSummary[]` |
| GET | `/api/runs/{run}/cases` | `CaseSummary[]` |
| GET | `/api/runs/{run}/cases/{case}/timeline` | `CaseTimeline` |
| GET | `/api/runs/{run}/cases/{case}/stream?delay_ms=` | SSE `Event` stream |
| GET | `/api/runs/{run}/cases/{case}/artifacts/{name}` | raw artifact text |
| POST | `/api/live/events` | publish one live `Event` |
| POST | `/api/live/close` | close a live stream without a terminal event |

The OpenAPI spec is at `/docs` (Swagger) and `/openapi.json`.

## Live Event Ingest

The harness stays stdlib-only. To watch a CLI run live, pass an emitter that
POSTs each Event-shaped dictionary to the viewer backend:

```python
import json
import urllib.request


def viewer_emitter(event: dict) -> None:
    request = urllib.request.Request(
        "http://127.0.0.1:8000/api/live/events",
        data=json.dumps(event).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(request, timeout=2).close()
```

Then call `run_retrieval_guided_manifest_eval(..., emitter=viewer_emitter)`.
The existing `/stream` endpoint will use live events while the case is active
and fall back to disk replay afterward.

From the CLI, pass the viewer backend URL directly:

```bash
clinical-harness benchmark retrieval-guided-eval \
  --manifest runs/your_manifest.jsonl \
  --out-dir runs/live_test \
  --case-id your_case_id \
  --viewer-url http://127.0.0.1:8000
```

The viewer is observational. If the backend is unavailable, the run continues
and writes the normal artifacts plus `<case>.events.jsonl`.

## For the next agent

Read [ARCHITECTURE.md](ARCHITECTURE.md). The highest-value next step is no
longer basic live discovery; it is richer trace semantics and control-plane
work. Useful directions include first-class tool-call events beyond PubMed
search, side-by-side comparison of multiple runs on the same case, and
interactive controls for pausing or steering retrieval. The current run/case
lists already badge live/growing/native-event traces and auto-refresh while a
selected run has active or incomplete traces. Live events posted to
`/api/live/events` are discoverable even before a run directory exists on disk;
once the harness writes `<case>.events.jsonl`, the same case is replayable from
disk as a native trace.
