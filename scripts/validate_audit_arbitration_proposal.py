#!/usr/bin/env python3
"""Validate the audit arbitration proposal before user approval/application.

The proposal is intentionally human-readable, but its counts are easy to make
stale. This script checks the document against the audit cross-reference file:
coverage, action counts, mend-operation coverage, and expected denominator math.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path


DEFAULT_PROPOSAL = Path("docs/AUDIT_ARBITRATION_PROPOSAL_20260623.md")
DEFAULT_CROSSREF = Path("data/eval/audit/_crossref.csv")
DEFAULT_MANIFEST = Path("data/eval/crossmodel/flash_fail_postcutoff.jsonl")

# Mend-maximal slate (2026-06-24): two former DROPs (PMC13167955 leak3, PMC13154095
# leak2) converted to source-grounded MENDs, and the former REVIEW case (PMC13149065)
# resolved to DROP. See docs/AUDIT_ARBITRATION_PROPOSAL_20260623.md.
EXPECTED_HIGH_COUNTS = Counter({"DROP": 5, "MEND": 8, "KEEP": 22})
EXPECTED_TIER2_LEAK_COUNTS = Counter({"DROP": 5, "MEND": 3, "KEEP": 4})
EXPECTED_TIER2_INSUFF_COUNTS = Counter({"DROP": 3, "KEEP": 8})
EXPECTED_COMBINED_COUNTS = Counter({"DROP": 13, "MEND": 11, "KEEP": 34})


def read_crossref(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def manifest_count(path: Path) -> int:
    # The proposal's denominator math is relative to the ORIGINAL (pre-cleanup) manifest.
    # Once the cleanup is applied, the live manifest is the cleaned set, so prefer the
    # pre-cleanup backup when present to keep the original count stable.
    backup = path.with_suffix(path.suffix + ".pre_audit_cleanup.bak")
    source = backup if backup.exists() else path
    with source.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def section_text(markdown: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*$"
    match = re.search(pattern, markdown, flags=re.MULTILINE)
    if not match:
        return ""
    next_heading = re.search(r"^## ", markdown[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(markdown)
    return markdown[match.end() : end]


def table_rows(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        if re.fullmatch(r"\|[\s:|\-]+\|", stripped):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] == "case_id":
            continue
        rows.append(cells)
    return rows


def action_rows(section: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cells in table_rows(section):
        if len(cells) < 4:
            continue
        action = cells[2]
        if action not in {"DROP", "MEND", "KEEP", "REVIEW_FOR_MEND_OR_DROP"}:
            continue
        rows.append(
            {
                "case_id": cells[0],
                "tier": cells[1],
                "action": action,
                "justification": cells[3],
            }
        )
    return rows


def operation_case_ids(section: str) -> set[str]:
    ids: set[str] = set()
    for cells in table_rows(section):
        if len(cells) >= 3 and cells[0].startswith("transformed_"):
            ids.add(cells[0])
    return ids


def parse_summary_count(markdown: str, label: str) -> int | None:
    match = re.search(rf"- {re.escape(label)}:\s*(\d+)", markdown)
    return int(match.group(1)) if match else None


def compare_counts(
    errors: list[str], label: str, actual: Counter[str], expected: Counter[str]
) -> None:
    if actual != expected:
        errors.append(f"{label} action counts {dict(actual)} != expected {dict(expected)}")


def validate(proposal: Path, crossref: Path, manifest: Path) -> list[str]:
    errors: list[str] = []
    if not proposal.exists():
        return [f"missing proposal: {proposal}"]
    if not crossref.exists():
        return [f"missing crossref: {crossref}"]
    if not manifest.exists():
        return [f"missing manifest: {manifest}"]

    markdown = proposal.read_text(encoding="utf-8")
    cross_rows = read_crossref(crossref)
    manifest_n = manifest_count(manifest)
    cross_case_ids = {row["case_id"] for row in cross_rows}
    high_expected = {
        row["case_id"]
        for row in cross_rows
        if int(row["leak_votes"]) == 3 or int(row["insuff_votes"]) == 3
    }
    all_work_expected = {
        row["case_id"]
        for row in cross_rows
        if int(row["leak_votes"]) >= 2 or int(row["insuff_votes"]) >= 2
    }
    tier2_expected = all_work_expected - high_expected

    high_rows = action_rows(section_text(markdown, "Proposed Changes"))
    tier2_leak_rows = action_rows(section_text(markdown, "Tier-2 First-Pass Arbitration Addendum"))
    tier2_insuff_rows = action_rows(section_text(markdown, "Tier-2 Insufficiency Addendum"))
    all_rows = high_rows + tier2_leak_rows + tier2_insuff_rows
    all_case_ids = [row["case_id"] for row in all_rows]

    duplicates = sorted(case_id for case_id, count in Counter(all_case_ids).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate action rows: {', '.join(duplicates)}")

    unknown = sorted(set(all_case_ids) - cross_case_ids)
    if unknown:
        errors.append(f"proposal contains case IDs missing from crossref: {', '.join(unknown)}")

    high_actual = {row["case_id"] for row in high_rows}
    if high_actual != high_expected:
        errors.append(
            "highest-agreement proposal coverage mismatch: "
            f"missing={sorted(high_expected - high_actual)} extra={sorted(high_actual - high_expected)}"
        )

    tier2_actual = {row["case_id"] for row in tier2_leak_rows + tier2_insuff_rows}
    if tier2_actual != tier2_expected:
        errors.append(
            "tier-2 proposal coverage mismatch: "
            f"missing={sorted(tier2_expected - tier2_actual)} extra={sorted(tier2_actual - tier2_expected)}"
        )

    compare_counts(errors, "highest-agreement", Counter(row["action"] for row in high_rows), EXPECTED_HIGH_COUNTS)
    compare_counts(
        errors,
        "tier-2 leak addendum",
        Counter(row["action"] for row in tier2_leak_rows),
        EXPECTED_TIER2_LEAK_COUNTS,
    )
    compare_counts(
        errors,
        "tier-2 insufficiency addendum",
        Counter(row["action"] for row in tier2_insuff_rows),
        EXPECTED_TIER2_INSUFF_COUNTS,
    )
    combined_counts = Counter(row["action"] for row in all_rows)
    compare_counts(errors, "combined proposal", combined_counts, EXPECTED_COMBINED_COUNTS)

    high_section = section_text(markdown, "Highest-Agreement Tier Summary")
    for label, expected in (
        ("Proposed drops", EXPECTED_HIGH_COUNTS["DROP"]),
        ("Proposed mends", EXPECTED_HIGH_COUNTS["MEND"]),
        ("Proposed keeps", EXPECTED_HIGH_COUNTS["KEEP"]),
    ):
        actual = parse_summary_count(high_section, label)
        if actual != expected:
            errors.append(f"highest-agreement summary {label}={actual}, expected {expected}")

    combined_section = section_text(markdown, "Tier-2 Insufficiency Addendum")
    for label, expected in (
        ("Proposed drops", EXPECTED_COMBINED_COUNTS["DROP"]),
        ("Proposed mends", EXPECTED_COMBINED_COUNTS["MEND"]),
        ("Review-for-mend-or-drop", EXPECTED_COMBINED_COUNTS["REVIEW_FOR_MEND_OR_DROP"]),
        ("Proposed keeps", EXPECTED_COMBINED_COUNTS["KEEP"]),
    ):
        actual = parse_summary_count(combined_section, label)
        if actual != expected:
            errors.append(f"combined summary {label}={actual}, expected {expected}")

    operation_ids = operation_case_ids(section_text(markdown, "Exact Mend Operations Proposed"))
    operation_ids |= operation_case_ids(section_text(markdown, "Tier-2 First-Pass Arbitration Addendum"))
    mend_ids = {row["case_id"] for row in all_rows if row["action"] == "MEND"}
    missing_operations = sorted(mend_ids - operation_ids)
    if missing_operations:
        errors.append(f"MEND rows without exact operation: {', '.join(missing_operations)}")

    drops = EXPECTED_COMBINED_COUNTS["DROP"]
    review = EXPECTED_COMBINED_COUNTS["REVIEW_FOR_MEND_OR_DROP"]
    expected_mended_denominator = manifest_n - drops
    expected_dropped_denominator = manifest_n - drops - review
    if f"{expected_mended_denominator} cases" not in markdown:
        errors.append(
            f"proposal missing expected denominator if review is mended: {expected_mended_denominator}"
        )
    if f"denominator becomes {expected_dropped_denominator}" not in markdown:
        errors.append(
            f"proposal missing expected denominator if review is dropped: {expected_dropped_denominator}"
        )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, default=DEFAULT_PROPOSAL)
    parser.add_argument("--crossref", type=Path, default=DEFAULT_CROSSREF)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)

    errors = validate(args.proposal, args.crossref, args.manifest)
    if errors:
        print("Audit arbitration proposal validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Audit arbitration proposal validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
