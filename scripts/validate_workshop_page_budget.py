#!/usr/bin/env python3
"""Approximate the LM4Sci/COLM main-content page budget.

This is a local guardrail only. It is not a substitute for compiling the COLM
PDF, but it catches obvious overlength before a machine with LaTeX is available.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DEFAULT_DRAFT = Path("docs/paper_workshop_compact_20260623.md")
DEFAULT_TEX = Path("docs/workshop_submission/main.tex")


def main_content_markdown(markdown: str) -> str:
    start = markdown.find("## Abstract")
    if start >= 0:
        markdown = markdown[start:]
    for marker in ("\n## References", "\n## Submission Readiness Note"):
        index = markdown.find(marker)
        if index >= 0:
            markdown = markdown[:index]
            break
    return markdown


def word_count(markdown: str) -> int:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", markdown)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"[\[\]#*_>|]", " ", text)
    return len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", text))


def float_counts(tex: str) -> tuple[int, int]:
    return tex.count(r"\begin{figure}"), tex.count(r"\begin{table}")


def estimate_pages(words: int, figures: int, tables: int) -> float:
    # COLM-style two-column pages vary by equation/table density. These weights
    # are intentionally conservative for this paper's compact figures/tables.
    text_pages = words / 650
    float_pages = figures * 0.35 + tables * 0.22
    return text_pages + float_pages


def validate(draft: Path, tex: Path, max_pages: float) -> tuple[list[str], dict[str, float | int]]:
    errors: list[str] = []
    if not draft.exists():
        return [f"missing draft: {draft}"], {}
    if not tex.exists():
        return [f"missing TeX source: {tex}"], {}

    main_markdown = main_content_markdown(draft.read_text(encoding="utf-8"))
    tex_text = tex.read_text(encoding="utf-8")
    words = word_count(main_markdown)
    figures, tables = float_counts(tex_text)
    estimated_pages = estimate_pages(words, figures, tables)
    metrics: dict[str, float | int] = {
        "words": words,
        "figures": figures,
        "tables": tables,
        "estimated_pages": round(estimated_pages, 2),
        "max_pages": max_pages,
    }
    if estimated_pages > max_pages:
        errors.append(
            f"estimated main-content pages {estimated_pages:.2f} exceeds local budget {max_pages:.2f}"
        )
    return errors, metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--tex", type=Path, default=DEFAULT_TEX)
    parser.add_argument(
        "--max-pages",
        type=float,
        default=8.0,
        help="Maximum estimated main-content pages before failing the local guardrail.",
    )
    args = parser.parse_args(argv)

    errors, metrics = validate(args.draft, args.tex, args.max_pages)
    if metrics:
        print(
            "Page budget estimate: "
            f"{metrics['estimated_pages']} pages "
            f"({metrics['words']} words, {metrics['figures']} figures, {metrics['tables']} tables; "
            f"limit {metrics['max_pages']})."
        )
    if errors:
        print("Workshop page-budget validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Workshop page-budget validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
