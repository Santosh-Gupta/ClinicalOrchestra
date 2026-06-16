"""Live adapter for in-process streaming.

This module documents and stubs the in-process event bus that will let the UI
watch a run *as it happens*, rather than replaying finished artifacts.

Design (see viewer/ARCHITECTURE.md, "Live mode"):

1. The harness (``retrieval_guided_eval`` / ``diagnostic_harness``) has an
   optional ``emitter`` callback. At each stage boundary it emits Event-shaped
   dictionaries with the SAME unified Event schema used here.

2. ``LiveEventBus`` below is a process-local pub/sub. The FastAPI live ingest
   endpoint publishes events; the SSE endpoint subscribes and forwards them.

3. For cross-process / scheduled runs, the same Event objects are also appended
   to ``<run>/<case>.events.jsonl`` (mirroring the existing ledger), so replay
   and live share one on-disk format and the UI code path is identical.

For same-process runs, a caller can publish directly to ``bus``. For normal CLI
runs, use the FastAPI ingest endpoint as the ``emitter`` target.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import Iterable

from ..events import Event


class LiveEventBus:
    """Process-local async pub/sub keyed by ``(run_id, case_id)``.

    Producers (the harness, via an emitter callback) call :meth:`publish`.
    Consumers (the SSE endpoint) call :meth:`subscribe` to get an async queue.
    """

    def __init__(self) -> None:
        self._subscribers: dict[tuple[str, str], list[asyncio.Queue[Event | None]]] = defaultdict(list)
        self._history: dict[tuple[str, str], deque[Event]] = defaultdict(lambda: deque(maxlen=500))
        self._active: set[tuple[str, str]] = set()

    def subscribe(self, run_id: str, case_id: str, *, replay_history: bool = True) -> asyncio.Queue[Event | None]:
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        if replay_history:
            for event in self.history(run_id, case_id):
                queue.put_nowait(event)
        self._subscribers[(run_id, case_id)].append(queue)
        return queue

    def unsubscribe(self, run_id: str, case_id: str, queue: asyncio.Queue[Event | None]) -> None:
        subs = self._subscribers.get((run_id, case_id))
        if subs and queue in subs:
            subs.remove(queue)

    async def publish(self, event: Event) -> None:
        key = (event.run_id, event.case_id)
        self._active.add(key)
        self._history[key].append(event)
        for queue in list(self._subscribers.get(key, [])):
            await queue.put(event)
        if event.type.value == "case_completed":
            await self.close(event.run_id, event.case_id)

    async def close(self, run_id: str, case_id: str) -> None:
        """Signal end-of-stream to all subscribers of a case."""

        key = (run_id, case_id)
        self._active.discard(key)
        for queue in list(self._subscribers.get(key, [])):
            await queue.put(None)

    def is_active(self, run_id: str, case_id: str) -> bool:
        return (run_id, case_id) in self._active

    def history(self, run_id: str, case_id: str) -> Iterable[Event]:
        return tuple(self._history.get((run_id, case_id), ()))

    def keys(self) -> Iterable[tuple[str, str]]:
        """All run/case pairs known to this process, active or recently completed."""

        return tuple(sorted(set(self._history) | self._active))

    def run_ids(self) -> Iterable[str]:
        return tuple(sorted({run_id for run_id, _case_id in self.keys()}))

    def case_ids(self, run_id: str) -> Iterable[str]:
        return tuple(case_id for key_run_id, case_id in self.keys() if key_run_id == run_id)

    def clear(self) -> None:
        """Reset process-local state. Intended for tests and development reloads."""

        self._subscribers.clear()
        self._history.clear()
        self._active.clear()


# Singleton used by the app. Harvested by the SSE endpoint; populated by a future
# harness emitter.
bus = LiveEventBus()
