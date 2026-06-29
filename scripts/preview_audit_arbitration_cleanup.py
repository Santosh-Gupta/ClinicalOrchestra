#!/usr/bin/env python3
"""Preview the proposed audit-arbitration cleanup without editing source manifests.

This script is intentionally conservative: it verifies that the proposed DROP
and MEND operations can be applied to the current manifests, then optionally
writes preview JSONL files under ``build/``. It does not modify the source
manifests because the audit proposal still requires user approval/veto.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CROSSMODEL = Path("data/eval/crossmodel/flash_fail_postcutoff.jsonl")
DEFAULT_PUBLISH = Path("data/eval/publish/flash_failures_hard_cases.jsonl")
DEFAULT_OUT_DIR = Path("build/audit_arbitration_preview")

# Mend-maximal slate (2026-06-24): two former drops (PMC13167955, PMC13154095) were
# converted to source-grounded mends because the gold remains determinable from the
# legitimate pre-question workup once the gratuitous label/alias is removed. The former
# review case (PMC13149065) was resolved to DROP — no source-grounded EPP discriminator
# (erythrocyte protoporphyrin / FECH) is present, and adding the FECH mutation would leak
# the answer, so the case is left under-determined and dropped.
DROP_IDS = {
    "transformed_PMC13268879",
    "transformed_PMC13171345",
    "transformed_PMC13115914",
    "transformed_PMC13122547",
    "transformed_PMC13201062",
    "transformed_PMC13272297",
    "transformed_PMC13251344",
    "transformed_PMC13173917",
    "transformed_PMC13212106",
    "transformed_PMC13235501",
    "transformed_PMC13033411",
    "transformed_PMC13212079",
    "transformed_PMC13149065",
}

# No unresolved review case remains after the 2026-06-24 mend-maximal pass.
REVIEW_ID = None


@dataclass(frozen=True)
class MendOperation:
    case_id: str
    old: str
    new: str
    label: str


MEND_OPERATIONS = (
    MendOperation(
        case_id="transformed_PMC13276447",
        label="delete post-question EUS-FNB toxoplasma outcome leak",
        old=(
            "\n\nThe diagnosis was ultimately established via endoscopic ultrasound (EUS)-guided "
            "fine needle biopsy (FNB), which identified T. gondii organisms."
        ),
        new="",
    ),
    MendOperation(
        case_id="transformed_PMC13173586",
        label="delete post-question gingival SCC outcome leak",
        old=(
            "\n\nThe tumor was determined to be primary gingival squamous cell carcinoma with "
            "secondary extension into the maxillary sinus, orbit, and skull base."
        ),
        new="",
    ),
    MendOperation(
        case_id="transformed_PMC13053943",
        label="delete post-question MRI/subdural empyema outcome leak",
        old=(
            "\n\nMRI of the brain and orbits revealed left frontal subdural empyema and "
            "maxillary sinusitis."
        ),
        new="",
    ),
    MendOperation(
        case_id="transformed_PMC13135428",
        label="move Streptococcus dysgalactiae blood-culture result before question",
        old=(
            "Based on the presentation, what is the most likely diagnosis?\n\nBlood cultures "
            "resulted positive for Streptococcus dysgalactiae."
        ),
        new=(
            "Blood cultures resulted positive for Streptococcus dysgalactiae.\n\nBased on the "
            "presentation, what is the most likely diagnosis?"
        ),
    ),
    MendOperation(
        case_id="transformed_PMC12875838",
        label="move C1-INH/complement result before management question",
        old=(
            "After recovery, the provider wishes to restart SCIG therapy. What is the most "
            "appropriate next step to allow safe SCIG administration?\n\nLaboratory evaluation "
            "revealed low C1 esterase inhibitor level (14 mg/dL; reference range 21-39) and "
            "elevated complement activation markers (C3a and C5a)."
        ),
        new=(
            "After recovery, the provider wishes to restart SCIG therapy. Laboratory evaluation "
            "revealed low C1 esterase inhibitor level (14 mg/dL; reference range 21-39) and "
            "elevated complement activation markers (C3a and C5a).\n\nWhat is the most appropriate "
            "next step to allow safe SCIG administration?"
        ),
    ),
    MendOperation(
        case_id="transformed_PMC13107638",
        label="delete post-question necropsy organism leak",
        old=(
            "\n\nAt necropsy, adult Angiostrongylus cantonensis were found in the meninges, and "
            "histopathology of the lungs revealed necrotizing fungal pneumonia due to Aspergillus species."
        ),
        new="",
    ),
    MendOperation(
        case_id="transformed_PMC13198432",
        label="add source-grounded TB confirmation before question",
        old=(
            "No CSF leak was evident clinically or from drain output.\n\nBased on the presentation "
            "and findings, what is the most likely diagnosis for the postoperative MRI finding, "
            "and what is the most appropriate next step in management?"
        ),
        new=(
            "No CSF leak was evident clinically or from drain output. Histopathology of the "
            "intraoperative specimen showed acid-fast bacilli, and GeneXpert detected "
            "rifampicin-sensitive Mycobacterium tuberculosis.\n\nBased on the presentation and "
            "findings, what is the most likely diagnosis for the postoperative MRI finding, and "
            "what is the most appropriate next step in management?"
        ),
    ),
    MendOperation(
        case_id="transformed_PMC12865494",
        label="rephrase restless-arm family-history leak",
        old="Family history of restless legs or restless arm syndrome was negative.",
        new="Family history of similar nocturnal limb-movement symptoms was negative.",
    ),
    MendOperation(
        case_id="transformed_PMC13167955",
        label="delete gratuitous inline PAH diagnosis label (workup still determines gold)",
        old=" Diagnosis: idiopathic precapillary pulmonary arterial hypertension (PAH).",
        new="",
    ),
    MendOperation(
        case_id="transformed_PMC13154095",
        label="rephrase ILR primary-VF alias to descriptive rhythm (keeps normal-QT/not-TdP discriminator)",
        old="consistent with primary ventricular fibrillation (not TdP)",
        new=(
            "arising abruptly from a normal QT interval and distinct from the earlier "
            "torsades de pointes"
        ),
    ),
    MendOperation(
        case_id="transformed_PMC13198437",
        label="rephrase night-terror diagnostic label as descriptive nocturnal episodes",
        old=(
            "Past psychiatric history: generalized anxiety disorder and night terrors beginning "
            "in early childhood, ongoing for 1.5 years, typically between 12-4 AM, lasting 15 "
            "minutes to 3 hours, with vocalized screaming at home."
        ),
        new=(
            "Past psychiatric history: generalized anxiety disorder and recurrent nocturnal episodes "
            "beginning in early childhood, ongoing for 1.5 years, typically between 12-4 AM, lasting "
            "15 minutes to 3 hours, with vocalized screaming at home."
        ),
    ),
)


def effective_source(path: Path) -> Path:
    """Return the pre-cleanup backup when present, else the path itself.

    After ``--apply`` the live manifest is the cleaned set, but the preview/validation
    logic describes the ORIGINAL -> cleaned transform, so it must read the original. The
    backup written by ``apply_cleanup`` provides that stable source and makes both the
    preview and the apply idempotent.
    """
    backup = path.with_suffix(path.suffix + ".pre_audit_cleanup.bak")
    return backup if backup.exists() else path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def rows_by_case(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["case_id"]): row for row in rows}


def validate_manifest_rows(rows: list[dict[str, Any]], label: str) -> list[str]:
    errors: list[str] = []
    by_case = rows_by_case(rows)
    missing_drops = sorted(DROP_IDS - set(by_case))
    if missing_drops:
        errors.append(f"{label}: DROP ids missing from manifest: {', '.join(missing_drops)}")
    missing_mends = sorted(op.case_id for op in MEND_OPERATIONS if op.case_id not in by_case)
    if missing_mends:
        errors.append(f"{label}: MEND ids missing from manifest: {', '.join(missing_mends)}")
    if REVIEW_ID is not None and REVIEW_ID not in by_case:
        errors.append(f"{label}: review case missing from manifest: {REVIEW_ID}")

    for op in MEND_OPERATIONS:
        row = by_case.get(op.case_id)
        if not row:
            continue
        prompt = str(row.get("challenge_prompt", ""))
        if op.old not in prompt:
            errors.append(f"{label}: exact old text not found for {op.case_id} ({op.label})")
        if op.new and op.new in prompt:
            errors.append(f"{label}: replacement text already present before mend for {op.case_id}")
    return errors


def preview_cleanup(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patched: list[dict[str, Any]] = []
    operations = {op.case_id: op for op in MEND_OPERATIONS}
    for row in rows:
        case_id = str(row["case_id"])
        if case_id in DROP_IDS:
            continue
        if case_id in operations:
            op = operations[case_id]
            row = dict(row)
            row["challenge_prompt"] = str(row["challenge_prompt"]).replace(op.old, op.new, 1)
            row["audit_arbitration_preview"] = {
                "action": "MEND",
                "operation": op.label,
                "source": "docs/AUDIT_ARBITRATION_PROPOSAL_20260623.md",
            }
        patched.append(row)
    return patched


def validate_patched_rows(
    original: list[dict[str, Any]], patched: list[dict[str, Any]], label: str
) -> list[str]:
    errors: list[str] = []
    original_ids = {str(row["case_id"]) for row in original}
    patched_by_case = rows_by_case(patched)
    patched_ids = set(patched_by_case)
    retained_drops = sorted(DROP_IDS & patched_ids)
    if retained_drops:
        errors.append(f"{label}: DROP ids still present after preview: {', '.join(retained_drops)}")
    unexpected_removed = sorted((original_ids - DROP_IDS) - patched_ids)
    if unexpected_removed:
        errors.append(f"{label}: non-DROP ids removed: {', '.join(unexpected_removed)}")

    expected_n = len(original) - len(DROP_IDS)
    if len(patched) != expected_n:
        errors.append(f"{label}: patched row count {len(patched)} != expected {expected_n}")

    for op in MEND_OPERATIONS:
        row = patched_by_case.get(op.case_id)
        if not row:
            errors.append(f"{label}: patched manifest missing MEND id {op.case_id}")
            continue
        prompt = str(row.get("challenge_prompt", ""))
        if op.old in prompt:
            errors.append(f"{label}: old text still present after mend for {op.case_id}")
        if op.new and op.new not in prompt:
            errors.append(f"{label}: replacement text missing after mend for {op.case_id}")
    return errors


def run_preview(crossmodel: Path, publish: Path, out_dir: Path | None) -> list[str]:
    errors: list[str] = []
    cross_rows = read_jsonl(effective_source(crossmodel))
    publish_rows = read_jsonl(effective_source(publish))
    errors.extend(validate_manifest_rows(cross_rows, "crossmodel"))
    errors.extend(validate_manifest_rows(publish_rows, "publish"))
    if errors:
        return errors

    patched_cross = preview_cleanup(cross_rows)
    patched_publish = preview_cleanup(publish_rows)
    errors.extend(validate_patched_rows(cross_rows, patched_cross, "crossmodel"))
    errors.extend(validate_patched_rows(publish_rows, patched_publish, "publish"))
    if errors:
        return errors

    if out_dir is not None:
        write_jsonl(out_dir / crossmodel.name, patched_cross)
        write_jsonl(out_dir / publish.name, patched_publish)
        summary = {
            "source_crossmodel": str(crossmodel),
            "source_publish": str(publish),
            "drop_count": len(DROP_IDS),
            "mend_count": len(MEND_OPERATIONS),
            "review_case_unresolved": REVIEW_ID,
            "crossmodel_original_n": len(cross_rows),
            "crossmodel_preview_n": len(patched_cross),
            "publish_original_n": len(publish_rows),
            "publish_preview_n": len(patched_publish),
        }
        (out_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return []


def apply_cleanup(crossmodel: Path, publish: Path) -> list[str]:
    """Apply the cleanup destructively to the SOURCE manifests after a clean preview.

    Each source file is backed up to ``<path>.pre_audit_cleanup.bak`` before being
    overwritten with the patched rows.
    """
    errors = run_preview(crossmodel, publish, out_dir=None)
    if errors:
        return errors
    for path in (crossmodel, publish):
        backup = path.with_suffix(path.suffix + ".pre_audit_cleanup.bak")
        if not backup.exists():
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        # Always re-derive from the original (backup) so re-applying is idempotent.
        rows = read_jsonl(backup)
        write_jsonl(path, preview_cleanup(rows))
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crossmodel", type=Path, default=DEFAULT_CROSSMODEL)
    parser.add_argument("--publish", type=Path, default=DEFAULT_PUBLISH)
    parser.add_argument(
        "--write-preview",
        action="store_true",
        help=f"write patched preview JSONL files under {DEFAULT_OUT_DIR}",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="DESTRUCTIVELY apply the cleanup to the source manifests (backs up first). "
        "Use only after user approval.",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    if args.apply:
        errors = apply_cleanup(args.crossmodel, args.publish)
        if errors:
            print("Audit arbitration cleanup APPLY failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print(
            "Audit arbitration cleanup APPLIED to source manifests: "
            f"{len(DROP_IDS)} drops, {len(MEND_OPERATIONS)} mends (backups written)."
        )
        return 0

    out_dir = args.out_dir if args.write_preview else None
    errors = run_preview(args.crossmodel, args.publish, out_dir)
    if errors:
        print("Audit arbitration cleanup preview failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    review_note = REVIEW_ID if REVIEW_ID is not None else "none"
    print(
        "Audit arbitration cleanup preview passed: "
        f"{len(DROP_IDS)} drops, {len(MEND_OPERATIONS)} mends, review case unresolved ({review_note})."
    )
    if out_dir is not None:
        print(f"Wrote preview manifests under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
