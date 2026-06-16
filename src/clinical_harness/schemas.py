"""Serializable core schemas for diagnosis attempts."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any


JsonDict = dict[str, Any]


class JsonSerializableMixin:
    """Mixin for dataclasses that should be JSON-serializable."""

    def to_dict(self) -> JsonDict:
        return to_jsonable(self)


def to_jsonable(value: Any) -> Any:
    """Convert nested dataclasses and containers to JSON-compatible values."""

    if is_dataclass(value):
        return {item.name: to_jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple | list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class ClinicalCase(JsonSerializableMixin):
    case_id: str
    title: str
    prompt: str
    answer_key: JsonDict | None = None
    metadata: JsonDict = field(default_factory=dict)

    def source_exclusion(self) -> JsonDict:
        value = self.metadata.get("source_exclusion", {})
        return dict(value) if isinstance(value, dict) else {}


@dataclass(frozen=True)
class ProblemRepresentation(JsonSerializableMixin):
    case_id: str
    summary: str
    age: str | None = None
    sex: str | None = None
    tempo: str | None = None
    localization: str | None = None
    key_findings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SearchQuery(JsonSerializableMixin):
    query_id: str
    query: str
    source: str
    generated_by: str
    intent: str
    executed: bool = False
    result_count: int | None = None


@dataclass(frozen=True)
class EvidenceRecord(JsonSerializableMixin):
    evidence_id: str
    source_api: str
    query_id: str
    query: str
    rank: int
    retrieved_at: str
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    title: str | None = None
    abstract: str | None = None
    journal: str | None = None
    publication_year: str | None = None
    publication_types: tuple[str, ...] = field(default_factory=tuple)
    url: str | None = None
    license_status: str = "metadata_or_abstract_only"
    original_source_match: bool = False
    excluded: bool = False
    exclusion_reason: str | None = None


@dataclass(frozen=True)
class CandidateDiagnosis(JsonSerializableMixin):
    diagnosis: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    supporting_evidence: tuple[str, ...] = field(default_factory=tuple)
    refuting_evidence: tuple[str, ...] = field(default_factory=tuple)
    confidence: str = "low"


@dataclass(frozen=True)
class AnswerCitation(JsonSerializableMixin):
    evidence_id: str
    claim: str


@dataclass(frozen=True)
class StructuredAnswer(JsonSerializableMixin):
    final_diagnosis: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    localization: str | None = None
    differential: tuple[CandidateDiagnosis, ...] = field(default_factory=tuple)
    recommended_next_tests: tuple[str, ...] = field(default_factory=tuple)
    citations: tuple[AnswerCitation, ...] = field(default_factory=tuple)
    confidence: str = "low"


@dataclass(frozen=True)
class RunManifest(JsonSerializableMixin):
    run_id: str
    case_id: str
    mode: str
    started_at: str
    status: str
    run_dir: str
    case_path: str
    cli_args: JsonDict = field(default_factory=dict)
    allowed_sources: tuple[str, ...] = field(default_factory=tuple)
    source_exclusion: JsonDict = field(default_factory=dict)
    query_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    model_call_ids: tuple[str, ...] = field(default_factory=tuple)
    answer_path: str | None = None
    scores_path: str | None = None
    git_commit: str | None = None
    python_version: str | None = None
    completed_at: str | None = None


@dataclass(frozen=True)
class ModelCallRecord(JsonSerializableMixin):
    call_id: str
    role: str
    provider: str
    model: str
    started_at: str
    prompt_id: str | None = None
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_estimate_usd: float | None = None
    latency_ms: float | None = None
    error: str | None = None
    completed_at: str | None = None
