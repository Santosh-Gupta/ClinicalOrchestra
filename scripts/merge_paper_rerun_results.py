#!/usr/bin/env python3
"""Merge targeted paper rerun results into a fresh JSONL artifact.

This script never edits the base result file in place. It keys rows by
`case_id`, replaces base rows only with complete rerun rows by default, and
prints before/after summaries so paper tables can be refreshed without losing
historical run artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


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


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def is_complete_result(row: dict) -> bool:
    """Return whether a rerun row is safe to prefer over the base row."""
    if row.get("error"):
        return False
    score = row.get("score")
    if score == "not_run":
        return False
    return bool(row.get("case_id"))


def row_by_case_id(rows: list[dict]) -> tuple[dict[str, dict], int, int]:
    keyed: dict[str, dict] = {}
    missing_case_id = 0
    duplicate_case_id = 0
    for row in rows:
        case_id = row.get("case_id")
        if not case_id:
            missing_case_id += 1
            continue
        if case_id in keyed:
            duplicate_case_id += 1
        keyed[case_id] = row
    return keyed, missing_case_id, duplicate_case_id


def score_summary(rows: Iterable[dict]) -> dict[str, int]:
    summary = {
        "rows": 0,
        "pass": 0,
        "fail": 0,
        "not_run": 0,
        "error": 0,
        "other_score": 0,
    }
    for row in rows:
        summary["rows"] += 1
        if row.get("error"):
            summary["error"] += 1
        score = row.get("score")
        if score in {"pass", "fail", "not_run"}:
            summary[score] += 1
        else:
            summary["other_score"] += 1
    return summary


def merge_rows(
    base_rows: list[dict],
    rerun_rows: list[dict],
    *,
    allow_incomplete_rerun: bool = False,
) -> tuple[list[dict], dict[str, int]]:
    base_by_id, base_missing_id, base_duplicates = row_by_case_id(base_rows)
    rerun_by_id, rerun_missing_id, rerun_duplicates = row_by_case_id(rerun_rows)

    merged_by_id = dict(base_by_id)
    stats = {
        "base_rows": len(base_rows),
        "rerun_rows": len(rerun_rows),
        "base_missing_case_id": base_missing_id,
        "rerun_missing_case_id": rerun_missing_id,
        "base_duplicate_case_id": base_duplicates,
        "rerun_duplicate_case_id": rerun_duplicates,
        "added": 0,
        "replaced": 0,
        "skipped_incomplete_rerun": 0,
    }

    for case_id, rerun_row in rerun_by_id.items():
        if not allow_incomplete_rerun and not is_complete_result(rerun_row):
            stats["skipped_incomplete_rerun"] += 1
            continue
        if case_id in merged_by_id:
            merged_by_id[case_id] = rerun_row
            stats["replaced"] += 1
        else:
            merged_by_id[case_id] = rerun_row
            stats["added"] += 1

    base_order = [row.get("case_id") for row in base_rows if row.get("case_id") in merged_by_id]
    seen = set()
    merged_rows: list[dict] = []
    for case_id in base_order:
        if case_id in seen:
            continue
        seen.add(case_id)
        merged_rows.append(merged_by_id[case_id])
    for case_id in rerun_by_id:
        if case_id not in seen and case_id in merged_by_id:
            seen.add(case_id)
            merged_rows.append(merged_by_id[case_id])

    stats["merged_rows"] = len(merged_rows)
    return merged_rows, stats


def print_summary(base_rows: list[dict], rerun_rows: list[dict], merged_rows: list[dict], stats: dict[str, int]) -> None:
    print("Base:", score_summary(base_rows))
    print("Rerun:", score_summary(rerun_rows))
    print("Merged:", score_summary(merged_rows))
    print("Merge stats:", stats)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True, help="Existing lane JSONL result file.")
    parser.add_argument("--rerun", type=Path, required=True, help="Fresh targeted rerun JSONL result file.")
    parser.add_argument("--out", type=Path, required=True, help="New merged JSONL result file.")
    parser.add_argument(
        "--allow-incomplete-rerun",
        action="store_true",
        help="Allow rerun rows with errors/not_run to replace base rows. Off by default.",
    )
    args = parser.parse_args(argv)

    if args.out.resolve() in {args.base.resolve(), args.rerun.resolve()}:
        print("--out must be a new file, not the base or rerun path", file=sys.stderr)
        return 2

    base_rows = read_jsonl(args.base)
    rerun_rows = read_jsonl(args.rerun)
    merged_rows, stats = merge_rows(
        base_rows,
        rerun_rows,
        allow_incomplete_rerun=args.allow_incomplete_rerun,
    )
    write_jsonl(args.out, merged_rows)
    print_summary(base_rows, rerun_rows, merged_rows, stats)
    print(f"Wrote merged results: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
