from __future__ import annotations

import pytest

from clinical_viewer import runs as runs_mod
from clinical_viewer.adapters.live import LiveEventBus, bus
from clinical_viewer.events import Event, EventType


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _event(seq: int, event_type: EventType = EventType.CASE_STARTED) -> Event:
    return Event(
        id=f"e{seq:04d}",
        seq=seq,
        run_id="live-run",
        case_id="case-1",
        type=event_type,
        actor="runner",
        title="event",
    )


@pytest.mark.anyio
async def test_live_bus_replays_history_to_late_subscriber() -> None:
    bus = LiveEventBus()
    first = _event(0)

    await bus.publish(first)
    queue = bus.subscribe("live-run", "case-1")

    assert bus.is_active("live-run", "case-1")
    assert await queue.get() == first


@pytest.mark.anyio
async def test_live_bus_closes_on_case_completed() -> None:
    bus = LiveEventBus()
    queue = bus.subscribe("live-run", "case-1")
    done = _event(1, EventType.CASE_COMPLETED)

    await bus.publish(done)

    assert await queue.get() == done
    assert await queue.get() is None
    assert not bus.is_active("live-run", "case-1")


@pytest.mark.anyio
async def test_bus_only_live_run_is_discoverable_and_has_timeline() -> None:
    bus.clear()
    try:
        await bus.publish(_event(0))

        run = next(run for run in runs_mod.list_runs() if run.run_id == "live-run")
        case = runs_mod.list_cases("live-run")[0]
        timeline = runs_mod.live_timeline("live-run", "case-1")

        assert run.path == "(live)"
        assert run.live_case_count == 1
        assert case.case_id == "case-1"
        assert case.is_live
        assert case.event_count == 1
        assert timeline is not None
        assert timeline.trace_source == "live"
        assert timeline.trace_notice
        assert timeline.events[0].type == EventType.CASE_STARTED
    finally:
        bus.clear()
