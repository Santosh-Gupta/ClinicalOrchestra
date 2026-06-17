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
POST /api/new-case                               -> create and run a viewer-submitted case
POST /api/live/events                            -> publish one live Event
POST /api/live/close                             -> close one live stream

The stream endpoint prefers active live events and falls back to replaying a
finished timeline event-by-event with a small delay.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import runs as runs_mod
from .adapters.live import bus
from .adapters.replay import ARTIFACTS, LEDGER_ARTIFACTS, build_case_timeline
from .config import cors_origins, runs_dir, user_generated_dir, user_generated_runs_dir
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
_REPO_ROOT = Path(__file__).resolve().parents[3]


class NewCaseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    prompt: str = Field(min_length=20, max_length=50000)
    correct_answer: str | None = Field(default=None, max_length=1000)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    case_id: str | None = Field(default=None, max_length=120)
    run_id: str | None = Field(default=None, max_length=120)
    dry_run: bool = True
    retrieve: bool = False
    judge: bool = False
    max_queries: int = Field(default=2, ge=1, le=8)
    articles_per_query: int = Field(default=3, ge=1, le=10)
    max_rounds: int = Field(default=1, ge=1, le=4)
    model: str | None = Field(default=None, max_length=120)


class NewCaseResponse(BaseModel):
    status: str
    run_id: str
    case_id: str
    run_dir: str
    manifest_path: str
    trace_url: str
    dry_run: bool
    retrieve: bool
    judge: bool


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


@app.post("/api/new-case", response_model=NewCaseResponse)
async def create_new_case(payload: NewCaseRequest) -> NewCaseResponse:
    """Create a viewer-owned case manifest and run it in the background."""

    submitted_at = datetime.now(UTC).replace(microsecond=0)
    case_id = _safe_case_slug(payload.case_id or payload.title, prefix="user_case")
    run_id = _safe_run_slug(payload.run_id or f"user_generated_{submitted_at.strftime('%Y%m%d_%H%M%S')}")
    case_root = user_generated_dir() / "cases" / run_id
    run_root = user_generated_runs_dir()
    run_dir = run_root / run_id
    manifest_path = case_root / "manifest.jsonl"
    if run_dir.exists():
        raise HTTPException(status_code=409, detail=f"run already exists: {run_id}")
    case_root.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)

    answer_key = {
        "diagnosis": payload.correct_answer.strip() if payload.correct_answer and payload.correct_answer.strip() else "unknown",
        "aliases": [alias.strip() for alias in payload.aliases if alias.strip()],
    }
    manifest_row = {
        "case_id": case_id,
        "title": payload.title.strip(),
        "challenge_prompt": payload.prompt.strip(),
        "answer_key": answer_key,
        "source": "viewer_user_generated",
        "created_at": submitted_at.isoformat(),
        "metadata": {"correct_answer_provided": answer_key["diagnosis"] != "unknown"},
    }
    manifest_path.write_text(json.dumps(manifest_row, ensure_ascii=False) + "\n", encoding="utf-8")

    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=_run_new_case_background,
        kwargs={
            "payload": payload,
            "manifest_path": manifest_path,
            "run_dir": run_dir,
            "run_id": run_id,
            "case_id": case_id,
            "loop": loop,
        },
        name=f"clinical-viewer-new-case-{run_id}",
        daemon=True,
    )
    thread.start()

    return NewCaseResponse(
        status="started",
        run_id=run_id,
        case_id=case_id,
        run_dir=str(run_dir),
        manifest_path=str(manifest_path),
        trace_url=f"/api/runs/{run_id}/cases/{case_id}/stream",
        dry_run=payload.dry_run,
        retrieve=payload.retrieve,
        judge=payload.judge and bool(payload.correct_answer and payload.correct_answer.strip()),
    )


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


def _run_new_case_background(
    *,
    payload: NewCaseRequest,
    manifest_path: Path,
    run_dir: Path,
    run_id: str,
    case_id: str,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Run the submitted case without blocking the FastAPI request."""

    try:
        src_dir = _REPO_ROOT / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        from clinical_harness.ncbi import NcbiClient, NcbiConfig
        from clinical_harness.retrieval_guided_eval import HarnessConfig, run_retrieval_guided_manifest_eval

        pubmed_client = (
            NcbiClient(
                NcbiConfig(
                    email=os.getenv("NCBI_EMAIL"),
                    api_key=os.getenv("NCBI_API_KEY"),
                    tool="ClinicalHarnessViewer",
                )
            )
            if payload.retrieve
            else None
        )

        def emitter(raw_event: dict) -> None:
            try:
                event = Event.model_validate(raw_event)
            except ValueError:
                return
            try:
                loop.call_soon_threadsafe(lambda: asyncio.create_task(bus.publish(event)))
            except RuntimeError:
                pass

        run_retrieval_guided_manifest_eval(
            manifest_path=manifest_path,
            out_dir=run_dir,
            dry_run=payload.dry_run,
            retrieve=payload.retrieve,
            pubmed_client=pubmed_client,
            model_name=payload.model,
            max_queries=payload.max_queries,
            articles_per_query=payload.articles_per_query,
            max_rounds=payload.max_rounds,
            judge=payload.judge and bool(payload.correct_answer and payload.correct_answer.strip()),
            concurrency=1,
            emitter=emitter,
            config=HarnessConfig(eval_mode=False),
        )
    except Exception as exc:  # noqa: BLE001 - surface failures as trace events.
        _write_new_case_error_trace(run_dir, run_id, case_id, str(exc), loop)


def _write_new_case_error_trace(
    run_dir: Path,
    run_id: str,
    case_id: str,
    error: str,
    loop: asyncio.AbstractEventLoop,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).replace(microsecond=0).isoformat()
    events = [
        Event(
            id="e0000",
            seq=0,
            ts=ts,
            run_id=run_id,
            case_id=case_id,
            type="case_started",
            actor="runner",
            title=f"Case {case_id}",
            status="error",
            payload={"source": "viewer_new_case"},
        ),
        Event(
            id="e0001",
            seq=1,
            ts=ts,
            run_id=run_id,
            case_id=case_id,
            type="error",
            actor="system",
            title="New case run failed",
            summary=error,
            status="error",
            payload={"error": error},
        ),
        Event(
            id="e0002",
            seq=2,
            ts=ts,
            run_id=run_id,
            case_id=case_id,
            type="case_completed",
            actor="runner",
            title="Case complete",
            summary="failed",
            status="error",
            payload={"error": error},
        ),
    ]
    (run_dir / f"{case_id}.events.jsonl").write_text(
        "".join(event.model_dump_json() + "\n" for event in events),
        encoding="utf-8",
    )
    for event in events:
        try:
            loop.call_soon_threadsafe(lambda event=event: asyncio.create_task(bus.publish(event)))
        except RuntimeError:
            pass


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


def _safe_case_slug(value: str, *, prefix: str) -> str:
    slug = _safe_filename(value.lower().replace(" ", "_"))
    slug = re.sub(r"_+", "_", slug)[:80].strip("_")
    if not slug or slug == "trace":
        slug = prefix
    return slug


def _safe_run_slug(value: str) -> str:
    slug = _safe_filename(value)
    if slug in ("", ".", "..", "trace"):
        slug = f"user_generated_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    return slug[:120]


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
