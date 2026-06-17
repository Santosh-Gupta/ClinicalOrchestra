"""Discover runs and cases on disk.

A "run" is a directory under :func:`config.runs_dir`. A "case" is identified by
the shared filename stem of its artifacts, e.g. ``transformed_PMC11631938`` for
``transformed_PMC11631938.queries.json`` and friends. An aggregate
``retrieval_guided_results.jsonl`` (when present) carries judge verdicts.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .adapters.live import bus
from .config import runs_dir, user_generated_runs_dir
from .events import CaseSummary, RunSummary

# Artifact suffixes that identify a case stem. Order is also the rough pipeline
# order, used elsewhere when reconstructing timelines.
ARTIFACT_SUFFIXES = (
    ".events.jsonl",
    ".queries.json",
    ".evidence.json",
    ".synthesis.json",
    ".retrieval_response.json",
    ".retrieval_prompt.txt",
    ".report.md",
)

RESULTS_FILENAME = "retrieval_guided_results.jsonl"
LEDGER_EVENTS_FILENAME = "events.jsonl"
LEDGER_MANIFEST_FILENAME = "manifest.json"


def _safe_run_dir(run_id: str) -> Path:
    """Resolve a run id to a directory, refusing path traversal."""

    if "/" in run_id or "\\" in run_id or run_id in ("", ".", ".."):
        raise ValueError(f"invalid run id: {run_id!r}")
    for root in _run_roots():
        path = (root / run_id).resolve()
        if path.parent == root and path.is_dir():
            return path
    raise FileNotFoundError(f"run not found: {run_id}")


def _run_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for root in (runs_dir(), user_generated_runs_dir()):
        resolved = root.resolve()
        if resolved not in seen:
            roots.append(resolved)
            seen.add(resolved)
    return tuple(roots)


def case_stems(run_path: Path) -> list[str]:
    """Distinct case stems present in a run directory."""

    stems: set[str] = set()
    for entry in run_path.iterdir():
        if not entry.is_file():
            continue
        for suffix in ARTIFACT_SUFFIXES:
            if entry.name.endswith(suffix):
                stems.add(entry.name[: -len(suffix)])
                break
    ledger_case_id = _ledger_case_id(run_path)
    if ledger_case_id:
        stems.add(ledger_case_id)
    return sorted(stems)


def _ledger_case_id(run_path: Path) -> str | None:
    """Case id for a root ``RunLedger`` directory, when present."""

    if not (run_path / LEDGER_EVENTS_FILENAME).exists():
        return None
    manifest = _load_ledger_manifest(run_path)
    case_id = manifest.get("case_id")
    return str(case_id) if case_id else run_path.name


def _load_ledger_manifest(run_path: Path) -> dict:
    path = run_path / LEDGER_MANIFEST_FILENAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def load_results_index(run_path: Path) -> dict[str, dict]:
    """Map case_id -> aggregate results row, if a results jsonl exists."""

    results_path = run_path / RESULTS_FILENAME
    if not results_path.exists():
        return {}
    index: dict[str, dict] = {}
    for line in results_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        case_id = row.get("case_id")
        if case_id:
            index[case_id] = row
    return index


def list_runs() -> list[RunSummary]:
    """All run directories, newest first."""

    disk_entries: list[Path] = []
    for base in _run_roots():
        if base.is_dir():
            disk_entries.extend(entry for entry in base.iterdir() if entry.is_dir())
    summaries: list[RunSummary] = []
    seen_run_ids: set[str] = set()
    for entry in disk_entries:
        seen_run_ids.add(entry.name)
        results = load_results_index(entry)
        stems = case_stems(entry)
        event_infos = {}
        for stem in stems:
            info = native_event_info(entry, stem)
            event_infos[stem] = info if info["exists"] else ledger_event_info(entry, stem)
        native_count = sum(1 for info in event_infos.values() if info["exists"])
        live_count = sum(1 for stem in stems if bus.is_active(entry.name, stem))
        incomplete_count = sum(
            1
            for stem, info in event_infos.items()
            if info["exists"] and info["is_complete"] is False
        )
        passes = sum(1 for r in results.values() if r.get("score") == "pass") if results else None
        fails = sum(1 for r in results.values() if r.get("score") == "fail") if results else None
        mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=UTC).isoformat()
        summaries.append(
            RunSummary(
                run_id=entry.name,
                path=str(entry),
                modified_at=mtime,
                case_count=len(stems) or len(results),
                pass_count=passes,
                fail_count=fails,
                has_results=bool(results),
                native_event_case_count=native_count,
                live_case_count=live_count,
                incomplete_case_count=incomplete_count,
            )
        )
    for run_id in bus.run_ids():
        if run_id in seen_run_ids:
            continue
        case_ids = tuple(bus.case_ids(run_id))
        active_count = sum(1 for case_id in case_ids if bus.is_active(run_id, case_id))
        incomplete_count = sum(1 for case_id in case_ids if _live_case_is_complete(run_id, case_id) is False)
        summaries.append(
            RunSummary(
                run_id=run_id,
                path="(live)",
                modified_at=_live_run_modified_at(run_id),
                case_count=len(case_ids),
                pass_count=None,
                fail_count=None,
                has_results=False,
                native_event_case_count=0,
                live_case_count=active_count,
                incomplete_case_count=incomplete_count,
            )
        )
    summaries.sort(key=lambda s: s.modified_at or "", reverse=True)
    return summaries


def list_cases(run_id: str) -> list[CaseSummary]:
    """Case rows for a run, ordered by stem name."""

    try:
        run_path = _safe_run_dir(run_id)
    except FileNotFoundError:
        live_case_ids = tuple(bus.case_ids(run_id))
        if not live_case_ids:
            raise
        return [_live_case_summary(run_id, case_id) for case_id in live_case_ids]
    results = load_results_index(run_path)
    stems = case_stems(run_path)
    # Include result-only cases that may not have artifacts on disk.
    case_ids = sorted(set(stems) | set(results.keys()) | set(bus.case_ids(run_id)))
    summaries: list[CaseSummary] = []
    for case_id in case_ids:
        row = results.get(case_id, {})
        event_info = native_event_info(run_path, case_id)
        if not event_info["exists"]:
            event_info = ledger_event_info(run_path, case_id)
        live_history = tuple(bus.history(run_id, case_id))
        live_last = live_history[-1].type.value if live_history else None
        summaries.append(
            CaseSummary(
                case_id=case_id,
                expected_diagnosis=row.get("expected_diagnosis"),
                model_diagnosis=row.get("model_final_diagnosis"),
                score=row.get("score"),
                judge_match_type=row.get("judge_match_type"),
                query_count=row.get("query_count"),
                evidence_count=row.get("evidence_count"),
                error=row.get("error"),
                has_native_events=bool(event_info["exists"]),
                is_live=bus.is_active(run_id, case_id),
                is_complete=(
                    event_info["is_complete"]
                    if event_info["exists"]
                    else _live_case_is_complete(run_id, case_id)
                ),
                event_count=event_info["event_count"] if event_info["exists"] else (len(live_history) if live_history else None),
                last_event_type=event_info["last_event_type"] or live_last,
            )
        )
    return summaries


def resolve_case_dir(run_id: str) -> Path:
    """Validated run directory for a case lookup."""

    return _safe_run_dir(run_id)


def native_event_info(run_path: Path, case_id: str) -> dict:
    """Light metadata about a native ``<case>.events.jsonl`` ledger."""

    path = run_path / f"{case_id}.events.jsonl"
    if not path.exists():
        return {"exists": False, "event_count": None, "last_event_type": None, "is_complete": None}
    event_count = 0
    last_type = None
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                event_count += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    last_type = event.get("type") or last_type
    except OSError:
        return {"exists": True, "event_count": None, "last_event_type": None, "is_complete": None}
    return {
        "exists": True,
        "event_count": event_count,
        "last_event_type": last_type,
        "is_complete": last_type == "case_completed",
    }


def ledger_event_info(run_path: Path, case_id: str) -> dict:
    """Light metadata about a root ``RunLedger`` ``events.jsonl`` file."""

    manifest = _load_ledger_manifest(run_path)
    ledger_case_id = manifest.get("case_id") or run_path.name
    if str(ledger_case_id) != case_id:
        return {"exists": False, "event_count": None, "last_event_type": None, "is_complete": None}
    path = run_path / LEDGER_EVENTS_FILENAME
    if not path.exists():
        return {"exists": False, "event_count": None, "last_event_type": None, "is_complete": None}
    event_count = 0
    last_action = None
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                event_count += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    last_action = event.get("action") or last_action
    except OSError:
        return {"exists": True, "event_count": None, "last_event_type": None, "is_complete": None, "ledger": True}
    status = manifest.get("status")
    is_complete = status == "completed" or last_action == "answer_written"
    if status == "error" or last_action == "run_failed":
        is_complete = True
    return {
        "exists": True,
        "event_count": event_count,
        "last_event_type": last_action,
        "is_complete": is_complete,
        "ledger": True,
    }


def live_timeline(run_id: str, case_id: str):
    history = list(bus.history(run_id, case_id))
    if not history:
        return None
    from .events import CaseTimeline

    answer = next((event.payload for event in history if event.type.value == "answer"), {})
    judge = next((event.payload for event in history if event.type.value == "judge"), {})
    return CaseTimeline(
        run_id=run_id,
        case_id=case_id,
        title=case_id,
        trace_source="live",
        trace_notice="Live event stream: updates as the harness publishes prompts, model calls, retrieval, reasoning, and verdict events.",
        expected_diagnosis=judge.get("expected_diagnosis"),
        model_diagnosis=judge.get("model_final_diagnosis") or answer.get("final_diagnosis"),
        score=judge.get("score"),
        score_method=judge.get("score_method"),
        artifacts=[],
        events=history,
    )


def _live_case_summary(run_id: str, case_id: str) -> CaseSummary:
    history = tuple(bus.history(run_id, case_id))
    last_type = history[-1].type.value if history else None
    judge = next((event.payload for event in history if event.type.value == "judge"), {})
    answer = next((event.payload for event in history if event.type.value == "answer"), {})
    return CaseSummary(
        case_id=case_id,
        expected_diagnosis=judge.get("expected_diagnosis"),
        model_diagnosis=judge.get("model_final_diagnosis") or answer.get("final_diagnosis"),
        score=judge.get("score"),
        judge_match_type=judge.get("judge_match_type"),
        query_count=None,
        evidence_count=None,
        error=None,
        has_native_events=False,
        is_live=bus.is_active(run_id, case_id),
        is_complete=_live_case_is_complete(run_id, case_id),
        event_count=len(history),
        last_event_type=last_type,
    )


def _live_case_is_complete(run_id: str, case_id: str) -> bool | None:
    history = tuple(bus.history(run_id, case_id))
    if not history:
        return None
    return history[-1].type.value == "case_completed"


def _live_run_modified_at(run_id: str) -> str | None:
    latest = None
    for case_id in bus.case_ids(run_id):
        for event in bus.history(run_id, case_id):
            if event.ts and (latest is None or event.ts > latest):
                latest = event.ts
    return latest
