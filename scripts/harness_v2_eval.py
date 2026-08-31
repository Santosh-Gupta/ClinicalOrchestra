"""Harness v2 evaluation: run an arm on a manifest and report PER-CUTOFF non-inferiority vs bare.

This file locks the success metric so the executor measures the right thing. The operational definition of
"only helps" is: for every n in 1..5, pass@n(arm) >= pass@n(bare), with harm counts reported. Tuning happens
on benchmark/development_solvable.jsonl (313 cases); the 68-case benchmark is touched only after a policy is
frozen.

Usage (once the pipeline is implemented):
    PYTHONPATH=src python3.11 scripts/harness_v2_eval.py <arm> <primary_model> <manifest> <out_dir>
    arm in {bare, self_critique, retrieval, full}
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from clinical_harness.harness_v2.config import HarnessV2Config
from clinical_harness.harness_v2.pipeline import run_manifest
from clinical_harness.model_client import OpenAICompatibleChatClient, OpenAIResponsesClient
from clinical_harness.ncbi import NcbiClient, NcbiConfig
from clinical_harness.retrieval_guided_eval import _gold_rank


import re


def _score_norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def per_cutoff_ladder(gold_ranks: list[int | None]) -> list[int]:
    """pass@n for n=1..5 given each case's gold rank (None or >5 = miss)."""
    def hit(r, k):
        return isinstance(r, int) and 1 <= r <= k
    return [sum(1 for r in gold_ranks if hit(r, k)) for k in range(1, 6)]


def dominance_report(bare_ranks: list[int | None], arm_ranks: list[int | None], strata: list[str] | None = None) -> dict:
    """Compute the per-cutoff comparison + harm/help counts. `bare_ranks` and `arm_ranks` are aligned per case
    (same judge, same run). Returns the report dict the executor prints and logs.

    Metric definitions (locked):
      - bare[n], arm[n]: pass@n ladders.
      - delta[n] = arm[n] - bare[n]; "only helps" requires delta[n] >= 0 for ALL n.
      - harm@n  = #cases with (bare hit @n) AND (arm miss @n)   <- must trend to 0, every one is audited.
      - help@n  = #cases with (arm hit @n) AND (bare miss @n).
      - net@n   = help@n - harm@n  (== delta[n]).
    Optionally stratify by review_status.
    """
    def hit(r, k):
        return isinstance(r, int) and 1 <= r <= k
    n = range(1, 6)
    bare = per_cutoff_ladder(bare_ranks)
    arm = per_cutoff_ladder(arm_ranks)
    harm = [sum(1 for b, a in zip(bare_ranks, arm_ranks) if hit(b, k) and not hit(a, k)) for k in n]
    help_ = [sum(1 for b, a in zip(bare_ranks, arm_ranks) if hit(a, k) and not hit(b, k)) for k in n]
    rep = {
        "n": list(n), "bare": bare, "arm": arm,
        "delta": [arm[i] - bare[i] for i in range(5)],
        "harm_at": harm, "help_at": help_,
        "only_helps": all(arm[i] - bare[i] >= 0 for i in range(5)),
        "cases": len(bare_ranks),
    }
    if strata is not None:
        groups: dict[str, tuple[list[int | None], list[int | None]]] = {}
        for label, bare_rank, arm_rank in zip(strata, bare_ranks, arm_ranks):
            key = label or "unknown"
            if key not in groups:
                groups[key] = ([], [])
            groups[key][0].append(bare_rank)
            groups[key][1].append(arm_rank)
        rep["strata"] = {
            key: dominance_report(values[0], values[1])
            for key, values in sorted(groups.items(), key=lambda item: item[0])
        }
    return rep


