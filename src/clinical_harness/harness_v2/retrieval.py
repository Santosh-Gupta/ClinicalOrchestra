"""Stage 3: retrieval (gated, frontier-led, reader-as-extractor).

Reuse v1 infrastructure: NcbiClient (ncbi.py) for PubMed/PMC, eval-mode source exclusion, and the cheap reader.
Do NOT reuse v1's final reranker — v2 never lets retrieval reorder the list; it only produces evidence for the
verifier.

Three principles (docs/HARNESS_V2_DESIGN.md):
1. Necessity gate: skip retrieval entirely when the model's bare differential is confident and complete. This
   avoids injecting noise into cases the model already knows (the main source of v1 regressions).
2. Frontier-led queries: the PRIMARY model sets the retrieval agenda from its own uncertainty
   ("what distinguishes B1 from B2?", "what would make B1 impossible?", "what rare entity explains finding F?").
   The reader may expand wording/synonyms but does not own the first agenda.
3. Candidate coverage: retrieve a discriminator source for EACH bare candidate (Bi diagnosis/mimics/Bi-vs-Bj),
   so retrieval protects the existing list from unfair demotion rather than only amplifying a new "shiny" dx.

Reader = EXTRACTOR ONLY. It extracts verbatim discriminators and suggests search phrases. It never decides the
diagnosis or reorders the top-5.
"""
from __future__ import annotations

import json
import re
from typing import Any

from clinical_harness.guided_eval import parse_json_object
from clinical_harness.pubmed import pubmed_search
from clinical_harness.retrieval_guided_eval import _normalize_identifier, _normalize_title, _sanitize_query

from .types import Discriminator, ProtectedLedger

_NECESSITY_PROMPT = (
    "You are deciding whether external biomedical retrieval is necessary for this protected bare differential. "
    "Return retrieval_needed=false when the differential is confident, specific, and does not hinge on an "
    "external criterion. Return true when there is a concrete knowledge gap, rare entity, pathology/genetic/"
    "drug/infectious discriminator, or criterion-dependent distinction. Return strict JSON only.\n\n"
    "Case:\n{case_prompt}\n\nProtected top-5:\n{top5}\n\n"
    'Schema: {"retrieval_needed":true,"reason":"brief","uncertainties":["..."]}'
)

_QUERY_PROMPT = (
    "Generate PubMed queries for ClinicalHarness v2. The primary model controls the retrieval agenda. "
    "Do not search for article titles, DOI, PMCID, PMID, or exact case text. Generate queries about concepts, "
    "discriminators, criteria, mimics, tests, imaging/pathology/lab patterns, and candidate coverage. "
    "Include at least one query that protects or checks each protected bare candidate. Return strict JSON only.\n\n"
    "Case:\n{case_prompt}\n\nProtected ledger:\n{ledger}\n\n"
    'Schema: {"queries":[{"query":"...","purpose":"..."}],'
    '"reader_extraction_brief":"what the reader should extract if papers are relevant"}'
)

_READER_PROMPT = (
    "You are a reader/extractor inside ClinicalHarness v2. You are NOT deciding the diagnosis and must not "
    "reorder candidates. Read the retrieved abstract skeptically. Extract only case-anchored diagnostic "
    "discriminators. A generic article criterion counts only if its triggering finding is quoted verbatim from "
    "the case. Absence is not refutation.\n\n"
    "Return strict JSON only:\n"
    '{"relevant":true,"discriminators":[{"quote":"verbatim case span","diagnosis":"entity",'
    '"relation":"supports|refutes","diagnostic":true,"evidence_tier":1,'
    '"source_claim":"brief claim from abstract"}],"suggested_queries":["..."]}\n\n'
    "Case:\n{case_prompt}\n\n"
    "Query: {query}\n\n"
    "Article:\n{article}\n"
)


