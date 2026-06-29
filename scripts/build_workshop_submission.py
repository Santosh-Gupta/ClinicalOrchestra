#!/usr/bin/env python3
"""Check or build the workshop LaTeX scaffold.

The default mode is a non-destructive readiness check. Use ``--build`` on a
machine with LaTeX installed to compile ``docs/workshop_submission/main.tex``.
Run ``scripts/build_paper_figures.py`` first after figure edits.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_TEX = Path("docs/workshop_submission/main.tex")


def _line_number(text: str, needle: str) -> int:
    prefix = text.split(needle, 1)[0]
    return prefix.count("\n") + 1


def available_builder() -> str | None:
    if shutil.which("latexmk"):
        return "latexmk"
    if shutil.which("pdflatex") and shutil.which("bibtex"):
        return "pdflatex"
    return None


def validate_float_and_label_hygiene(text: str, tex_path: Path) -> list[str]:
    errors: list[str] = []
    labels = re.findall(r"\\label\{([^}]+)\}", text)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for label in labels:
        if label in seen:
            duplicates.add(label)
        seen.add(label)
    for label in sorted(duplicates):
        errors.append(f"duplicate LaTeX label {label}: {tex_path}")

    refs = re.findall(r"\\(?:ref|autoref|eqref)\{([^}]+)\}", text)
    for ref in sorted(set(refs) - set(labels)):
        errors.append(f"LaTeX reference has no matching label {ref}: {tex_path}")

    for match in re.finditer(
        r"\\begin\{(figure|table)\}(?:\[[^\]]*\])?(.*?)\\end\{\1\}",
        text,
        flags=re.DOTALL,
    ):
        environment = match.group(1)
        body = match.group(2)
        line_number = text[: match.start()].count("\n") + 1
        if r"\caption{" not in body:
            errors.append(
                f"{environment} environment missing caption near line {line_number}: {tex_path}"
            )
        body_labels = re.findall(r"\\label\{([^}]+)\}", body)
        if not body_labels:
            errors.append(
                f"{environment} environment missing label near line {line_number}: {tex_path}"
            )
            continue
        expected_prefix = "fig:" if environment == "figure" else "tab:"
        for label in body_labels:
            if not label.startswith(expected_prefix):
                errors.append(
                    f"{environment} label {label} should start with {expected_prefix}: {tex_path}"
                )
    return errors


def check_inputs(tex_path: Path) -> list[str]:
    errors: list[str] = []
    if not tex_path.exists():
        return [f"missing TeX file: {tex_path}"]

    text = tex_path.read_text(encoding="utf-8")

    for line_number, line in enumerate(text.splitlines(), start=1):
        try:
            line.encode("ascii")
        except UnicodeEncodeError:
            errors.append(f"TeX scaffold contains non-ASCII text on line {line_number}: {tex_path}")
            break

    markdown_artifacts = [
        "![",
        "TO" + "DO",
        "PLACE" + "HOLDER",
        "FIXME",
        r"\fbox",
    ]
    for snippet in markdown_artifacts:
        if snippet in text:
            line_number = _line_number(text, snippet)
            errors.append(
                f"TeX scaffold contains draft/markdown artifact {snippet} on line {line_number}: {tex_path}"
            )

    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("#"):
            errors.append(
                f"TeX scaffold contains markdown heading marker on line {line_number}: {tex_path}"
            )

    for environment in ("abstract", "figure", "table", "tabular"):
        begins = text.count(rf"\begin{{{environment}}}")
        ends = text.count(rf"\end{{{environment}}}")
        if begins != ends:
            errors.append(
                f"TeX scaffold has unbalanced {environment} environments ({begins} begin, {ends} end): {tex_path}"
            )
    errors.extend(validate_float_and_label_hygiene(text, tex_path))

    required_snippets = [
        r"\documentclass{article}",
        r"\usepackage[submission]{colm2026_conference}",
        r"\author{Anonymous Authors}",
        r"\begin{document}",
        r"\end{document}",
        r"\bibliographystyle{colm2026_conference}",
        r"\bibliography{../paper_references}",
    ]
    for snippet in required_snippets:
        if snippet not in text:
            errors.append(f"TeX scaffold missing {snippet}: {tex_path}")

    forbidden_snippets = [
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{geometry}",
        r"\usepackage{times}",
        r"\bibliographystyle{plainnat}",
        "ClinicalHarness Contributors",
        r"\thanks{",
        "Department of",
        "University",
    ]
    for snippet in forbidden_snippets:
        if snippet in text:
            errors.append(f"TeX scaffold uses non-COLM snippet {snippet}: {tex_path}")

    for filename in (
        "colm2026_conference.sty",
        "colm2026_conference.bst",
        "fancyhdr.sty",
        "natbib.sty",
    ):
        if not (tex_path.parent / filename).exists():
            errors.append(f"missing COLM template file: {tex_path.parent / filename}")

    for filename in (
        "figures/figure1_three_stage_funnel.pdf",
        "figures/figure2_judge_variance_floor.pdf",
    ):
        if filename not in text:
            errors.append(f"TeX scaffold does not include figure asset {filename}: {tex_path}")
        if not (tex_path.parent / filename).exists():
            errors.append(f"missing figure asset: {tex_path.parent / filename}")

    bib = tex_path.parent.parent / "paper_references.bib"
    if not bib.exists():
        errors.append(f"missing bibliography: {bib}")

    return errors


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def build(tex_path: Path) -> int:
    errors = check_inputs(tex_path)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    builder = available_builder()
    if builder is None:
        print(
            "No LaTeX builder found. Install latexmk, or install pdflatex and bibtex.",
            file=sys.stderr,
        )
        return 2

    workdir = tex_path.parent
    tex_name = tex_path.name
    stem = tex_path.stem

    try:
        if builder == "latexmk":
            run(["latexmk", "-pdf", "-interaction=nonstopmode", tex_name], cwd=workdir)
        else:
            run(["pdflatex", "-interaction=nonstopmode", tex_name], cwd=workdir)
            run(["bibtex", stem], cwd=workdir)
            run(["pdflatex", "-interaction=nonstopmode", tex_name], cwd=workdir)
            run(["pdflatex", "-interaction=nonstopmode", tex_name], cwd=workdir)
    except subprocess.CalledProcessError as exc:
        return exc.returncode or 1

    pdf = workdir / f"{stem}.pdf"
    if not pdf.exists():
        print(f"build completed but PDF is missing: {pdf}", file=sys.stderr)
        return 1
    print(f"Built {pdf}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tex", type=Path, default=DEFAULT_TEX)
    parser.add_argument(
        "--build",
        action="store_true",
        help="Compile the TeX scaffold instead of only checking inputs/tools.",
    )
    args = parser.parse_args(argv)

    errors = check_inputs(args.tex)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    builder = available_builder()
    if not args.build:
        if builder:
            print(f"Workshop scaffold check passed; available builder: {builder}.")
        else:
            print(
                "Workshop scaffold check passed; no LaTeX builder is installed in this environment."
            )
        return 0

    return build(args.tex)


if __name__ == "__main__":
    raise SystemExit(main())
