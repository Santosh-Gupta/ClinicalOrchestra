"""Bare-model baseline eval (no harness).

This is the model answering the case cold: just the redacted challenge prompt, no retrieval, no
preset checklist, no finalization gates, no rounds. It establishes the floor the harness has to
beat, and the Flash/Pro baselines define the gap the harness is meant to close.

Pipeline this supports:
  1. bare Flash over all cases (this module)            -> baseline pass/fail
  2. bare Pro over the Flash failures (this module)     -> ceiling / filter out unsolvable cases
  3. Flash WITH the harness (retrieval_guided_eval)     -> measured lift over the bare floor

Results reuse RetrievalGuidedEvalRow + the same scoring/judge/results writers, so all three stages
are directly comparable and share the same downstream summary/filter tooling.
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .guided_eval import (
    answer_key_from_manifest_row,
    case_from_manifest_row,
    load_failed_manifest,
    parse_json_object,
)
from .model_client import OpenAICompatibleChatClient
from .retrieval_guided_eval import (
    RetrievalGuidedEvalRow,
    _score_fields,
    summarize_retrieval_guided_results,
    write_retrieval_guided_results,
)
from .schemas import ClinicalCase


def build_baseline_prompt(case: ClinicalCase) -> str:
    """Minimal cold-diagnosis prompt: no checklist, no gates, no retrieved evidence."""
    return (
        "You are an expert physician taking a closed-book diagnostic exam. Read the clinical case "
        "and give your single best final diagnosis and the single best next step.\n"
        'Return ONLY JSON: {"final_diagnosis": "...", "recommended_next_step": "..."}\n\n'
        f"Case:\n{case.prompt}\n"
    )


def run_baseline_manifest_eval(
    *,
    manifest_path: str | Path,
    out_dir: str | Path,
    case_ids: tuple[str, ...] = (),
    limit: int | None = None,
    dry_run: bool = False,
    model_client: OpenAICompatibleChatClient | None = None,
    model_name: str | None = None,
    judge: bool = False,
    judge_client: OpenAICompatibleChatClient | None = None,
    judge_model: str | None = None,
    skip_existing: bool = False,
    progress: bool = False,
    concurrency: int = 1,
    max_tokens: int = 8192,
    temperature: float = 0.0,
) -> tuple[RetrievalGuidedEvalRow, ...]:
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
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
    if model_client is None and not dry_run:
        model_client = OpenAICompatibleChatClient.from_env(model=model_name)

    judge_fallback_client: OpenAICompatibleChatClient | None = None
    if judge and judge_client is None and not dry_run:
        resolved_judge_model = judge_model or os.getenv("DEEPSEEK_JUDGE_MODEL")
        if resolved_judge_model:
            judge_client = OpenAICompatibleChatClient.from_env(model=resolved_judge_model)
            judge_fallback_client = model_client
        else:
            judge_client = model_client
    total = len(rows)

    def _run_case(index: int, manifest_row: dict[str, Any]) -> RetrievalGuidedEvalRow:
        case = case_from_manifest_row(manifest_row)
        answer_key = answer_key_from_manifest_row(manifest_row)
        prompt_path = root / f"{case.case_id}.baseline_prompt.txt"
        response_path = root / f"{case.case_id}.baseline_response.json"
        if progress:
            print(f"[{index}/{total}] baseline {case.case_id}", file=sys.stderr, flush=True)

        if skip_existing and response_path.exists():
            stored = json.loads(response_path.read_text(encoding="utf-8"))
            content = stored.get("content")
            final = content.get("final_diagnosis") if isinstance(content, dict) else None
            error = stored.get("error") if isinstance(stored.get("error"), str) else None
            return _baseline_row(case, answer_key, final, error, prompt_path, response_path, judge, judge_client, judge_fallback_client)

        prompt = build_baseline_prompt(case)
        prompt_path.write_text(prompt, encoding="utf-8")
        final: str | None = None
        error: str | None = None
        if not dry_run:
            assert model_client is not None
            try:
                # Reasoning models (e.g. deepseek-v4-pro) spend completion tokens on hidden
                # reasoning first; too small a budget leaves zero tokens for the answer JSON and
                # returns empty content (finish_reason=length). Keep this generous.
                result = model_client.chat(prompt=prompt, temperature=temperature, max_tokens=max_tokens)
                payload = parse_json_object(result.content)
                value = payload.get("final_diagnosis")
                final = value if isinstance(value, str) else None
                response_path.write_text(
                    json.dumps(
                        {"content": payload, "raw": result.raw, "raw_latency_ms": result.latency_ms},
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            except Exception as exc:  # noqa: BLE001 - record per-case failure, keep the batch going.
                error = str(exc)
                response_path.write_text(json.dumps({"error": error}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        row = _baseline_row(case, answer_key, final, error, prompt_path, response_path, judge, judge_client, judge_fallback_client)
        if progress:
            status = "error" if error else (row.score or row.lexical_score)
            print(f"[{index}/{total}] baseline {case.case_id} status={status}", file=sys.stderr, flush=True)
        return row

    if concurrency > 1 and total > 1:
        ordered: list[RetrievalGuidedEvalRow | None] = [None] * total
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            future_to_index = {
                pool.submit(_run_case, index, manifest_row): index - 1
                for index, manifest_row in enumerate(rows, start=1)
            }
            for future in as_completed(future_to_index):
                ordered[future_to_index[future]] = future.result()
        result_rows = [row for row in ordered if row is not None]
    else:
        result_rows = [_run_case(index, manifest_row) for index, manifest_row in enumerate(rows, start=1)]

    write_retrieval_guided_results(root, tuple(result_rows))
    return tuple(result_rows)


def _baseline_row(
    case: ClinicalCase,
    answer_key: dict[str, Any],
    final: str | None,
    error: str | None,
    prompt_path: Path,
    response_path: Path,
    judge: bool,
    judge_client: OpenAICompatibleChatClient | None,
    judge_fallback_client: OpenAICompatibleChatClient | None,
) -> RetrievalGuidedEvalRow:
    return RetrievalGuidedEvalRow(
        case_id=case.case_id,
        preset="bare_no_harness",
        expected_diagnosis=answer_key["diagnosis"],
        model_final_diagnosis=final,
        query_count=0,
        evidence_count=0,
        synthesis_path=None,
        prompt_path=str(prompt_path),
        query_path="",
        evidence_path="",
        response_path=str(response_path) if response_path.exists() else None,
        error=error,
        **_score_fields(final, answer_key, judge_client=judge_client if judge else None, fallback_client=judge_fallback_client),
    )


def summarize_baseline_results(rows: tuple[RetrievalGuidedEvalRow, ...]) -> dict[str, int]:
    return summarize_retrieval_guided_results(rows)
