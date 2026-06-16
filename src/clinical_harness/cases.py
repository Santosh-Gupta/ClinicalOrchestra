"""Clinical case loading helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import ClinicalCase


def load_clinical_case(path: str | Path) -> ClinicalCase:
    """Load a ClinicalCase from a JSON file."""

    case_path = Path(path)
    with case_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"case file must contain a JSON object: {case_path}")
    return clinical_case_from_dict(payload)


def clinical_case_from_dict(payload: dict[str, Any]) -> ClinicalCase:
    case_id = _required_str(payload, "case_id")
    title = _required_str(payload, "title")
    prompt = _required_str(payload, "prompt")

    answer_key = payload.get("answer_key")
    if answer_key is not None and not isinstance(answer_key, dict):
        raise ValueError("case answer_key must be an object when provided")

    metadata = payload.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError("case metadata must be an object when provided")

    return ClinicalCase(
        case_id=case_id,
        title=title,
        prompt=prompt,
        answer_key=answer_key,
        metadata=metadata,
    )


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"case {key} must be a non-empty string")
    return value