def retrieval_needed(ledger: ProtectedLedger, primary_model, config) -> bool:
    """Necessity gate: return False (skip retrieval) when the model is confident its differential is complete
    and no top candidate hinges on an external diagnostic criterion. Return True for rare/low-confidence/
    criterion-dependent cases. (config.retrieval_necessity_gate toggles whether this is consulted.)"""
    if not config.retrieval_necessity_gate:
        return True
    prompt = _NECESSITY_PROMPT.replace("{case_prompt}", ledger.case_prompt).replace(
        "{top5}", json.dumps(ledger.ranked_diagnoses(), indent=2)
    )
    try:
        result = primary_model.chat(prompt=prompt, temperature=0.0, max_tokens=3000)
        payload = parse_json_object(result.content)
    except Exception:
        return True
    return bool(payload.get("retrieval_needed"))


def generate_queries(ledger: ProtectedLedger, primary_model, config) -> list[str]:
    """Frontier-led discriminator queries derived from the model's own uncertainty + per-candidate coverage."""
    ledger_payload = [
        {
            "rank": c.rank,
            "diagnosis": c.diagnosis,
            "aliases": list(c.aliases),
            "broader_form": c.broader_form,
            "candidate_subtypes": list(c.candidate_subtypes),
        }
        for c in ledger.candidates
    ]
    queries: list[str] = []
    prompt = _QUERY_PROMPT.replace("{case_prompt}", ledger.case_prompt).replace(
        "{ledger}", json.dumps(ledger_payload, indent=2)
    )
    try:
        result = primary_model.chat(prompt=prompt, temperature=0.0, max_tokens=6000)
        payload = parse_json_object(result.content)
        for item in payload.get("queries", []):
            if isinstance(item, dict):
                query = item.get("query")
            else:
                query = item
            if isinstance(query, str) and query.strip():
                queries.append(_sanitize_query(query))
    except Exception:
        pass
    for c in ledger.candidates:
        queries.append(_sanitize_query(f"{c.diagnosis} diagnostic criteria mimics distinguishing features"))
    return _dedupe([q for q in queries if q])[: int(getattr(config, "max_queries", 8))]


def gather_evidence(queries: list[str], case_prompt: str, ncbi_client, reader_model, config) -> list[dict]:
    """Run eval-mode retrieval (exclude the source paper), screen each paper with the reader, and return the
    retained relevant items. Each item carries: pmcid/doi/title, the extracted verbatim discriminator(s), the
    diagnosis it supports/refutes, and an evidence tier (1-4). Most retrieved papers are rejected; keep only
    case-relevant extractions. The reader does NOT pick a diagnosis."""
    if ncbi_client is None:
        return []
    retained: list[dict[str, Any]] = []
    seen_pmids: set[str] = set()
    articles_per_query = int(getattr(config, "articles_per_query", 3))
    max_reader_articles = int(getattr(config, "max_reader_articles", 18))
    source_exclusion = getattr(config, "_current_source_exclusion", {}) or {}
    for query in queries:
        try:
            search_result = pubmed_search(ncbi_client, query, limit=articles_per_query, sort="relevance")
        except Exception as exc:
            retained.append({"query": query, "error": str(exc), "discriminators": [], "excluded": True})
            continue
        for article in search_result.get("articles", []):
            if not isinstance(article, dict):
                continue
            pmid = _optional_str(article.get("pmid"))
            if pmid and pmid in seen_pmids:
                continue
            if pmid:
                seen_pmids.add(pmid)
            excluded, reason = _excluded_source(article, source_exclusion)
            item = {
                "query": query,
                "pmid": pmid,
                "pmcid": _optional_str(article.get("pmcid")),
                "doi": _optional_str(article.get("doi")),
                "title": _optional_str(article.get("title")),
                "journal": _optional_str(article.get("journal")),
                "publication_year": _optional_str(article.get("publication_year")),
                "publication_types": article.get("publication_types") if isinstance(article.get("publication_types"), list) else [],
                "url": _optional_str(article.get("url")),
                "abstract": _clip(_optional_str(article.get("abstract")), 1800),
                "excluded": excluded,
                "exclusion_reason": reason,
                "discriminators": [],
            }
            if excluded:
                retained.append(item)
                continue
            if len([x for x in retained if not x.get("excluded")]) >= max_reader_articles:
                continue
            item["discriminators"] = _reader_extract(query, case_prompt, item, reader_model)
            if item["discriminators"]:
                retained.append(item)
    return retained


