"""Guided evaluation helpers for Pro-failed public case manifests."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .diagnostic_harness import PRESET_CHECKLISTS, _model_visible_case_id, redacted_blocked_shortcuts
from .model_client import OpenAICompatibleChatClient
from .preset_selection import PRESET_BY_CASE_ID, select_preset
from .schemas import ClinicalCase, JsonSerializableMixin


DEFAULT_ALL_PUBLIC_PRO_FAILED_MANIFEST = Path(
    "/Users/santoshg/Coding/NeurologyBM/data/pmc/processed/public_case_challenge_splits/refined/"
    "all_public_deepseek_v4_pro_failed_manifest_20260613.jsonl"
)



@dataclass(frozen=True)
class GuidedEvalRow(JsonSerializableMixin):
    case_id: str
    preset: str
    expected_diagnosis: str
    expected_aliases: tuple[str, ...]
    model_final_diagnosis: str | None
    model_recommended_next_step: str | None
    lexical_score: str
    prompt_path: str
    response_path: str | None
    error: str | None = None


def run_guided_manifest_eval(
    *,
    manifest_path: str | Path = DEFAULT_ALL_PUBLIC_PRO_FAILED_MANIFEST,
    out_dir: str | Path,
    case_ids: tuple[str, ...] = (),
    limit: int | None = None,
    dry_run: bool = False,
    client: OpenAICompatibleChatClient | None = None,
    model_name: str | None = None,
    skip_existing: bool = False,
    progress: bool = False,
) -> tuple[GuidedEvalRow, ...]:
    rows = load_failed_manifest(manifest_path)
    if case_ids:
        wanted = set(case_ids)
        rows = [row for row in rows if row["case_id"] in wanted]
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise ValueError("no cases selected")
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    result_rows: list[GuidedEvalRow] = []
    total = len(rows)
    for index, manifest_row in enumerate(rows, start=1):
        case = case_from_manifest_row(manifest_row)
        answer_key = answer_key_from_manifest_row(manifest_row)
        preset = select_preset(case.prompt, case_id=case.case_id)
        prompt = build_guided_final_prompt(case, preset=preset)
        prompt_path = root / f"{case.case_id}.prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        response_path = root / f"{case.case_id}.response.json"
        model_payload: dict[str, Any] | None = None
        error: str | None = None
        if progress:
            print(f"[{index}/{total}] {case.case_id} preset={preset}", file=sys.stderr, flush=True)
        if skip_existing and response_path.exists():
            stored = json.loads(response_path.read_text(encoding="utf-8"))
            content = stored.get("content")
            if isinstance(content, dict):
                model_payload = content
            stored_error = stored.get("error")
            error = stored_error if isinstance(stored_error, str) else None
            response_path_value = str(response_path)
            if progress:
                status = "error" if error else lexical_score(_optional_str(model_payload, "final_diagnosis") or "", answer_key)
                print(f"[{index}/{total}] skipped existing status={status}", file=sys.stderr, flush=True)
            result_rows.append(
                GuidedEvalRow(
                    case_id=case.case_id,
                    preset=preset,
                    expected_diagnosis=answer_key["diagnosis"],
                    expected_aliases=tuple(answer_key.get("aliases", ())),
                    model_final_diagnosis=_optional_str(model_payload, "final_diagnosis") if model_payload else None,
                    model_recommended_next_step=_optional_str(model_payload, "recommended_next_step") if model_payload else None,
                    lexical_score=lexical_score(_optional_str(model_payload, "final_diagnosis") or "", answer_key),
                    prompt_path=str(prompt_path),
                    response_path=response_path_value,
                    error=error,
                )
            )
            continue
        if dry_run:
            response_path_value = None
        else:
            if client is None:
                client = OpenAICompatibleChatClient.from_env(model=model_name)
            try:
                result = client.chat(prompt=prompt)
                try:
                    model_payload = parse_json_object(result.content)
                except Exception as exc:
                    error = f"model response was not valid JSON: {exc}"
                    response_path.write_text(
                        json.dumps(
                            {
                                "case_id": case.case_id,
                                "preset": preset,
                                "model": result.model,
                                "latency_ms": result.latency_ms,
                                "error": error,
                                "raw_content": result.content,
                                "raw": result.raw,
                            },
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    response_path_value = str(response_path)
                else:
                    response_path.write_text(
                        json.dumps(
                            {
                                "case_id": case.case_id,
                                "preset": preset,
                                "model": result.model,
                                "latency_ms": result.latency_ms,
                                "content": model_payload,
                                "raw": result.raw,
                            },
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    response_path_value = str(response_path)
            except Exception as exc:
                error = str(exc)
                response_path.write_text(
                    json.dumps({"case_id": case.case_id, "preset": preset, "error": error}, indent=2) + "\n",
                    encoding="utf-8",
                )
                response_path_value = str(response_path)
        model_final = _optional_str(model_payload, "final_diagnosis") if model_payload else None
        model_next = _optional_str(model_payload, "recommended_next_step") if model_payload else None
        result_rows.append(
            GuidedEvalRow(
                case_id=case.case_id,
                preset=preset,
                expected_diagnosis=answer_key["diagnosis"],
                expected_aliases=tuple(answer_key.get("aliases", ())),
                model_final_diagnosis=model_final,
                model_recommended_next_step=model_next,
                lexical_score=lexical_score(model_final or "", answer_key),
                prompt_path=str(prompt_path),
                response_path=response_path_value,
                error=error,
            )
        )
        if progress:
            status = "error" if error else result_rows[-1].lexical_score
            print(f"[{index}/{total}] completed status={status}", file=sys.stderr, flush=True)
    write_guided_results(root, tuple(result_rows))
    return tuple(result_rows)


def load_failed_manifest(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"manifest row must be object at {path}:{line_number}")
            rows.append(payload)
    return rows


def case_from_manifest_row(row: dict[str, Any]) -> ClinicalCase:
    return ClinicalCase(
        case_id=_required_str(row, "case_id"),
        title=_required_str(row, "title"),
        prompt=_required_str(row, "challenge_prompt"),
        metadata={
            "source_exclusion": {
                "title": row.get("title"),
                "pmcid": row.get("pmcid"),
                "doi": row.get("doi"),
            },
            "license_key": row.get("license_key"),
            "license_tier": row.get("license_tier"),
        },
    )


def answer_key_from_manifest_row(row: dict[str, Any]) -> dict[str, Any]:
    # Two manifest schemas exist: older batches store the answer as an ``answer_rest`` JSON string;
    # newer refined batches store a nested ``answer_key`` object. Support both so a schema change in
    # the generator does not silently strip the gold (which degraded the eighth-wave validation run).
    payload: dict[str, Any] | None = None
    answer_rest = row.get("answer_rest")
    if isinstance(answer_rest, str) and answer_rest.strip():
        parsed = json.loads(answer_rest)
        if isinstance(parsed, dict):
            payload = parsed
    if payload is None and isinstance(row.get("answer_key"), dict):
        payload = row["answer_key"]
    if not isinstance(payload, dict) or not isinstance(payload.get("diagnosis"), str):
        raise ValueError(f"row {row.get('case_id')} has no answer_rest/answer_key with a diagnosis")
    aliases = payload.get("aliases", [])
    if not isinstance(aliases, list):
        aliases = []
    return {
        "diagnosis": payload["diagnosis"],
        "aliases": tuple(alias for alias in aliases if isinstance(alias, str)),
        "next_management_step": payload.get("next_management_step"),
    }


def build_guided_final_prompt(case: ClinicalCase, *, preset: str) -> str:
    checklist = PRESET_CHECKLISTS[preset]
    payload = {
        "case_id": _model_visible_case_id(case.case_id),
        "harness_preset": preset,
        "expected_retrieval_bucket": f"{preset}_queries",
        "blocked_shortcuts": redacted_blocked_shortcuts(case),
        "required_preset_checklist": list(checklist),
        "challenge_prompt": case.prompt,
    }
    return (
        "You are running inside ClinicalHarness, a benchmark research harness. This is not clinical "
        "decision support and not patient-specific medical advice.\n\n"
        "Task: answer the diagnostic case using the challenge prompt and the ClinicalHarness preset checklist. "
        "The checklist tells you what discriminators must be considered before final closure. Do not search for "
        "or use source title, article title, DOI, PMCID, PMID, or exact prompt text.\n\n"
        "Return only strict JSON with:\n"
        "{\n"
        '  "problem_representation": "...",\n'
        '  "top_differential": [{"diagnosis": "...", "supporting_features": [], "refuting_features": []}],\n'
        '  "discriminator_summary": [{"discriminator": "...", "case_finding": "...", "direction": "..."}],\n'
        '  "final_diagnosis": "...",\n'
        '  "etiology": null,\n'
        '  "recommended_next_step": "...",\n'
        '  "confidence": "low|medium|high",\n'
        '  "uncertainty_or_missing_information": []\n'
        "}\n\n"
        f"Case packet:\n{json.dumps(payload, indent=2, sort_keys=True)}\n"
    )


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError("model response must be a JSON object")
    return payload


def lexical_score(model_final_diagnosis: str, answer_key: dict[str, Any]) -> str:
    normalized_model = _normalize(model_final_diagnosis)
    if not normalized_model:
        return "not_run"
    candidates = [
        answer_key["diagnosis"],
        *_derived_diagnosis_aliases(answer_key["diagnosis"]),
        *answer_key.get("aliases", ()),
    ]
    normalized_candidates = [_normalize(candidate) for candidate in candidates if isinstance(candidate, str)]
    for candidate in normalized_candidates:
        if candidate and (candidate in normalized_model or normalized_model in candidate):
            return "pass"
    for candidate in candidates:
        if isinstance(candidate, str) and _token_subset_match(model_final_diagnosis, candidate):
            return "pass"
    return "fail"


def _derived_diagnosis_aliases(diagnosis: str) -> tuple[str, ...]:
    normalized = _normalize(diagnosis)
    aliases: list[str] = []
    if "primary cns lymphoma" in normalized or "lymphomatous infiltration" in normalized:
        aliases.extend(("primary CNS lymphoma", "PCNSL", "CNS lymphoma", "lymphoma"))
    if "seronegative autoimmune encephalitis" in normalized or "probable autoimmune encephalitis" in normalized:
        aliases.extend(("seronegative autoimmune encephalitis", "probable autoimmune encephalitis"))
    if "tethered cord syndrome" in normalized:
        aliases.extend(("tethered cord syndrome", "tethered cord"))
    return tuple(aliases)


def _token_subset_match(model_final_diagnosis: str, candidate: str) -> bool:
    model_tokens = set(_meaningful_tokens(model_final_diagnosis))
    candidate_tokens = _meaningful_tokens(candidate)
    if len(candidate_tokens) < 2:
        return False
    return set(candidate_tokens).issubset(model_tokens)


def _meaningful_tokens(value: str) -> list[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "as",
        "associated",
        "due",
        "for",
        "in",
        "involving",
        "likely",
        "of",
        "or",
        "presenting",
        "probable",
        "suspected",
        "the",
        "to",
        "with",
    }
    tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", value)]
    return [token for token in tokens if len(token) > 1 and token not in stopwords]


def write_guided_results(root: Path, rows: tuple[GuidedEvalRow, ...]) -> None:
    jsonl_path = root / "guided_results.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")
    tsv_path = root / "guided_results.tsv"
    with tsv_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "case_id\tpreset\tlexical_score\texpected_diagnosis\tmodel_final_diagnosis\t"
            "model_recommended_next_step\terror\tprompt_path\tresponse_path\n"
        )
        for row in rows:
            handle.write(
                "\t".join(
                    _tsv_cell(value)
                    for value in (
                        row.case_id,
                        row.preset,
                        row.lexical_score,
                        row.expected_diagnosis,
                        row.model_final_diagnosis,
                        row.model_recommended_next_step,
                        row.error,
                        row.prompt_path,
                        row.response_path,
                    )
                )
                + "\n"
            )


def summarize_guided_results(rows: tuple[GuidedEvalRow, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.lexical_score] = counts.get(row.lexical_score, 0) + 1
    return counts


def _required_str(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"manifest row {key} must be a non-empty string")
    return value


def _optional_str(payload: dict[str, Any] | None, key: str) -> str | None:
    if not payload:
        return None
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _tsv_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\n", " ")
