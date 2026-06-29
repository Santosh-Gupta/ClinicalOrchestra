#!/usr/bin/env python3
"""Summarize paper-critical run artifacts for the LM4Sci submission.

This script is read-only. It reports which result lanes exist, how many rows
they contain, pass/fail/not_run/error counts, and rank-based pass@1/pass@5 where
`gold_rank` is available.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


MANIFEST = Path("data/eval/crossmodel/flash_fail_postcutoff.jsonl")


@dataclass(frozen=True)
class Lane:
    name: str
    path: Path
    kind: str
    status: str
    caveat: str


LANES = [
    Lane(
        "gemini-3.5-flash bare",
        Path("data/eval/crossmodel/gemini-3.5-flash_flashfail/retrieval_guided_results.jsonl"),
        "bare",
        "secondary",
        "single-answer rescue set",
    ),
    Lane(
        "gemini-3.1-pro bare",
        Path("data/eval/crossmodel_merged/gemini-3.1-pro_flashfail_lm4sci/retrieval_guided_results.jsonl"),
        "bare",
        "secondary",
        "single-answer rescue set; merged with one clean 2026-06-23 rerun",
    ),
    Lane(
        "opus-4.7 bare",
        Path("data/eval/crossmodel/opus-4.7_flashfail/retrieval_guided_results.jsonl"),
        "bare",
        "secondary",
        "provider-default temperature; audit-cleaned + mended re-scored",
    ),
    Lane(
        "opus-4.8 bare",
        Path("data/eval/crossmodel/opus-4.8_flashfail/retrieval_guided_results.jsonl"),
        "bare",
        "secondary",
        "provider-default temperature; multi-seed preferred",
    ),
    Lane(
        "gpt-5.4 bare Responses",
        Path("data/eval/crossmodel/gpt-5.4_flashfail_responses_medium/retrieval_guided_results.jsonl"),
        "bare",
        "secondary",
        "Responses API; medium reasoning; provider-default temp fallback",
    ),
    Lane(
        "gpt-5.5 bare Responses",
        Path("data/eval/crossmodel/gpt-5.5_flashfail_responses_medium/retrieval_guided_results.jsonl"),
        "bare",
        "secondary",
        "Responses API; medium reasoning; provider-default temp fallback; audit-cleaned + mended",
    ),
    Lane(
        "v4-pro answerer + v4-pro reader",
        Path("data/eval/crossmodel_harness_merged/v4-pro__reader_v4-pro_lm4sci/retrieval_guided_results.jsonl"),
        "harness",
        "secondary",
        "rank-based counts only; audit-cleaned + mended re-scored",
    ),
    Lane(
        "v4-pro answerer + v4-flash reader",
        Path("data/eval/crossmodel_harness_merged/v4-pro__reader_v4-flash_lm4sci/retrieval_guided_results.jsonl"),
        "harness",
        "secondary",
        "rank-based counts only; audit-cleaned + mended re-scored",
    ),
    Lane(
        "gemini-3.1-pro answerer + v4-pro reader",
        Path("data/eval/crossmodel_harness_merged/gemini-3.1-pro__reader_v4-pro_lm4sci_compact/retrieval_guided_results.jsonl"),
        "harness",
        "secondary",
        "rank-based counts only; audit-cleaned + mended re-scored",
    ),
    Lane(
        "opus-4.8 answerer + v4-pro reader",
        Path("data/eval/crossmodel_harness/opus-4.8__reader_v4-pro/retrieval_guided_results.jsonl"),
        "harness",
        "secondary",
        "rank-based counts only; complete on the cleaned 68",
    ),
    Lane(
        "gemini-3.5-flash answerer + v4-pro reader",
        Path("data/eval/crossmodel_harness/gemini-3.5-flash__reader_v4-pro/retrieval_guided_results.jsonl"),
        "harness",
        "secondary",
        "rank-based counts only; complete on the cleaned 68",
    ),
    Lane(
        "opus-4.7 answerer + v4-pro reader",
        Path("data/eval/crossmodel_harness/opus-4.7__reader_v4-pro/retrieval_guided_results.jsonl"),
        "harness",
        "secondary",
        "rank-based counts only; complete on the cleaned 68 (backfilled)",
    ),
    Lane(
        "gpt-5.5 answerer + v4-pro reader",
        Path("data/eval/crossmodel_harness/gpt-5.5__reader_v4-pro_responses_medium/retrieval_guided_results.jsonl"),
        "harness",
        "secondary",
        "rank-based counts only; complete on the cleaned 68 (backfilled)",
    ),
    Lane(
        "gpt-5.4 answerer + v4-pro reader",
        Path("data/eval/crossmodel_harness/gpt-5.4__reader_v4-pro/retrieval_guided_results.jsonl"),
        "harness",
        "secondary",
        "rank-based counts only; complete on the cleaned 68 (backfilled)",
    ),
]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def manifest_count() -> int:
    return len(read_jsonl(MANIFEST))


def score_counts(rows: Iterable[dict]) -> dict[str, int]:
    counts = {"pass": 0, "fail": 0, "not_run": 0, "rows_with_error": 0, "other": 0}
    for row in rows:
        if row.get("error"):
            counts["rows_with_error"] += 1
        score = row.get("score")
        if score in counts:
            counts[score] += 1
        else:
            counts["other"] += 1
    return counts


def rank_counts(rows: Iterable[dict]) -> tuple[int, int, int]:
    pass_at_1 = 0
    pass_at_5 = 0
    ranked = 0
    for row in rows:
        rank = row.get("gold_rank")
        if isinstance(rank, int):
            ranked += 1
            if rank <= 1:
                pass_at_1 += 1
            if rank <= 5:
                pass_at_5 += 1
    return pass_at_1, pass_at_5, ranked


def summarize_lane(lane: Lane, denominator: int) -> dict[str, object]:
    rows = read_jsonl(lane.path)
    counts = score_counts(rows)
    pass_at_1, pass_at_5, ranked = rank_counts(rows)
    missing_rows = max(denominator - len(rows), 0)
    return {
        "name": lane.name,
        "kind": lane.kind,
        "status": lane.status,
        "path": str(lane.path),
        "exists": lane.path.exists(),
        "rows": len(rows),
        "missing_rows": missing_rows,
        "score_pass": counts["pass"],
        "score_fail": counts["fail"],
        "score_not_run": counts["not_run"],
        "rows_with_error": counts["rows_with_error"],
        "ranked_rows": ranked,
        "pass_at_1": pass_at_1,
        "pass_at_5": pass_at_5,
        "caveat": lane.caveat,
    }


def print_table(rows: list[dict[str, object]], denominator: int) -> None:
    print(f"Manifest denominator: {denominator}")
    print()
    header = [
        "lane",
        "kind",
        "status",
        "rows",
        "missing",
        "score_pass",
        "score_fail",
        "not_run",
        "rows_with_error",
        "p@1",
        "p@5",
        "caveat",
    ]
    print("\t".join(header))
    for row in rows:
        print(
            "\t".join(
                str(value)
                for value in [
                    row["name"],
                    row["kind"],
                    row["status"],
                    row["rows"],
                    row["missing_rows"],
                    row["score_pass"],
                    row["score_fail"],
                    row["score_not_run"],
                    row["rows_with_error"],
                    row["pass_at_1"],
                    row["pass_at_5"],
                    row["caveat"],
                ]
            )
        )


def summarize_all() -> tuple[int, list[dict[str, object]]]:
    denominator = manifest_count()
    summaries = [summarize_lane(lane, denominator) for lane in LANES]
    return denominator, summaries


def markdown_lane_table(rows: list[dict[str, object]]) -> str:
    lines = [
        "| Lane | Kind | Status | Rows | Missing | Score pass | Score fail | not_run | rows_with_error | p@1 | p@5 | Caveat |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(value)
                for value in [
                    row["name"],
                    row["kind"],
                    row["status"],
                    row["rows"],
                    row["missing_rows"],
                    row["score_pass"],
                    row["score_fail"],
                    row["score_not_run"],
                    row["rows_with_error"],
                    row["pass_at_1"],
                    row["pass_at_5"],
                    row["caveat"],
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_markdown() -> str:
    denominator, summaries = summarize_all()
    lane_table = markdown_lane_table(summaries)
    return "\n".join(
        [
            "# LM4Sci Run Status (2026-06-25)",
            "",
            "Generated from:",
            "",
            "```bash",
            "python3.11 scripts/paper_run_status.py --markdown",
            "```",
            "",
            "Targeted rerun manifests are generated by:",
            "",
            "```bash",
            "python3.11 scripts/export_paper_rerun_manifests.py",
            "```",
            "",
            "Current rerun manifest summary:",
            "`data/eval/rerun_manifests/lm4sci_20260623/README.md`.",
            "",
            f"The {denominator}-case hard set is `data/eval/crossmodel/flash_fail_postcutoff.jsonl`. This is a",
            f"failure-selected rescue set: DeepSeek V4 Flash is 0/{denominator} by construction, so these rows are not a neutral",
            "leaderboard.",
            "",
            "The compact final table for the paper is summarized in",
            "`docs/FINAL_RESULTS_20260625.md` and `docs/paper_workshop_compact_20260623.md` §5.4.",
            "",
            "## Current Lane Status",
            "",
            lane_table,
            "",
            "## LM4Sci Rerun Priorities",
            "",
            "No required rerun remains for the paper's main single-seed final table. Optional follow-up work:",
            "",
            "1. Run multi-seed/default-temperature checks for Opus and GPT-5.x if budget permits; use them to",
            "   avoid overclaiming fine model ordering within the variance floor.",
            "2. If any new lane is added or re-run, regenerate this status doc and re-check",
            "   `docs/FINAL_RESULTS_20260625.md`, the compact draft, and `main.tex` together.",
            "3. Treat old 81-case/pre-audit artifacts and rerun attempts as historical unless explicitly used for",
            "   an ablation or provenance note.",
            "",
            "## Rerun Manifest Summary",
            "",
            "The authoritative targeted-rerun list is generated separately in",
            "`data/eval/rerun_manifests/lm4sci_20260623/README.md`. Regenerate it with",
            "`python3.11 scripts/export_paper_rerun_manifests.py` after any lane changes; do not maintain a second",
            "hand-edited manifest table here.",
            "",
            "## Reporting Rules",
            "",
            "- For bare lanes, current values are single-answer rescue counts, not pass@5.",
            "- For harness lanes, use rank-based `gold_rank` counts (`p@1`, `p@5`), not raw `score=pass`.",
            "- Treat `not_run` rows as incomplete cells. They often also have an error message; `rows_with_error`",
            "  records that implementation detail.",
            "- The current paper table uses the audit-cleaned 68-case set after ADR-049; older 81-case values are superseded.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", action="store_true", help="Print the Markdown status document.")
    parser.add_argument("--write-markdown", type=Path, help="Write the Markdown status document.")
    args = parser.parse_args(argv)

    if args.markdown or args.write_markdown:
        rendered = render_markdown()
        if args.write_markdown:
            args.write_markdown.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return 0

    denominator, summaries = summarize_all()
    print_table(summaries, denominator)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
