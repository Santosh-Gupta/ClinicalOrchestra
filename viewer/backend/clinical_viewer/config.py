"""Runtime configuration for the viewer backend."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


# This file lives at viewer/backend/clinical_viewer/config.py, so the repo root
# is three parents up from the package directory.
_REPO_ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def runs_dir() -> Path:
    """Directory holding harness run outputs.

    Override with the ``CLINICAL_HARNESS_RUNS`` environment variable; otherwise
    default to ``<repo>/runs``.
    """

    env = os.environ.get("CLINICAL_HARNESS_RUNS")
    if env:
        return Path(env).expanduser().resolve()
    return (_REPO_ROOT / "runs").resolve()


@lru_cache(maxsize=1)
def user_generated_dir() -> Path:
    """Directory for viewer-created exports.

    These files are intentionally separate from harness run artifacts so saved
    traces can be consumed by other systems without mutating benchmark outputs.
    """

    env = os.environ.get("CLINICAL_VIEWER_USER_GENERATED")
    if env:
        return Path(env).expanduser().resolve()
    return (_REPO_ROOT / "viewer" / "user_generated").resolve()


@lru_cache(maxsize=1)
def user_generated_runs_dir() -> Path:
    """Directory holding viewer-created run outputs."""

    env = os.environ.get("CLINICAL_VIEWER_USER_RUNS")
    if env:
        return Path(env).expanduser().resolve()
    return (user_generated_dir() / "runs").resolve()


def cors_origins() -> list[str]:
    """Allowed origins for the dev frontend.

    Defaults to the Vite dev server. Override with ``CLINICAL_VIEWER_CORS`` as a
    comma-separated list.
    """

    env = os.environ.get("CLINICAL_VIEWER_CORS")
    if env:
        return [origin.strip() for origin in env.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]
