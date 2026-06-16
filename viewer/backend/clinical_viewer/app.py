"""FastAPI app: read-only API over harness runs, plus a streaming endpoint.

Routes
------
GET  /api/health
GET  /api/runs                                   -> [RunSummary]
GET  /api/runs/{run_id}/cases                    -> [CaseSummary]
GET  /api/runs/{run_id}/cases/{case_id}/timeline -> CaseTimeline
GET  /api/runs/{run_id}/cases/{case_id}/stream   -> text/event-stream (SSE)
GET  /api/runs/{run_id}/cases/{case_id}/artifacts/{name} -> raw artifact text
POST /api/live/events                            -> publish one live Event
POST /api/live/close                             -> close one live stream

The stream endpoint prefers active live events and falls back to replaying a
finished timeline event-by-event with a small delay.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import runs as runs_mod
from .adapters.live import bus
from .adapters.replay import ARTIFACTS, LEDGER_ARTIFACTS, build_case_timeline
from .config import cors_origins, runs_dir
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