def score_arm_results(arm_result_path: str, judge_client, judge_votes: int) -> dict:
    """Load persisted ArmResults (bare_top5 + final_top5 per case), judge the gold's rank in each list with the
    SAME judge (reuse clinical_harness.retrieval_guided_eval._gold_rank), align per case, and return
    dominance_report(...). Judging both lists in this one pass guarantees within-run consistency."""
    path = Path(arm_result_path)
    if path.is_dir():
        path = path / "arm_results.jsonl"
    old_votes = os.environ.get("JUDGE_VOTES")
    os.environ["JUDGE_VOTES"] = str(judge_votes)
    bare_ranks: list[int | None] = []
    arm_ranks: list[int | None] = []
    strata: list[str] = []
    rows: list[dict[str, Any]] = []
    errors = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("error"):
                    errors += 1
                    bare_rank = None
                    final_rank = None
                else:
                    answer_key = _answer_key(row)
                    bare_list = _str_list(row.get("bare_top5"))
                    final_list = _str_list(row.get("final_top5"))
                    bare_rank = _gold_rank(
                        bare_list, answer_key, judge_client=judge_client, fallback_client=None,
                    )
                    # Judge stochasticity (DeepSeek-flash is not perfectly deterministic at temp 0) can give an
                    # identical list a different rank on a second call, manufacturing spurious deltas on cases
                    # the harness did not change. Reuse the bare rank whenever the final list is identical, so
                    # delta reflects the HARNESS effect only, not judge noise.
                    if [_score_norm(x) for x in bare_list] == [_score_norm(x) for x in final_list]:
                        final_rank = bare_rank
                    else:
                        final_rank = _gold_rank(
                            final_list, answer_key, judge_client=judge_client, fallback_client=None,
                        )
                bare_rank = bare_rank if isinstance(bare_rank, int) else None
                final_rank = final_rank if isinstance(final_rank, int) else None
                bare_ranks.append(bare_rank)
                arm_ranks.append(final_rank)
                strata.append(str(row.get("review_status") or "unknown"))
                rows.append(
                    {
                        "case_id": row.get("case_id"),
                        "review_status": row.get("review_status"),
                        "bare_rank": bare_rank,
                        "final_rank": final_rank,
                        "error": row.get("error"),
                    }
                )
    finally:
        if old_votes is None:
            os.environ.pop("JUDGE_VOTES", None)
        else:
            os.environ["JUDGE_VOTES"] = old_votes
    report = dominance_report(bare_ranks, arm_ranks, strata=strata)
    report["errors"] = errors
    score_path = path.with_name("scores.jsonl")
    with score_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    path.with_name("dominance_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    if len(sys.argv) < 5:
        raise SystemExit(__doc__)
    arm, primary_model_name, manifest, out_dir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    if arm not in {"bare", "self_critique", "retrieval", "full"}:
        raise SystemExit(f"unknown arm {arm!r}; expected bare/self_critique/retrieval/full")
    policy = os.environ.get("HARNESS_V2_POLICY") or ("P0" if arm == "bare" else "P1")
    config = HarnessV2Config(
        policy_level=policy,  # type: ignore[arg-type]
        use_self_critique=arm in {"self_critique", "full"},
        use_retrieval=arm in {"retrieval", "full"},
        retrieval_necessity_gate=os.environ.get("HARNESS_V2_RETRIEVAL_GATE", "1").lower() not in {"0", "false", "no"},
        primary_model=primary_model_name,
        reader_model=os.environ.get("HARNESS_V2_READER", "v4-flash"),
        judge_model=os.environ.get("HARNESS_V2_JUDGE", "v4-flash"),
        judge_votes=int(os.environ.get("JUDGE_VOTES", "3")),
        temperature=0.0,
    )
    setattr(config, "skip_existing", os.environ.get("HARNESS_V2_SKIP_EXISTING", "1"))
    setattr(config, "max_queries", int(os.environ.get("HARNESS_V2_MAX_QUERIES", "8")))
    setattr(config, "articles_per_query", int(os.environ.get("HARNESS_V2_ARTICLES_PER_QUERY", "3")))
    setattr(config, "max_reader_articles", int(os.environ.get("HARNESS_V2_MAX_READER_ARTICLES", "18")))

    primary_model = _build_model(primary_model_name)
    reader_model = _build_model(config.reader_model) if arm in {"retrieval", "full"} else None
    judge_client = _build_model(config.judge_model)
    ncbi_client = _build_ncbi() if arm in {"retrieval", "full"} else None
    run_manifest(
        manifest,
        arm,
        primary_model=primary_model,
        reader_model=reader_model,
        ncbi_client=ncbi_client,
        config=config,
        out_dir=out_dir,
    )
    report = score_arm_results(out_dir, judge_client=judge_client, judge_votes=config.judge_votes)
    print(json.dumps(report, indent=2, sort_keys=True))


_MODELS = {
    "gpt-5.4": ("https://api.openai.com/v1", ("XM_OPENAI_KEY", "OPENAI_API_KEY"), "gpt-5.4"),
    "gpt-5.5": ("https://api.openai.com/v1", ("XM_OPENAI_KEY", "OPENAI_API_KEY"), "gpt-5.5"),
    "gemini-3.1-pro": ("https://generativelanguage.googleapis.com/v1beta/openai", ("XM_GEMINI_KEY", "GEMINI_API_KEY"), "gemini-3.1-pro-preview"),
    "gemini-3.5-flash": ("https://generativelanguage.googleapis.com/v1beta/openai", ("XM_GEMINI_KEY", "GEMINI_API_KEY"), "gemini-3.5-flash"),
    "opus-4.8": ("https://api.anthropic.com/v1", ("XM_ANTHROPIC_KEY", "ANTHROPIC_API_KEY"), "claude-opus-4-8"),
    "v4-pro": ("https://api.deepseek.com", ("DEEPSEEK_API_KEY",), "deepseek-v4-pro"),
    "v4-flash": ("https://api.deepseek.com", ("DEEPSEEK_API_KEY",), "deepseek-v4-flash"),
}


def _build_model(name: str):
    if name not in _MODELS:
        raise ValueError(f"unknown model alias {name!r}; expected one of {sorted(_MODELS)}")
    base_url, key_names, model = _MODELS[name]
    api_key = _env_first(key_names)
    if base_url == "https://api.openai.com/v1" and model.startswith("gpt-5"):
        return OpenAIResponsesClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=float(os.environ.get("MODEL_TIMEOUT_SECONDS", "300")),
            max_retries=int(os.environ.get("MODEL_MAX_RETRIES", "4")),
            reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "medium"),
        )
    return OpenAICompatibleChatClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=float(os.environ.get("MODEL_TIMEOUT_SECONDS", "300")),
        max_retries=int(os.environ.get("MODEL_MAX_RETRIES", "4")),
    )


def _build_ncbi() -> NcbiClient:
    api_key = os.environ.get("NCBI_API_KEY")
    return NcbiClient(
        NcbiConfig(
            tool=os.environ.get("NCBI_TOOL", "ClinicalHarness"),
            email=os.environ.get("NCBI_EMAIL"),
            api_key=api_key,
            min_interval_seconds=float(os.environ.get("NCBI_SLEEP", "0.11" if api_key else "0.34")),
        )
    )


def _env_first(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    raise ValueError(f"missing API key; set one of: {', '.join(names)}")


def _answer_key(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("answer_key")
    if not isinstance(raw, dict) or not isinstance(raw.get("diagnosis"), str):
        raise ValueError(f"{row.get('case_id')}: missing answer_key.diagnosis")
    aliases = raw.get("aliases")
    if isinstance(aliases, str):
        aliases = [aliases]
    elif not isinstance(aliases, list):
        aliases = []
    return {"diagnosis": raw["diagnosis"], "aliases": tuple(a for a in aliases if isinstance(a, str))}


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


if __name__ == "__main__":
    main()
