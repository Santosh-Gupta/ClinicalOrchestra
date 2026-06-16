"""ClinicalHarness Viewer backend.

A read-only service that reconstructs the *trace* of a harness run from its
on-disk artifacts (replay mode) and serves it to the web UI as a stream of
unified :class:`~clinical_viewer.events.Event` objects.

See ``viewer/ARCHITECTURE.md`` for the full design and the live-mode roadmap.
"""

__version__ = "0.1.0"
