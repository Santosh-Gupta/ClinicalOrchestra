"""Deterministic single-case runner."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cases import load_clinical_case
from .ledger import RunLedger, utc_now
from .ncbi import NcbiClient
from .pubmed import pubmed_search
from .schemas import (
    AnswerCitation,
    CandidateDiagnosis,
    ClinicalCase,
    EvidenceRecord,
    ProblemRepresentation,
    RunManifest,
    SearchQuery,
    StructuredAnswer,
)


RUN_MODES = ("closed_book", "pubmed_only", "pubmed_only_source_excluded")

NEUROLOGY_TERMS = (
    "seizure",
    "seizures",
    "epilepsy",
    "ataxia",
    "catatonia",
    "psychosis",
    "encephalitis",
    "encephalopathy",
    "neuropathy",
    "myelopathy",
    "myelitis",
    "weakness",
    "paralysis",
    "diplopia",
    "ophthalmoplegia",
    "headache",
    "migraine",
    "tremor",
    "chorea",
    "dystonia",
    "dementia",
    "aphasia",
    "dysarthria",
    "dysphagia",
    "nystagmus",
    "vertigo",
    "paresthesia",
    "numbness",
    "spasticity",
)

HIGH_SIGNAL_PHRASES = (
    "autoimmune encephalitis",
    "anti nmda",
    "nmda receptor",
    "limbic encephalitis",
    "opsoclonus myoclonus",
    "transverse myelitis",
    "optic neuritis",
    "rapidly progressive dementia",
    "stiff person",
    "dropped head",
    "alien limb",
    "startle",
)

STOPWORDS = {
    "about",
    "after",
    "again",
    "before",
    "being",
    "between",
    "during",
    "following",
    "history",
    "patient",
    "patients",
    "presented",
    "presents",
    "showed",
    "there",
    "these",
    "those",
    "through",
    "which",
    "while",
    "without",
}


@dataclass(frozen=True)
class CaseRunResult:
    run_id: str
    run_dir: Path
    manifest: RunManifest
    answer: StructuredAnswer
    queries: tuple[SearchQuery, ...]
    evidence: tuple[EvidenceRecord, ...]


def run_case(
    case_path: str | Path,
    *,
    mode: str,
    out_dir: str | Path = "runs",
    run_id: str | None = None,
    limit: int = 5,
    sort: str = "relevance",
    retrieve: bool = True,
    client: NcbiClient | None = None,
    cli_args: dict[str, Any] | None = None,
) -> CaseRunResult:
    """Run one case through the deterministic first-slice workflow."""

    if mode not in RUN_MODES:
        raise ValueError(f"mode must be one of: {', '.join(RUN_MODES)}")
    if limit < 1:
        raise ValueError("--limit must be at least 1")
    if retrieve and mode.startswith("pubmed") and client is None:
        raise ValueError("PubMed retrieval requires an NCBI client")

    case = load_clinical_case(case_path)
    allowed_sources = ("pubmed",) if mode.startswith("pubmed") else ()
    ledger = RunLedger.create(
        out_dir=out_dir,
        case_id=case.case_id,
        case_path=case_path,
        mode=mode,
        run_id=run_id,
        cli_args=cli_args,
        allowed_sources=allowed_sources,
        source_exclusion=case.source_exclusion(),
        git_commit=_git_commit(Path(case_path).expanduser().resolve().parent),
    )

    queries: list[SearchQuery] = []
    evidence_records: list[EvidenceRecord] = []
    try:
        ledger.append_event(
            actor="case_loader",
            action="case_loaded",
            input_ids=[str(Path(case_path).expanduser())],
            output_ids=[case.case_id],
            details={"title": case.title},
        )

        problem = build_problem_representation(case)
        ledger.append_event(
            actor="template_runner",
            action="problem_represented",
            input_ids=[case.case_id],
            output_ids=[f"problem:{case.case_id}"],
            details=problem.to_dict(),
        )

        if mode.startswith("pubmed"):
            for query in generate_template_queries(case, problem):
                executed_query = query
                ledger.append_event(
                    actor="template_runner",
                    action="query_generated",
                    input_ids=[case.case_id],
                    output_ids=[query.query_id],
                    details=query.to_dict(),
                )
                if retrieve:
                    assert client is not None
                    result = pubmed_search(client, query.query, limit=limit, sort=sort)
                    result_count = _int_or_none(result.get("count"))
                    executed_query = SearchQuery(
                        query_id=query.query_id,
                        query=query.query,
                        source=query.source,
                        generated_by=query.generated_by,
                        intent=query.intent,
                        executed=True,
                        result_count=result_count,
                    )
                    ledger.append_event(
                        actor="pubmed",
                        action="query_executed",
                        input_ids=[query.query_id],
                        output_ids=[query.query_id],
                        details={
                            "query": query.query,
                            "result_count": result_count,
                            "returned_articles": len(result.get("articles", [])),
                        },
                    )
                    for rank, article in enumerate(result.get("articles", []), start=1):
                        if not isinstance(article, dict):
                            continue
                        record = evidence_from_pubmed_article(
                            article,
                            query=executed_query,
                            rank=rank,
                            case=case,
                            mode=mode,
                        )
                        if record.excluded:
                            ledger.append_event(
                                actor="retrieval_guard",
                                action="evidence_excluded",
                                input_ids=[query.query_id],
                                output_ids=[record.evidence_id],
                                details=record.to_dict(),
                            )
                            continue
                        evidence_records.append(record)
                        ledger.write_evidence(record)
                        ledger.append_event(
                            actor="pubmed",
                            action="evidence_recorded",
                            input_ids=[query.query_id],
                            output_ids=[record.evidence_id],
                            details={
                                "pmid": record.pmid,
                                "pmcid": record.pmcid,
                                "doi": record.doi,
                                "original_source_match": record.original_source_match,
                            },
                        )
                ledger.write_query(executed_query)
                queries.append(executed_query)

        answer = placeholder_structured_answer(problem, tuple(evidence_records))
        answer_path = ledger.write_answer(answer)
        ledger.append_event(
            actor="template_runner",
            action="answer_written",
            input_ids=[case.case_id, *[record.evidence_id for record in evidence_records]],
            output_ids=["answer"],
            details={"answer_path": str(answer_path), "confidence": answer.confidence},
        )
        ledger.update_manifest(
            status="completed",
            completed_at=utc_now(),
            query_ids=tuple(query.query_id for query in queries),
            evidence_ids=tuple(record.evidence_id for record in evidence_records),
            answer_path=str(answer_path),
        )
    except Exception as exc:
        ledger.append_event(
            actor="runner",
            action="run_failed",
            input_ids=[case.case_id],
            error=str(exc),
        )
        ledger.update_manifest(status="error", completed_at=utc_now())
        raise

    return CaseRunResult(
        run_id=ledger.manifest.run_id,
        run_dir=ledger.run_dir,
        manifest=ledger.manifest,
        answer=answer,
        queries=tuple(queries),
        evidence=tuple(evidence_records),
    )


def build_problem_representation(case: ClinicalCase) -> ProblemRepresentation:
    text = f"{case.title}\n{case.prompt}"
    return ProblemRepresentation(
        case_id=case.case_id,
        summary=_summary(case.prompt),
        age=_extract_age(text),
        sex=_extract_sex(text),
        tempo=_extract_tempo(text),
        localization=None,
        key_findings=tuple(_extract_key_terms(text)[:8]),
    )


def generate_template_queries(case: ClinicalCase, problem: ProblemRepresentation) -> tuple[SearchQuery, ...]:
    findings = list(problem.key_findings)
    if not findings:
        findings = _fallback_terms(case.prompt)
    base_terms = findings[:6] + ["diagnosis", "neurology", '"case report"']
    queries = [
        SearchQuery(
            query_id="q1",
            query=" ".join(base_terms),
            source="pubmed",
            generated_by="template",
            intent="find similar diagnostic case reports",
        )
    ]
    if problem.tempo and findings:
        tempo_terms = [problem.tempo, *findings[:4], '"case report"']
        queries.append(
            SearchQuery(
                query_id="q2",
                query=" ".join(tempo_terms),
                source="pubmed",
                generated_by="template",
                intent="find tempo-matched neurologic case reports",
            )
        )
    return tuple(queries)


def evidence_from_pubmed_article(
    article: dict[str, Any],
    *,
    query: SearchQuery,
    rank: int,
    case: ClinicalCase,
    mode: str,
) -> EvidenceRecord:
    pmid = _str_or_none(article.get("pmid"))
    reason = _source_match_reason(case, article)
    excluded = mode == "pubmed_only_source_excluded" and reason is not None
    return EvidenceRecord(
        evidence_id=f"pubmed:{pmid or 'unknown'}",
        source_api="pubmed",
        query_id=query.query_id,
        query=query.query,
        rank=rank,
        retrieved_at=utc_now(),
        pmid=pmid,
        pmcid=_str_or_none(article.get("pmcid")),
        doi=_str_or_none(article.get("doi")),
        title=_str_or_none(article.get("title")),
        abstract=_str_or_none(article.get("abstract")),
        journal=_str_or_none(article.get("journal")),
        publication_year=_str_or_none(article.get("publication_year")),
        publication_types=tuple(str(item) for item in article.get("publication_types", []) if item),
        url=_str_or_none(article.get("url")),
        original_source_match=reason is not None,
        excluded=excluded,
        exclusion_reason=reason,
    )


def placeholder_structured_answer(
    problem: ProblemRepresentation,
    evidence: tuple[EvidenceRecord, ...],
) -> StructuredAnswer:
    evidence_ids = tuple(record.evidence_id for record in evidence[:3])
    citations = tuple(
        AnswerCitation(
            evidence_id=evidence_id,
            claim="Retrieved PubMed evidence reserved for later synthesis.",
        )
        for evidence_id in evidence_ids
    )
    differential = (
        CandidateDiagnosis(
            diagnosis="undetermined diagnosis",
            supporting_evidence=evidence_ids,
            confidence="low",
        ),
    )
    return StructuredAnswer(
        final_diagnosis="undetermined",
        localization=problem.localization,
        differential=differential,
        citations=citations,
        confidence="low",
    )


def _source_match_reason(case: ClinicalCase, article: dict[str, Any]) -> str | None:
    exclusion = case.source_exclusion()
    pmid = _str_or_none(exclusion.get("pmid"))
    pmcid = _normalize_pmcid(_str_or_none(exclusion.get("pmcid")))
    doi = _normalize_doi(_str_or_none(exclusion.get("doi")))
    title = _normalize_title(_str_or_none(exclusion.get("title")))

    article_pmid = _str_or_none(article.get("pmid"))
    if pmid and article_pmid and pmid == article_pmid:
        return "pmid"
    article_pmcid = _normalize_pmcid(_str_or_none(article.get("pmcid")))
    if pmcid and article_pmcid and pmcid == article_pmcid:
        return "pmcid"
    article_doi = _normalize_doi(_str_or_none(article.get("doi")))
    if doi and article_doi and doi == article_doi:
        return "doi"
    article_title = _normalize_title(_str_or_none(article.get("title")))
    if title and article_title and title == article_title:
        return "title"
    return None


def _summary(prompt: str) -> str:
    cleaned = " ".join(prompt.split())
    if len(cleaned) <= 280:
        return cleaned
    return cleaned[:277].rstrip() + "..."


def _extract_age(text: str) -> str | None:
    match = re.search(r"\b(\d{1,3})[- ]?(?:year|years|yo)[- ]old\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_sex(text: str) -> str | None:
    for value, pattern in (
        ("female", r"\b(female|woman|girl)\b"),
        ("male", r"\b(male|man|boy)\b"),
    ):
        if re.search(pattern, text, flags=re.IGNORECASE):
            return value
    return None


def _extract_tempo(text: str) -> str | None:
    lowered = text.lower()
    for tempo in ("acute", "subacute", "chronic", "progressive", "relapsing", "episodic"):
        if tempo in lowered:
            return tempo
    return None


def _extract_key_terms(text: str) -> list[str]:
    lowered = text.lower()
    terms: list[str] = []
    for phrase in HIGH_SIGNAL_PHRASES:
        if phrase in lowered:
            terms.append(f'"{phrase}"')
    tokens = re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", lowered)
    for token in tokens:
        normalized = token.rstrip(".,;:")
        if normalized in NEUROLOGY_TERMS:
            terms.append(normalized)
    return _unique(terms)


def _fallback_terms(prompt: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z-]{5,}", prompt.lower())
    candidates = [token for token in tokens if token not in STOPWORDS]
    return _unique(candidates)[:5] or ["diagnostic", "case"]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().removeprefix("https://doi.org/").removeprefix("doi:")


def _normalize_pmcid(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.upper().startswith("PMC"):
        return "PMC" + cleaned[3:]
    return f"PMC{cleaned}"


def _normalize_title(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.lower().split())


def _git_commit(start_dir: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=start_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None
