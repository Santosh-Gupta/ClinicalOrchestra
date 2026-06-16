"""Load DeepSeek failure cases and build retrieval-analysis packets."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schemas import JsonSerializableMixin


NEUROLOGYBM_ROOT = Path("/Users/santoshg/Coding/NeurologyBM")
READY_ROOT = NEUROLOGYBM_ROOT / "data/pmc/processed/public_case_challenge_splits"
REFINED_ROOT = READY_ROOT / "refined"
DEEPSEEK_RUNS_ROOT = READY_ROOT / "deepseek_runs"

DEFAULT_READY_MANIFEST = REFINED_ROOT / "ready_llm_eval_manifest_20260611.jsonl"
DEFAULT_STILL_FAILED_IDS = REFINED_ROOT / "ready_38_flash_fail_pro_still_fail_case_ids_20260612.txt"
DEFAULT_PRO_COMPARISON = REFINED_ROOT / "ready_38_flash_fail_pro_rescue_comparison_20260612.tsv"
DEFAULT_PRO_RESULTS = DEEPSEEK_RUNS_ROOT / "deepseek_public_20260612T000541Z/results.tsv"
DEFAULT_PRO_SCORES = DEEPSEEK_RUNS_ROOT / "deepseek_public_scores_20260612T001940Z/scores.tsv"
DEFAULT_FLASH_RESULTS = DEEPSEEK_RUNS_ROOT / "deepseek_public_20260611T224853Z/results.tsv"
DEFAULT_FLASH_SCORES = DEEPSEEK_RUNS_ROOT / "deepseek_public_scores_20260611T230530Z/scores.tsv"

DEFAULT_NEURO_PSYCH_CASE_IDS = (
    "transformed_PMC10399123",
    "transformed_PMC10409533",
    "transformed_PMC10540759",
    "transformed_PMC12581184",
    "transformed_PMC3214133",
    "transformed_PMC5516732",
    "transformed_PMC6179031",
    "transformed_PMC7678886",
    "transformed_PMC8115684",
    "transformed_PMC8143662",
)


@dataclass(frozen=True)
class DeepSeekFailurePaths:
    ready_manifest: Path = DEFAULT_READY_MANIFEST
    still_failed_ids: Path = DEFAULT_STILL_FAILED_IDS
    pro_comparison: Path = DEFAULT_PRO_COMPARISON
    pro_results: Path = DEFAULT_PRO_RESULTS
    pro_scores: Path = DEFAULT_PRO_SCORES
    flash_results: Path = DEFAULT_FLASH_RESULTS
    flash_scores: Path = DEFAULT_FLASH_SCORES


@dataclass(frozen=True)
class FailureAnalysisPacket(JsonSerializableMixin):
    case_id: str
    cluster_hint: str
    diagnostic_agent_input: dict[str, Any]
    evaluator_only: dict[str, Any]
    failed_model_outputs: dict[str, Any]
    comparison_prompt: str


def load_failure_analysis_packets(
    paths: DeepSeekFailurePaths = DeepSeekFailurePaths(),
    *,
    subset: str = "all",
    case_ids: tuple[str, ...] = (),
    max_answer_rest_chars: int = 5000,
) -> list[FailureAnalysisPacket]:
    """Load the joined failure set and build per-case Pro-analysis packets."""

    manifest_by_id = _read_jsonl_by_case_id(paths.ready_manifest)
    still_failed_ids = _read_case_ids(paths.still_failed_ids)
    selected_ids = _select_case_ids(still_failed_ids, subset=subset, case_ids=case_ids)

    pro_results = _read_tsv_by_case_id(paths.pro_results)
    pro_scores = _read_tsv_by_case_id(paths.pro_scores)
    flash_results = _read_tsv_by_case_id(paths.flash_results)
    flash_scores = _read_tsv_by_case_id(paths.flash_scores)
    pro_comparison = _read_tsv_by_case_id(paths.pro_comparison)

    packets: list[FailureAnalysisPacket] = []
    for case_id in selected_ids:
        manifest = _required_case(manifest_by_id, case_id, paths.ready_manifest)
        packet = build_failure_analysis_packet(
            case_id=case_id,
            manifest=manifest,
            flash_result=flash_results.get(case_id, {}),
            flash_score=flash_scores.get(case_id, {}),
            pro_result=pro_results.get(case_id, {}),
            pro_score=pro_scores.get(case_id, {}),
            pro_comparison=pro_comparison.get(case_id, {}),
            max_answer_rest_chars=max_answer_rest_chars,
        )
        packets.append(packet)
    return packets


def write_packets_jsonl(packets: list[FailureAnalysisPacket], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for packet in packets:
            handle.write(json.dumps(packet.to_dict(), sort_keys=True) + "\n")


def build_failure_analysis_packet(
    *,
    case_id: str,
    manifest: dict[str, Any],
    flash_result: dict[str, Any],
    flash_score: dict[str, Any],
    pro_result: dict[str, Any],
    pro_score: dict[str, Any],
    pro_comparison: dict[str, Any],
    max_answer_rest_chars: int = 5000,
) -> FailureAnalysisPacket:
    title = _text(manifest.get("title"))
    answer_rest = _truncate(_text(manifest.get("answer_rest")), max_answer_rest_chars)
    diagnostic_agent_input = {
        "case_id": case_id,
        "challenge_prompt": _text(manifest.get("challenge_prompt")),
        "available_fields": [
            "challenge_prompt",
        ],
        "blocked_retrieval_shortcuts": _blocked_shortcuts(manifest),
    }
    evaluator_only = {
        "expected_key_answer": _first_nonempty(
            pro_score.get("expected_key_answer"),
            flash_score.get("expected_key_answer"),
            _answer_key_from_manifest(manifest),
        ),
        "expected_next_step": _first_nonempty(
            pro_score.get("expected_next_step"),
            flash_score.get("expected_next_step"),
        ),
        "source_title": title,
        "source_journal": _text(manifest.get("journal")),
        "source_pmcid": _text(manifest.get("pmcid")),
        "source_doi": _text(manifest.get("doi")),
        "license_key": _text(manifest.get("license_key")),
        "license_tier": _text(manifest.get("license_tier")),
        "paper_outcome_or_discussion_excerpt": answer_rest,
        "answer_rest_truncated": len(_text(manifest.get("answer_rest"))) > len(answer_rest),
    }
    failed_model_outputs = {
        "flash": _model_output_summary(flash_result, flash_score),
        "pro": _model_output_summary(pro_result, pro_score),
        "pro_rescue_comparison": _compact_dict(pro_comparison),
    }
    cluster_hint = _cluster_hint(case_id, manifest, failed_model_outputs, evaluator_only)
    return FailureAnalysisPacket(
        case_id=case_id,
        cluster_hint=cluster_hint,
        diagnostic_agent_input=diagnostic_agent_input,
        evaluator_only=evaluator_only,
        failed_model_outputs=failed_model_outputs,
        comparison_prompt=build_comparison_prompt(
            case_id=case_id,
            cluster_hint=cluster_hint,
            diagnostic_agent_input=diagnostic_agent_input,
            evaluator_only=evaluator_only,
            failed_model_outputs=failed_model_outputs,
        ),
    )


def build_comparison_prompt(
    *,
    case_id: str,
    cluster_hint: str,
    diagnostic_agent_input: dict[str, Any],
    evaluator_only: dict[str, Any],
    failed_model_outputs: dict[str, Any],
) -> str:
    """Build a prompt for DeepSeek Pro to design retrieval scaffolding."""

    payload = {
        "case_id": case_id,
        "cluster_hint": cluster_hint,
        "diagnostic_agent_input": diagnostic_agent_input,
        "evaluator_only": evaluator_only,
        "failed_model_outputs": failed_model_outputs,
    }
    return (
        "You are designing a retrieval-guided diagnostic workflow for ClinicalHarness.\n"
        "Analyze why single-call DeepSeek failed and propose retrieval steps that would "
        "help deepseek-v4-flash solve the case without shortcutting to the original article.\n\n"
        "Rules:\n"
        "- Do not propose searches using source title, DOI, PMCID, article title, or exact quoted prompt text.\n"
        "- Separate diagnostic-agent-visible information from evaluator-only answer/source material.\n"
        "- Focus on knowledge gaps: criteria, discriminating tests, imaging/pathology features, mimics, guidelines, "
        "case-series tables, and disease-specific review knowledge.\n"
        "- Store structured reasoning artifacts, not hidden chain-of-thought.\n\n"
        "Return strict JSON with these fields:\n"
        "{\n"
        '  "case_id": "...",\n'
        '  "cluster": "neuro_psych|rare_tumor_pathology|infection_inflammatory|derm_drug_genital|other",\n'
        '  "failure_analysis": {\n'
        '    "organ_system_alignment": "right|adjacent|wrong|unclear",\n'
        '    "anchor_or_mimic": "...",\n'
        '    "missed_discriminators": ["..."],\n'
        '    "knowledge_gap_type": ["criteria|imaging|pathology_ihc|guideline|case_series|syndrome_review|test_interpretation|ontology"]\n'
        "  },\n"
        '  "ideal_retrieval_sequence": [\n'
        "    {\n"
        '      "step": 1,\n'
        '      "purpose": "...",\n'
        '      "query_templates": ["..."],\n'
        '      "target_source_type": "review|guideline|case_series|criteria|pathology_table|imaging_review|pubmed_case_reports",\n'
        '      "evidence_to_extract": ["..."],\n'
        '      "differential_update_rule": "..."\n'
        "    }\n"
        "  ],\n"
        '  "generalizable_rule": "...",\n'
        '  "first_harness_scaffold": {\n'
        '    "required_controller_stage": "...",\n'
        '    "retrieval_guard_needed": true,\n'
        '    "scoring_signal": "..."\n'
        "  }\n"
        "}\n\n"
        "Case packet:\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n"
    )


def _read_jsonl_by_case_id(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            case_id = row.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                raise ValueError(f"missing case_id in {path}:{line_number}")
            rows[case_id] = row
    return rows


def _read_tsv_by_case_id(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            case_id = row.get("case_id", "")
            if case_id:
                rows[case_id] = dict(row)
        return rows


def _read_case_ids(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8") as handle:
        return tuple(line.strip() for line in handle if line.strip())


def _select_case_ids(
    still_failed_ids: tuple[str, ...],
    *,
    subset: str,
    case_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if case_ids:
        allowed = set(still_failed_ids)
        missing = [case_id for case_id in case_ids if case_id not in allowed]
        if missing:
            raise ValueError(f"case ids are not in the still-failed set: {', '.join(missing)}")
        return case_ids
    if subset == "all":
        return still_failed_ids
    if subset == "neuro_psych":
        allowed = set(still_failed_ids)
        return tuple(case_id for case_id in DEFAULT_NEURO_PSYCH_CASE_IDS if case_id in allowed)
    raise ValueError("subset must be 'all' or 'neuro_psych'")


def _required_case(
    manifest_by_id: dict[str, dict[str, Any]],
    case_id: str,
    path: Path,
) -> dict[str, Any]:
    try:
        return manifest_by_id[case_id]
    except KeyError as exc:
        raise ValueError(f"case id {case_id!r} is not present in {path}") from exc


def _model_output_summary(result: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": _first_nonempty(result.get("model"), score.get("model")),
        "final_diagnosis": _text(result.get("final_diagnosis")),
        "top_differential": _json_or_text(result.get("top_differential")),
        "recommended_next_step": _text(result.get("recommended_next_step")),
        "confidence": _text(result.get("confidence")),
        "evidence_summary": _json_or_text(result.get("evidence_summary")),
        "uncertainty_or_missing_information": _json_or_text(result.get("uncertainty_or_missing_information")),
        "score_status": _text(score.get("score_status")),
        "diagnosis_status": _text(score.get("diagnosis_status")),
        "next_step_status": _text(score.get("next_step_status")),
        "rationale_status": _text(score.get("rationale_status")),
        "judge_rationale": _first_nonempty(score.get("rationale"), result.get("judge_rationale")),
    }


def _blocked_shortcuts(manifest: dict[str, Any]) -> dict[str, str]:
    return {
        "source_title": _text(manifest.get("title")),
        "doi": _text(manifest.get("doi")),
        "pmcid": _text(manifest.get("pmcid")),
        "exact_prompt_text": "blocked",
    }


def _answer_key_from_manifest(manifest: dict[str, Any]) -> str:
    answer_rest = manifest.get("answer_rest")
    if isinstance(answer_rest, dict):
        return _text(answer_rest.get("diagnosis"))
    if isinstance(answer_rest, str) and answer_rest.strip().startswith("{"):
        try:
            parsed = json.loads(answer_rest)
        except json.JSONDecodeError:
            return ""
        if isinstance(parsed, dict):
            return _text(parsed.get("diagnosis"))
    return ""


def _cluster_hint(
    case_id: str,
    manifest: dict[str, Any],
    failed_model_outputs: dict[str, Any],
    evaluator_only: dict[str, Any],
) -> str:
    if case_id in DEFAULT_NEURO_PSYCH_CASE_IDS:
        return "neuro_psych"
    text = " ".join(
        [
            _text(manifest.get("challenge_prompt")),
            _text(evaluator_only.get("expected_key_answer")),
            _text(failed_model_outputs.get("pro", {}).get("judge_rationale")),
        ]
    ).lower()
    if any(term in text for term in ("tumor", "sarcoma", "carcinoma", "lymphoma", "ihc", "histopath")):
        return "rare_tumor_pathology"
    if any(term in text for term in ("infection", "sepsis", "inflammatory", "fever", "abscess")):
        return "infection_inflammatory"
    if any(term in text for term in ("skin", "rash", "penile", "genital", "drug", "derm")):
        return "derm_drug_genital"
    return "other"


def _compact_dict(row: dict[str, Any]) -> dict[str, str]:
    return {str(key): _text(value) for key, value in row.items() if _text(value)}


def _json_or_text(value: Any) -> Any:
    text = _text(value)
    if not text:
        return ""
    if text[0] in "[{":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _truncate(value: str, max_chars: int) -> str:
    if max_chars < 1 or len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
