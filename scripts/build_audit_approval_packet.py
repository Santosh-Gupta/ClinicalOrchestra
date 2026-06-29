#!/usr/bin/env python3
"""Build a concise user-veto packet for audit arbitration.

The long proposal is useful for traceability, but the user needs a compact list
of the exact choices to approve or veto. This generator reads the proposal
tables and the executable preview plan, then writes a short Markdown packet.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_PROPOSAL = Path("docs/AUDIT_ARBITRATION_PROPOSAL_20260623.md")
DEFAULT_PREVIEW_SUMMARY = Path("build/audit_arbitration_preview/summary.json")
DEFAULT_OUT = Path("docs/AUDIT_ARBITRATION_APPROVAL_PACKET_20260623.md")
PREVIEW_SCRIPT = Path("scripts/preview_audit_arbitration_cleanup.py")
PROPOSAL_VALIDATOR = Path("scripts/validate_audit_arbitration_proposal.py")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_action_rows(proposal: Path) -> list[dict[str, str]]:
    validator = load_module(PROPOSAL_VALIDATOR, "validate_audit_arbitration_proposal_for_packet")
    markdown = proposal.read_text(encoding="utf-8")
    rows: list[dict[str, str]] = []
    for heading in (
        "Proposed Changes",
        "Tier-2 First-Pass Arbitration Addendum",
        "Tier-2 Insufficiency Addendum",
    ):
        rows.extend(validator.action_rows(validator.section_text(markdown, heading)))
    return rows


def operation_labels_by_case() -> dict[str, str]:
    preview = load_module(PREVIEW_SCRIPT, "preview_audit_arbitration_cleanup_for_packet")
    return {op.case_id: op.label for op in preview.MEND_OPERATIONS}


def read_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def grouped_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["action"]].append(row)
    for items in grouped.values():
        items.sort(key=lambda row: row["case_id"])
    return grouped


def table_for(rows: list[dict[str, str]], columns: tuple[str, ...]) -> str:
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("|" + "|".join("---" for _ in columns) + "|")
    for row in rows:
        values = [row.get(column, "") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_packet(proposal: Path, preview_summary: Path) -> str:
    rows = load_action_rows(proposal)
    grouped = grouped_rows(rows)
    labels = operation_labels_by_case()
    summary = read_summary(preview_summary)

    drops = grouped.get("DROP", [])
    mends = [dict(row, operation=labels.get(row["case_id"], "")) for row in grouped.get("MEND", [])]
    review = grouped.get("REVIEW_FOR_MEND_OR_DROP", [])

    cross_n = summary.get("crossmodel_original_n", 81)
    cross_preview_n = summary.get("crossmodel_preview_n", cross_n - len(drops))
    publish_n = summary.get("publish_original_n", 151)
    publish_preview_n = summary.get("publish_preview_n", publish_n - len(drops))
    review_case = summary.get("review_case_unresolved") or None
    drop_n, mend_n, review_n = len(drops), len(mends), len(review)
    review_dropped_n = cross_preview_n - review_n

    if review_n:
        review_section = [
            "## Unresolved Review Case",
            "",
            f"Default recommendation remains source validation before deciding whether to mend or drop `{review_case}`.",
            "",
            table_for(review, ("case_id", "tier", "justification")),
            "",
        ]
    else:
        review_section = [
            "## Unresolved Review Case",
            "",
            "None — the mend-maximal pass (2026-06-24) resolved the former review case "
            "(`transformed_PMC13149065`) to DROP. No unresolved review case remains.",
            "",
        ]

    lines = [
        "# Audit Arbitration Approval Packet 2026-06-23",
        "",
        "Status: user approval/veto packet. This file is generated from the audit proposal and the executable cleanup preview. It does not apply edits.",
        "",
        "## Decision Needed",
        "",
        "Approve or veto the proposed data-quality cleanup before source manifests are edited.",
        "",
        f"- Proposed drops: {drop_n}",
        f"- Proposed mends: {mend_n}",
        f"- Unresolved review-for-mend-or-drop: {review_n}",
        f"- Hard-set denominator if approved as previewed: {cross_n} -> {cross_preview_n}",
        f"- Hard-set denominator if the unresolved review case is dropped: {cross_n} -> {review_dropped_n}",
        f"- Publish manifest preview denominator: {publish_n} -> {publish_preview_n}",
        "- Gold labels are not relaxed or broadened.",
        "- Preview manifests are under `build/audit_arbitration_preview/` and are non-authoritative.",
        "",
        "## Proposed Drops",
        "",
        table_for(drops, ("case_id", "tier", "justification")),
        "",
        "## Proposed Mends",
        "",
        table_for(mends, ("case_id", "tier", "operation", "justification")),
        "",
        *review_section,
        "## After Approval",
        "",
        "1. Apply approved drops/mends to both `data/eval/crossmodel/flash_fail_postcutoff.jsonl` and `data/eval/publish/flash_failures_hard_cases.jsonl`.",
        "2. Run source/determinacy validation on mended cases.",
        "3. Re-score affected cells only and update paper counts.",
        "4. Add ADR-049 documenting final drop/mend/keep counts and the held-out data-quality rule.",
        "",
    ]
    return "\n".join(lines)


def validate_packet(text: str) -> list[str]:
    errors: list[str] = []
    required = [
        "Proposed drops:",
        "Proposed mends:",
        "Unresolved review-for-mend-or-drop:",
        "Gold labels are not relaxed or broadened.",
        "build/audit_arbitration_preview/",
    ]
    for needle in required:
        if needle not in text:
            errors.append(f"approval packet missing required text: {needle}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, default=DEFAULT_PROPOSAL)
    parser.add_argument("--preview-summary", type=Path, default=DEFAULT_PREVIEW_SUMMARY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that --out already matches the generated packet without rewriting it.",
    )
    args = parser.parse_args(argv)

    text = build_packet(args.proposal, args.preview_summary)
    errors = validate_packet(text)
    if args.check:
        if not args.out.exists():
            errors.append(f"missing approval packet: {args.out}")
        elif args.out.read_text(encoding="utf-8") != text:
            errors.append(f"stale approval packet: regenerate {args.out}")
    if errors:
        print("Audit approval packet validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if args.check:
        print(f"Audit approval packet is current: {args.out}")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
