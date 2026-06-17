"""FastAPI app: read-only API over harness runs, plus a streaming endpoint.

Routes
------
GET  /api/health
GET  /api/runs                                   -> [RunSummary]
GET  /api/runs/{run_id}/cases                    -> [CaseSummary]
GET  /api/runs/{run_id}/cases/{case_id}/timeline -> CaseTimeline
GET  /api/runs/{run_id}/cases/{case_id}/stream   -> text/event-stream (SSE)
GET  /api/runs/{run_id}/cases/{case_id}/artifacts/{name} -> raw artifact text
POST /api/runs/{run_id}/cases/{case_id}/save     -> persist trace JSON + Markdown
POST /api/live/events                            -> publish one live Event
POST /api/live/close                             -> close one live stream

The stream endpoint prefers active live events and falls back to replaying a
finished timeline event-by-event with a small delay.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import runs as runs_mod
from .adapters.live import bus
from .adapters.replay import ARTIFACTS, LEDGER_ARTIFACTS, build_case_timeline
from .config import cors_origins, runs_dir, user_generated_dir
from .events import CaseSummary, CaseTimeline, Event, RunSummary

app = FastAPI(title="ClinicalHarness Viewer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Artifacts the UI may fetch raw (e.g. the retrieval prompt, the report).
_RAW_ARTIFACTS = {name: suffix for name, _label, suffix in ARTIFACTS}
_RAW_LEDGER_ARTIFACTS = {name: filename for name, _label, filename in LEDGER_ARTIFACTS}


@app.get("/api/health")
def health() -> dict:
    base = runs_dir()
    return {"status": "ok", "runs_dir": str(base), "runs_dir_exists": base.is_dir()}


@app.get("/api/runs", response_model=list[RunSummary])
def get_runs() -> list[RunSummary]:
    return runs_mod.list_runs()


@app.get("/api/runs/{run_id}/cases", response_model=list[CaseSummary])
def get_cases(run_id: str) -> list[CaseSummary]:
    try:
        return runs_mod.list_cases(run_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/cases/{case_id}/timeline", response_model=CaseTimeline)
def get_timeline(run_id: str, case_id: str) -> CaseTimeline:
    _guard_case_id(case_id)
    live = runs_mod.live_timeline(run_id, case_id)
    if live is not None:
        return live
    run_dir = _resolve(run_id)
    return build_case_timeline(run_dir, run_id, case_id)


@app.get("/api/runs/{run_id}/cases/{case_id}/artifacts/{name}")
def get_artifact(run_id: str, case_id: str, name: str) -> dict:
    run_dir = _resolve(run_id)
    _guard_case_id(case_id)
    suffix = _RAW_ARTIFACTS.get(name)
    ledger_filename = _RAW_LEDGER_ARTIFACTS.get(name)
    if not suffix and not ledger_filename:
        raise HTTPException(status_code=404, detail=f"unknown artifact: {name}")
    path = run_dir / ledger_filename if ledger_filename else run_dir / f"{case_id}{suffix}"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"artifact not found: {path.name}")
    return {"name": name, "filename": path.name, "content": path.read_text(encoding="utf-8")}


@app.post("/api/runs/{run_id}/cases/{case_id}/save")
def save_trace(run_id: str, case_id: str) -> dict:
    """Persist a trace bundle under viewer/user_generated/traces/."""

    _guard_run_id(run_id)
    _guard_case_id(case_id)
    timeline = get_timeline(run_id, case_id)
    saved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    stem = f"{_safe_filename(run_id)}__{_safe_filename(case_id)}__{_safe_filename(saved_at)}"
    out_dir = user_generated_dir() / "traces" / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": 1,
        "saved_at": saved_at,
        "kind": "clinical_harness_trace_export",
        "run_id": timeline.run_id,
        "case_id": timeline.case_id,
        "title": timeline.title,
        "trace_source": timeline.trace_source,
        "trace_notice": timeline.trace_notice,
        "correct_answer": timeline.expected_diagnosis,
        "expected_diagnosis": timeline.expected_diagnosis,
        "model_diagnosis": timeline.model_diagnosis,
        "score": timeline.score,
        "score_method": timeline.score_method,
        "artifacts": [artifact.model_dump(mode="json") for artifact in timeline.artifacts],
        "events": [event.model_dump(mode="json") for event in timeline.events],
    }
    json_path = out_dir / "trace.json"
    md_path = out_dir / "trace.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_trace_markdown(timeline, saved_at), encoding="utf-8")

    return {
        "status": "ok",
        "saved_at": saved_at,
        "directory": str(out_dir),
        "files": {"json": str(json_path), "markdown": str(md_path)},
        "event_count": len(timeline.events),
        "correct_answer": timeline.expected_diagnosis,
        "model_diagnosis": timeline.model_diagnosis,
        "score": timeline.score,
    }


@app.get("/api/runs/{run_id}/cases/{case_id}/stream")
async def stream_timeline(
    run_id: str,
    case_id: str,
    delay_ms: int = Query(default=350, ge=0, le=5000),
) -> StreamingResponse:
    """Server-Sent Events: live stream when active, otherwise replay from disk."""

    _guard_run_id(run_id)
    _guard_case_id(case_id)
    if bus.is_active(run_id, case_id):
        queue = bus.subscribe(run_id, case_id)

        async def live_event_gen():
            try:
                while True:
                    event = await queue.get()
                    if event is None:
                        break
                    yield f"event: trace\ndata: {event.model_dump_json()}\n\n"
            finally:
                bus.unsubscribe(run_id, case_id, queue)
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(
            live_event_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    run_dir = _resolve(run_id)
    timeline = build_case_timeline(run_dir, run_id, case_id)

    async def event_gen():
        for event in timeline.events:
            yield f"event: trace\ndata: {event.model_dump_json()}\n\n"
            if delay_ms:
                await asyncio.sleep(delay_ms / 1000)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/live/events")
async def publish_live_event(event: Event) -> dict:
    """Publish one live event to in-process SSE subscribers."""

    _guard_run_id(event.run_id)
    _guard_case_id(event.case_id)
    await bus.publish(event)
    return {"status": "ok", "run_id": event.run_id, "case_id": event.case_id, "seq": event.seq}


@app.post("/api/live/close")
async def close_live_stream(payload: dict[str, str]) -> dict:
    """Explicitly close a live stream when a producer exits without case_completed."""

    run_id = payload.get("run_id", "")
    case_id = payload.get("case_id", "")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    _guard_run_id(run_id)
    _guard_case_id(case_id)
    await bus.close(run_id, case_id)
    return {"status": "ok", "run_id": run_id, "case_id": case_id}


def _resolve(run_id: str) -> Path:
    try:
        return runs_mod.resolve_case_dir(run_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _guard_case_id(case_id: str) -> None:
    if "/" in case_id or "\\" in case_id or ".." in case_id:
        raise HTTPException(status_code=400, detail="invalid case id")


def _guard_run_id(run_id: str) -> None:
    if "/" in run_id or "\\" in run_id or run_id in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="invalid run id")


def _safe_filename(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return clean or "trace"


def _trace_markdown(timeline: CaseTimeline, saved_at: str) -> str:
    lines = [
        f"# ClinicalHarness Trace: {timeline.case_id}",
        "",
        f"- Saved: `{saved_at}`",
        f"- Run: `{timeline.run_id}`",
        f"- Case: `{timeline.case_id}`",
        f"- Trace source: {timeline.trace_source}",
        f"- Correct answer: {timeline.expected_diagnosis or 'unknown'}",
        f"- Model diagnosis: {timeline.model_diagnosis or 'unknown'}",
        f"- Score: {timeline.score or 'unknown'}",
        f"- Score method: {timeline.score_method or 'unknown'}",
        f"- Events: {len(timeline.events)}",
        "",
        "## Events",
        "",
    ]
    for event in timeline.events:
        lines.extend(
            [
                f"### {event.seq + 1}. {event.type}: {event.title}",
                "",
                f"- Actor: {event.actor}",
                f"- Status: {event.status}",
                f"- Round: {event.round if event.round is not None else 'n/a'}",
            ]
        )
        if event.summary:
            lines.append(f"- Summary: {event.summary}")
        lines.extend(
            [
                "",
                "```json",
                json.dumps(event.payload, indent=2, ensure_ascii=False),
                "```",
                "",
            ]
        )
    return "\n".join(lines)
