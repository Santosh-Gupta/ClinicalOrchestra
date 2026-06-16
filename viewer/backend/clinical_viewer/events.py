"""The unified Event schema — the contract between harness and UI.

Every way of observing the harness (replay from artifacts today, a live event
emitter tomorrow) is normalized into a flat stream of :class:`Event` objects.
The frontend renders each event by its ``type`` and ``payload``; adding a new
harness stage means adding an :class:`EventType` and a payload shape here, then
a renderer in the frontend. Keep this file and ``frontend/src/types.ts`` in sync.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """The kinds of things that happen while the harness works a case.

    Ordered roughly by when they occur in a single case attempt.
    """

    RUN_STARTED = "run_started"
    CASE_STARTED = "case_started"
    PROBLEM_REPRESENTATION = "problem_representation"
    ROUND_STARTED = "round_started"
    QUERY_GENERATED = "query_generated"
    TOOL_CALL = "tool_call"
    SEARCH_EXECUTED = "search_executed"
    EVIDENCE_RETRIEVED = "evidence_retrieved"
    SYNTHESIS = "synthesis"
    ROUND_COMPLETED = "round_completed"
    PROMPT_BUILT = "prompt_built"
    MODEL_CALL = "model_call"
    MODEL_RESPONSE = "model_response"
    ANSWER = "answer"
    JUDGE = "judge"
    CASE_COMPLETED = "case_completed"
    NOTE = "note"
    ERROR = "error"


# Actors map to the conceptual "agents" inside the harness. The frontend uses
# these to assign an icon/colour, much like Claude Code labels tool calls.
Actor = Literal[
    "runner",
    "planner",
    "retriever",
    "synthesizer",
    "diagnostician",
    "judge",
    "system",
]

# A coarse status used for colour-coding. "pass"/"fail" are terminal verdicts;
# the rest describe in-flight or informational states.
Status = Literal["ok", "running", "warn", "error", "pass", "fail", "info"]


class Event(BaseModel):
    """One observable step in a case attempt.

    ``payload`` is intentionally free-form (type-specific) so the schema can grow
    without breaking older events. Renderers should treat unknown keys leniently.
    """

    id: str = Field(description="Stable, ordered id within a case timeline, e.g. 'e0007'.")
    seq: int = Field(description="Monotonic sequence number within the timeline.")
    ts: str | None = Field(default=None, description="ISO-8601 timestamp if known.")
    run_id: str
    case_id: str
    round: int | None = Field(default=None, description="Retrieval round, when applicable.")
    type: EventType
    actor: Actor = "system"
    title: str = Field(description="Short headline shown on the event card.")
    summary: str | None = Field(default=None, description="Optional one-line detail.")
    status: Status = "ok"
    payload: dict[str, Any] = Field(default_factory=dict)


class CaseTimeline(BaseModel):
    """A full reconstructed timeline for one case plus light header metadata."""

    run_id: str
    case_id: str
    title: str | None = None
    trace_source: Literal["native", "live", "replay"] = "replay"
    trace_notice: str | None = None
    expected_diagnosis: str | None = None
    model_diagnosis: str | None = None
    score: str | None = None
    score_method: str | None = None
    artifacts: list["CaseArtifact"] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)


class CaseArtifact(BaseModel):
    """A raw per-case artifact that can be fetched through the viewer API."""

    name: str
    label: str
    filename: str


class CaseSummary(BaseModel):
    """Row shown in the case list for a run."""

    case_id: str
    expected_diagnosis: str | None = None
    model_diagnosis: str | None = None
    score: str | None = None
    judge_match_type: str | None = None
    query_count: int | None = None
    evidence_count: int | None = None
    error: str | None = None
    has_native_events: bool = False
    is_live: bool = False
    is_complete: bool | None = None
    event_count: int | None = None
    last_event_type: str | None = None


class RunSummary(BaseModel):
    """Row shown in the run picker."""

    run_id: str
    path: str
    modified_at: str | None = None
    case_count: int = 0
    pass_count: int | None = None
    fail_count: int | None = None
    has_results: bool = False
    native_event_case_count: int = 0
    live_case_count: int = 0
    incomplete_case_count: int = 0
