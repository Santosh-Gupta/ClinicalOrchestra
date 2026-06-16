"""Append-only run ledger for reproducible case attempts."""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .schemas import (
    EvidenceRecord,
    RunManifest,
    SearchQuery,
    StructuredAnswer,
    to_jsonable,
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


class RunLedger:
    """Writes manifest, events, queries, evidence, and answers for one run."""

    def __init__(self, manifest: RunManifest) -> None:
        self.manifest = manifest
        self.run_dir = Path(manifest.run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self._touch("events.jsonl")
        self._touch("queries.jsonl")
        self._touch("evidence.jsonl")
        self.write_manifest()

    @classmethod
    def create(
        cls,
        *,
        out_dir: str | Path,
        case_id: str,
        case_path: str | Path,
        mode: str,
        run_id: str | None = None,
        cli_args: dict[str, Any] | None = None,
        allowed_sources: tuple[str, ...] = (),
        source_exclusion: dict[str, Any] | None = None,
        git_commit: str | None = None,
    ) -> "RunLedger":
        resolved_out_dir = Path(out_dir).expanduser().resolve()
        resolved_run_id = run_id or make_run_id()
        run_dir = resolved_out_dir / resolved_run_id
        manifest = RunManifest(
            run_id=resolved_run_id,
            case_id=case_id,
            mode=mode,
            started_at=utc_now(),
            status="running",
            run_dir=str(run_dir),
            case_path=str(Path(case_path).expanduser().resolve()),
            cli_args=cli_args or {},
            allowed_sources=allowed_sources,
            source_exclusion=source_exclusion or {},
            git_commit=git_commit,
            python_version=sys.version.split()[0],
        )
        ledger = cls(manifest)
        ledger.append_event(
            actor="runner",
            action="run_created",
            output_ids=[resolved_run_id],
            details={"mode": mode, "case_id": case_id},
        )
        return ledger

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "manifest.json"

    def update_manifest(self, **changes: Any) -> None:
        self.manifest = replace(self.manifest, **changes)
        self.write_manifest()

    def write_manifest(self) -> None:
        _write_json(self.manifest_path, self.manifest)

    def append_event(
        self,
        *,
        actor: str,
        action: str,
        input_ids: list[str] | tuple[str, ...] = (),
        output_ids: list[str] | tuple[str, ...] = (),
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_id": f"event:{uuid.uuid4().hex}",
            "timestamp": utc_now(),
            "actor": actor,
            "action": action,
            "input_ids": list(input_ids),
            "output_ids": list(output_ids),
            "details": details or {},
            "error": error,
        }
        self._append_jsonl("events.jsonl", event)
        return event

    def write_query(self, query: SearchQuery) -> None:
        self._append_jsonl("queries.jsonl", query)

    def write_evidence(self, evidence: EvidenceRecord) -> None:
        self._append_jsonl("evidence.jsonl", evidence)

    def write_answer(self, answer: StructuredAnswer) -> Path:
        path = self.run_dir / "answer.json"
        _write_json(path, answer)
        return path

    def _touch(self, filename: str) -> None:
        (self.run_dir / filename).touch(exist_ok=False)

    def _append_jsonl(self, filename: str, payload: Any) -> None:
        path = self.run_dir / filename
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(to_jsonable(payload), sort_keys=True) + "\n")


def _write_json(path: Path, payload: Any) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(to_jsonable(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
