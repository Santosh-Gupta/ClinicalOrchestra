#!/usr/bin/env python3
"""Run the LM4Sci workshop submission preflight.

This orchestrates the local checks that do not require provider quota or a TeX
installation. By default it refreshes generated paper artifacts before checking
them, so the validation result reflects the current repository state.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


PYTHON = "python3.11"


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]


REFRESH_STEPS = [
    Step("build figure PDFs", [PYTHON, "scripts/build_paper_figures.py"]),
    Step("stage workshop source bundle", [PYTHON, "scripts/package_workshop_source.py"]),
    Step(
        "preview audit cleanup manifests",
        [PYTHON, "scripts/preview_audit_arbitration_cleanup.py", "--write-preview"],
    ),
    Step("build audit approval packet", [PYTHON, "scripts/build_audit_approval_packet.py"]),
    Step("export rerun manifests", [PYTHON, "scripts/export_paper_rerun_manifests.py"]),
    Step(
        "refresh run-status Markdown",
        [
            PYTHON,
            "scripts/paper_run_status.py",
            "--write-markdown",
            "docs/LM4SCI_RUN_STATUS_20260623.md",
        ],
    ),
]

CHECK_STEPS = [
    Step("validate audit arbitration proposal", [PYTHON, "scripts/validate_audit_arbitration_proposal.py"]),
    Step("validate audit cleanup preview", [PYTHON, "scripts/preview_audit_arbitration_cleanup.py"]),
    Step("validate audit approval packet", [PYTHON, "scripts/build_audit_approval_packet.py", "--check"]),
    Step("validate workshop page budget", [PYTHON, "scripts/validate_workshop_page_budget.py"]),
    Step("check workshop LaTeX scaffold", [PYTHON, "scripts/build_workshop_submission.py"]),
    Step("validate paper package", [PYTHON, "scripts/validate_paper_package.py"]),
    Step("print paper run status", [PYTHON, "scripts/paper_run_status.py"]),
]


def planned_steps(check_only: bool = False) -> list[Step]:
    return ([] if check_only else list(REFRESH_STEPS)) + list(CHECK_STEPS)


def run_step(step: Step) -> None:
    print(f"\n== {step.name} ==")
    print("+ " + " ".join(step.command))
    subprocess.run(step.command, check=True)


def run_preflight(check_only: bool = False) -> int:
    for step in planned_steps(check_only=check_only):
        try:
            run_step(step)
        except subprocess.CalledProcessError as exc:
            print(f"preflight failed at step: {step.name}", file=sys.stderr)
            return exc.returncode or 1
    print("\nWorkshop submission preflight passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Skip artifact-refresh steps and only run validators/status commands.",
    )
    args = parser.parse_args(argv)
    return run_preflight(check_only=args.check_only)


if __name__ == "__main__":
    raise SystemExit(main())