def evidence_to_discriminators(evidence: list[dict], ledger: ProtectedLedger) -> list[Discriminator]:
    """Convert retained evidence into candidate Discriminators, each anchored to a VERBATIM span of the case
    prompt. A retrieved paper's generic criterion only becomes a Discriminator if the criterion's triggering
    finding is verbatim-present in THIS case. (This is where 'absence != refutation' is enforced upstream.)"""
    discriminators: list[Discriminator] = []
    for item in evidence:
        if item.get("excluded"):
            continue
        for disc in item.get("discriminators", []):
            if not isinstance(disc, dict):
                continue
            quote = _optional_str(disc.get("quote"))
            diagnosis = _optional_str(disc.get("diagnosis")) or _optional_str(disc.get("points_to"))
            relation = str(disc.get("relation") or "supports").strip().lower()
            if not quote or quote not in ledger.case_prompt or not diagnosis or relation not in {"supports", "refutes"}:
                continue
            discriminators.append(
                disc_obj := Discriminator(
                    quote=quote,
                    present=True,
                    points_to=diagnosis,
                    relation=relation,  # type: ignore[arg-type]
                    diagnostic=bool(disc.get("diagnostic")),
                )
            )
            setattr(disc_obj, "evidence_tier", disc.get("evidence_tier"))
    return discriminators


def _reader_extract(query: str, case_prompt: str, article: dict[str, Any], reader_model) -> list[dict[str, Any]]:
    if reader_model is None:
        return []
    packet = {
        "title": article.get("title"),
        "journal": article.get("journal"),
        "publication_year": article.get("publication_year"),
        "publication_types": article.get("publication_types"),
        "abstract": article.get("abstract"),
    }
    prompt = (
        _READER_PROMPT.replace("{case_prompt}", case_prompt)
        .replace("{query}", query)
        .replace("{article}", json.dumps(packet, indent=2, sort_keys=True))
    )
    try:
        result = reader_model.chat(prompt=prompt, temperature=0.0, max_tokens=6000)
        payload = parse_json_object(result.content)
    except Exception:
        return []
    if not payload.get("relevant"):
        return []
    out: list[dict[str, Any]] = []
    for item in payload.get("discriminators", []):
        if not isinstance(item, dict):
            continue
        quote = _optional_str(item.get("quote"))
        if not quote or quote not in case_prompt:
            continue
        item = dict(item)
        item["evidence_tier"] = _evidence_tier(item.get("evidence_tier"), article)
        out.append(item)
    return out


def _evidence_tier(value: Any, article: dict[str, Any]) -> int:
    try:
        tier = int(value)
        if 1 <= tier <= 4:
            return tier
    except (TypeError, ValueError):
        pass
    text = " ".join(str(x).lower() for x in article.get("publication_types", []) if isinstance(x, str))
    title = str(article.get("title") or "").lower()
    if any(word in text or word in title for word in ("guideline", "practice guideline", "consensus", "criteria")):
        return 1
    if "review" in text or "review" in title:
        return 1
    if "case reports" in text or "case report" in title:
        return 3
    if any(word in title for word in ("series", "cohort")):
        return 2
    return 4


def _excluded_source(article: dict[str, Any], exclusion: dict[str, Any]) -> tuple[bool, str | None]:
    source_pmcid = _normalize_identifier(_optional_str(exclusion.get("pmcid")))
    source_doi = _normalize_identifier(_optional_str(exclusion.get("doi")))
    source_title = _normalize_title(_optional_str(exclusion.get("title")))
    article_pmcid = _normalize_identifier(_optional_str(article.get("pmcid")))
    article_doi = _normalize_identifier(_optional_str(article.get("doi")))
    article_title = _normalize_title(_optional_str(article.get("title")))
    if source_pmcid and article_pmcid and source_pmcid == article_pmcid:
        return True, "source_pmcid_match"
    if source_doi and article_doi and source_doi == article_doi:
        return True, "source_doi_match"
    if source_title and article_title and source_title == article_title:
        return True, "source_title_match"
    return False, None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = re.sub(r"\s+", " ", value.lower()).strip()
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _clip(value: str | None, max_chars: int) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."
