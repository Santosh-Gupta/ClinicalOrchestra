#!/usr/bin/env python3
"""Stage a portable LM4Sci/COLM LaTeX source bundle.

The bundle mirrors the relative paths expected by ``main.tex``:
``workshop_submission/main.tex`` cites ``../paper_references.bib`` and includes
figures under ``workshop_submission/figures``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


DEFAULT_OUT_DIR = Path("build/lm4sci_submission_source")
SUBMISSION_DIR = Path("docs/workshop_submission")
BIB_PATH = Path("docs/paper_references.bib")

REQUIRED_SUBMISSION_FILES = [
    "main.tex",
    "colm2026_conference.sty",
    "colm2026_conference.bst",
    "fancyhdr.sty",
    "natbib.sty",
    "math_commands.tex",
    "figures/figure1_three_stage_funnel.pdf",
    "figures/figure2_judge_variance_floor.pdf",
]


def remove_existing(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def required_source_paths() -> list[Path]:
    return [SUBMISSION_DIR / name for name in REQUIRED_SUBMISSION_FILES] + [BIB_PATH]


def missing_required_sources() -> list[Path]:
    return [path for path in required_source_paths() if not path.exists()]


def stage_bundle(out_dir: Path) -> list[Path]:
    missing = missing_required_sources()
    if missing:
        raise FileNotFoundError(
            "missing required source files: " + ", ".join(str(path) for path in missing)
        )

    remove_existing(out_dir)
    staged: list[Path] = []
    copy_file(BIB_PATH, out_dir / "paper_references.bib")
    staged.append(out_dir / "paper_references.bib")
    for relative in REQUIRED_SUBMISSION_FILES:
        src = SUBMISSION_DIR / relative
        dst = out_dir / "workshop_submission" / relative
        copy_file(src, dst)
        staged.append(dst)
    return staged


def validate_bundle(out_dir: Path) -> list[str]:
    errors: list[str] = []
    required = [out_dir / "paper_references.bib"] + [
        out_dir / "workshop_submission" / relative for relative in REQUIRED_SUBMISSION_FILES
    ]
    for path in required:
        if not path.exists():
            errors.append(f"bundle missing required file: {path}")
    main = out_dir / "workshop_submission" / "main.tex"
    if main.exists():
        text = main.read_text(encoding="utf-8")
        if r"\bibliography{../paper_references}" not in text:
            errors.append("staged main.tex does not reference ../paper_references")
        for figure in (
            "figures/figure1_three_stage_funnel.pdf",
            "figures/figure2_judge_variance_floor.pdf",
        ):
            if figure not in text:
                errors.append(f"staged main.tex does not include {figure}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    try:
        staged = stage_bundle(args.out_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    errors = validate_bundle(args.out_dir)
    if errors:
        print("Workshop source bundle validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Staged {len(staged)} files under {args.out_dir}")
    print(f"Compile from: {args.out_dir / 'workshop_submission'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
