#!/usr/bin/env python3
"""Validate the workshop paper package.

This is intentionally lightweight and dependency-free. It checks the things that
have repeatedly become stale while the paper has been moving quickly: word count,
placeholder text, citation keys, inline reference entries, image paths, and
required caveat strings.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


DEFAULT_STALE_PATTERNS = [
    "TODO",
    "TBD",
    "Working title",
    "fill-in",
    "final-ish",
    "old-client",
    "PLACEHOLDER",
]

DEFAULT_REQUIRED_STRINGS = [
    "GPT-5.5 remains provisional",
    "audit arbitration",
    "not_run",
    "JUDGE_VOTES=3",
    "LM4Sci 2026",
    "June 28, 2026",
    "COLM template",
]

DEFAULT_REQUIRED_FILES = [
    "docs/HANDOFF_20260624.md",
    "docs/WORKSHOP_READINESS_20260623.md",
    "docs/WORKSHOP_SUBMISSION_PACKAGE_20260623.md",
    "docs/WORKSHOP_VENUE_ADAPTATION_20260623.md",
    "docs/WORKSHOP_CLAIM_EVIDENCE_MATRIX_20260623.md",
    "docs/LM4SCI_RUN_STATUS_20260623.md",
    "docs/AUDIT_ARBITRATION_APPROVAL_PACKET_20260623.md",
    "data/eval/rerun_manifests/lm4sci_20260623/README.md",
    "docs/paper_figures/README.md",
    "docs/paper_source_claim_audit_20260623.md",
    "docs/workshop_submission/README.md",
    "docs/workshop_submission/main.tex",
    "scripts/build_workshop_submission.py",
    "scripts/paper_run_status.py",
    "scripts/export_paper_rerun_manifests.py",
    "scripts/merge_paper_rerun_results.py",
    "scripts/build_audit_approval_packet.py",
]


SUBMISSION_PRIVACY_PATTERNS = [
    (re.compile(r"/Users/[A-Za-z0-9_.-]+"), "local absolute user path"),
    (re.compile(r"\bSantosh\b|\bsantosh\b"), "local user name"),
    (re.compile(r"\bNeurologyBM\b"), "external/private benchmark repo name"),
    (re.compile(r"DO NOT COMMIT", re.IGNORECASE), "private-material directory marker"),
    (re.compile(r"\bNEJM\b|\bJAMA\b|\bCarey\s+2017\b", re.IGNORECASE), "private/non-public source family"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "API key-like token"),
    (
        re.compile(r"\b(OPENAI|DEEPSEEK|ANTHROPIC|GEMINI|GOOGLE)_?API_?KEY\b", re.IGNORECASE),
        "API key environment variable",
    ),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"), "Google API key-like token"),
]


CORE_MARKDOWN_SECTIONS = [
    "Introduction",
    "Benchmark Construction",
    "ClinicalHarness",
    "Evaluation Protocol",
    "Results",
    "Negative Ablations",
    "Discussion",
    "Limitations",
    "Data, Code, and Ethics",
]

CORE_RESULT_SUBSECTIONS = [
    "Development Waves and Held-Out Generalization",
    "Post-Cutoff Contamination Control",
    "Residual Failures Are Mostly Gold Artifacts",
    "Cross-Model Evaluation, With and Without the Harness",
]

REQUIRED_TEX_CAVEATS = [
    "GPT-5.5 remains provisional",
    "failure-selected rescue set",
    "not a neutral leaderboard",
    r"\texttt{not\_run}",
    r"\texttt{JUDGE\_VOTES=3}",
]


def word_count(text: str) -> int:
    return len(text.split())


def bib_keys(bib_text: str) -> set[str]:
    return set(re.findall(r"@\w+\{([^,]+),", bib_text))


def bib_entry_records(bib_text: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", bib_text):
        entry_type = match.group(1).lower()
        key = match.group(2)
        start = match.end()
        next_entry = re.search(r"\n\s*@", bib_text[start:])
        end = start + next_entry.start() if next_entry else len(bib_text)
        entries.append((key, entry_type, bib_text[start:end]))
    return entries


def bib_entries(bib_text: str) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for key, entry_type, body in bib_entry_records(bib_text):
        entries[key] = (entry_type, body)
    return entries


def duplicate_bib_keys(bib_text: str) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for key in re.findall(r"@\w+\{([^,]+),", bib_text):
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return sorted(duplicates)


def bib_entry_fields(entry_body: str) -> set[str]:
    return {
        match.group(1).lower()
        for match in re.finditer(r"^\s*([A-Za-z][A-Za-z0-9_-]*)\s*=", entry_body, re.MULTILINE)
    }


def validate_bibliography(bib_text: str) -> list[str]:
    errors: list[str] = []
    duplicates = duplicate_bib_keys(bib_text)
    if duplicates:
        errors.append(f"duplicate BibTeX keys: {', '.join(duplicates)}")

    records = bib_entry_records(bib_text)
    parsed_keys = {key for key, _, _ in records}
    regex_keys = bib_keys(bib_text)
    if parsed_keys != regex_keys:
        missing = sorted(regex_keys - parsed_keys)
        if missing:
            errors.append(f"BibTeX entries could not be parsed: {', '.join(missing)}")

    for key, entry_type, body in sorted(records):
        fields = bib_entry_fields(body)
        for required in ("title", "author", "year"):
            if required not in fields:
                errors.append(f"BibTeX entry {key} missing required field: {required}")
        if "doi" not in fields and "url" not in fields:
            errors.append(f"BibTeX entry {key} missing DOI or URL")
        if entry_type in {"article", "inproceedings"}:
            if "journal" not in fields and "booktitle" not in fields:
                errors.append(f"BibTeX entry {key} missing journal/booktitle")
    return errors


def citation_keys(markdown: str) -> set[str]:
    keys: set[str] = set()
    for chunk in re.findall(r"\[([^\]]+)\]", markdown):
        for part in re.split(r";\s*", chunk):
            token = part.strip()
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9]+", token):
                keys.add(token)
    return keys


def inline_reference_keys(markdown: str) -> set[str]:
    return set(re.findall(r"^\[([^\]]+)\]", markdown, flags=re.MULTILINE))


def image_paths(markdown: str) -> list[str]:
    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown)


def validate_submission_privacy(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if not path.exists() or path.is_dir():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern, description in SUBMISSION_PRIVACY_PATTERNS:
            match = pattern.search(text)
            if match:
                line_number = text[: match.start()].count("\n") + 1
                errors.append(
                    f"submission-facing file contains {description} on line {line_number}: {path}"
                )
    return errors


def validate_latex_scaffold(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if r"\begin{document}" not in text:
        errors.append(f"LaTeX scaffold missing \\begin{{document}}: {path}")
    if r"\end{document}" not in text:
        errors.append(f"LaTeX scaffold missing \\end{{document}}: {path}")
    if text.count(r"\begin{document}") != text.count(r"\end{document}"):
        errors.append(f"LaTeX scaffold has unbalanced document environment: {path}")
    if r"\bibliography{../paper_references}" not in text:
        errors.append(f"LaTeX scaffold does not reference ../paper_references bibliography: {path}")
    if r"\title{" not in text or r"\begin{abstract}" not in text:
        errors.append(f"LaTeX scaffold missing title or abstract: {path}")
    build_checker = Path("scripts/build_workshop_submission.py")
    if build_checker.exists():
        spec = importlib.util.spec_from_file_location("build_workshop_submission", build_checker)
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            errors.extend(module.check_inputs(path))
    return errors


def latex_citation_keys(tex_text: str) -> set[str]:
    keys: set[str] = set()
    for command_args in re.findall(r"\\cite\w*\{([^}]+)\}", tex_text):
        for key in command_args.split(","):
            stripped = key.strip()
            if stripped:
                keys.add(stripped)
    return keys


def normalize_heading(text: str) -> str:
    text = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", text.strip())
    text = text.replace("`", "")
    return re.sub(r"\s+", " ", text)


def markdown_heading_titles(markdown: str, level: int) -> list[str]:
    marker = "#" * level
    pattern = rf"^{re.escape(marker)}\s+(.+)$"
    return [
        normalize_heading(match)
        for match in re.findall(pattern, markdown, flags=re.MULTILINE)
    ]


def latex_section_titles(tex_text: str, command: str = "section") -> list[str]:
    return [
        normalize_heading(match)
        for match in re.findall(rf"\\{command}\{{([^}}]+)\}}", tex_text)
    ]


def validate_latex_draft_alignment(draft_text: str, tex_text: str | None) -> list[str]:
    if tex_text is None:
        return []
    errors: list[str] = []
    markdown_sections = set(markdown_heading_titles(draft_text, 2))
    markdown_subsections = set(markdown_heading_titles(draft_text, 3))
    tex_sections = set(latex_section_titles(tex_text, "section"))
    tex_subsections = set(latex_section_titles(tex_text, "subsection"))

    for section in CORE_MARKDOWN_SECTIONS:
        if section in markdown_sections and section not in tex_sections:
            errors.append(f"LaTeX source missing core section from compact draft: {section}")

    for subsection in CORE_RESULT_SUBSECTIONS:
        if subsection in markdown_subsections and subsection not in tex_subsections:
            errors.append(
                f"LaTeX source missing Results subsection from compact draft: {subsection}"
            )

    for caveat in REQUIRED_TEX_CAVEATS:
        if caveat not in tex_text:
            errors.append(f"LaTeX source missing required reporting caveat: {caveat}")
    return errors


def rounded_percent(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return int((100 * numerator / denominator) + 0.5)


def load_run_status() -> tuple[int, dict[str, dict[str, object]]] | None:
    script = Path("scripts/paper_run_status.py")
    if not script.exists():
        return None
    spec = importlib.util.spec_from_file_location("paper_run_status", script)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    denominator = module.manifest_count()
    summaries = {
        row["name"]: row
        for row in [module.summarize_lane(lane, denominator) for lane in module.LANES]
    }
    return denominator, summaries


def run_status_module():
    script = Path("scripts/paper_run_status.py")
    if not script.exists():
        return None
    spec = importlib.util.spec_from_file_location("paper_run_status", script)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def audit_proposal_module():
    script = Path("scripts/validate_audit_arbitration_proposal.py")
    if not script.exists():
        return None
    spec = importlib.util.spec_from_file_location("validate_audit_arbitration_proposal", script)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_run_status_claims(draft_text: str, tex_text: str | None) -> list[str]:
    status = load_run_status()
    if status is None:
        return []
    denominator, summaries = status
    errors: list[str] = []
    normalized_draft = re.sub(r"\s+", " ", draft_text)
    normalized_tex = re.sub(r"\s+", " ", tex_text) if tex_text is not None else None

    # Unified cross-model table (§5.4): each frontier model bare (top-1) vs inside the harness
    # (answerer + V4 Pro reader), top-1 and top-5. Map each model to its bare lane and harness lane;
    # verify all three cell values are present in the draft and LaTeX (a staleness guard).
    models = {
        "Gemini 3.5 Flash": ("gemini-3.5-flash bare", "gemini-3.5-flash answerer + v4-pro reader"),
        "Gemini 3.1 Pro": ("gemini-3.1-pro bare", "gemini-3.1-pro answerer + v4-pro reader"),
        "Claude Opus 4.7": ("opus-4.7 bare", "opus-4.7 answerer + v4-pro reader"),
        "Claude Opus 4.8": ("opus-4.8 bare", "opus-4.8 answerer + v4-pro reader"),
        "GPT-5.4": ("gpt-5.4 bare Responses", "gpt-5.4 answerer + v4-pro reader"),
        "GPT-5.5": ("gpt-5.5 bare Responses", "gpt-5.5 answerer + v4-pro reader"),
    }
    for label, (bare_lane, harness_lane) in models.items():
        bare = summaries.get(bare_lane)
        harness = summaries.get(harness_lane)
        if bare is None or harness is None:
            continue
        cells = {
            "bare top-1": int(bare["score_pass"]),
            "harness top-1": int(harness["pass_at_1"]),
            "harness top-5": int(harness["pass_at_5"]),
        }
        for kind, value in cells.items():
            cell = f"{value} / {denominator}"
            if cell not in normalized_draft:
                errors.append(
                    f"draft cross-model table stale for {label} {kind}: expected '{cell}'"
                )
            if normalized_tex is not None and cell not in normalized_tex:
                errors.append(
                    f"LaTeX cross-model table stale for {label} {kind}: expected '{cell}'"
                )
    return errors


def validate_run_status_document(path: Path) -> list[str]:
    if not path.exists():
        return [f"run-status document does not exist: {path}"]
    module = run_status_module()
    if module is None:
        return []
    expected = module.render_markdown()
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        return [
            f"run-status document is stale: regenerate with python3.11 scripts/paper_run_status.py --write-markdown {path}"
        ]
    return []


def validate_rerun_manifest_readme(path: Path) -> list[str]:
    if not path.exists():
        return [f"rerun manifest README does not exist: {path}"]
    manifest_paths = sorted(
        child for child in path.parent.glob("*.jsonl") if child.name != "README.md"
    )
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for manifest in manifest_paths:
        if f"`{manifest}`" not in text:
            errors.append(f"rerun manifest README missing manifest path: {manifest}")
    table_rows = [
        line for line in text.splitlines() if line.startswith("| ") and not line.startswith("|---")
    ]
    data_rows = [line for line in table_rows if not line.startswith("| Lane |")]
    if len(data_rows) != len(manifest_paths):
        errors.append(
            f"rerun manifest README row count {len(data_rows)} does not match {len(manifest_paths)} JSONL manifests"
        )
    return errors


def validate_audit_proposal() -> list[str]:
    module = audit_proposal_module()
    if module is None:
        return []
    return module.validate(
        Path("docs/AUDIT_ARBITRATION_PROPOSAL_20260623.md"),
        Path("data/eval/audit/_crossref.csv"),
        Path("data/eval/crossmodel/flash_fail_postcutoff.jsonl"),
    )


def validate(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    draft = args.draft
    bib = args.bib

    if not draft.exists():
        return [f"draft does not exist: {draft}"]
    if not bib.exists():
        return [f"BibTeX file does not exist: {bib}"]
    for required_file in args.required_file:
        if not required_file.exists():
            errors.append(f"required package file does not exist: {required_file}")
    privacy_targets = [draft, bib] + [path for path in args.required_file if path.exists()]
    if args.tex is not None and args.tex.exists() and args.tex not in privacy_targets:
        privacy_targets.append(args.tex)
    errors.extend(validate_submission_privacy(privacy_targets))

    text = draft.read_text(encoding="utf-8")
    normalized_text = re.sub(r"\s+", " ", text)
    bib_text = bib.read_text(encoding="utf-8")
    errors.extend(validate_bibliography(bib_text))

    words = word_count(text)
    if words < args.min_words:
        errors.append(f"word count {words} is below minimum {args.min_words}")
    if args.max_words and words > args.max_words:
        errors.append(f"word count {words} exceeds maximum {args.max_words}")

    stale_targets = [draft] + [path for path in args.required_file if path.exists()]
    for target in stale_targets:
        target_text = target.read_text(encoding="utf-8")
        for pattern in args.stale_pattern:
            if re.search(re.escape(pattern), target_text):
                errors.append(f"stale marker found in {target}: {pattern}")

    for required in args.required_string:
        normalized_required = re.sub(r"\s+", " ", required)
        if normalized_required not in normalized_text:
            errors.append(f"required string missing from draft: {required}")

    cites = citation_keys(text)
    keys = bib_keys(bib_text)
    missing_bib = sorted(cites - keys)
    if missing_bib:
        errors.append(f"citation keys missing from BibTeX: {', '.join(missing_bib)}")

    inline_keys = inline_reference_keys(text)
    missing_inline = sorted(cites - inline_keys)
    if missing_inline:
        errors.append(
            "citation keys missing inline reference entries: "
            + ", ".join(missing_inline)
        )

    for image in image_paths(text):
        path = Path(image)
        if not path.is_absolute():
            path = draft.parent / path
        if not path.exists():
            errors.append(f"image path does not exist: {image}")
            continue
        if path.suffix.lower() == ".svg":
            try:
                ET.parse(path)
            except ET.ParseError as exc:
                errors.append(f"SVG does not parse: {image}: {exc}")

    tex_path = args.tex
    if tex_path is not None:
        errors.extend(validate_latex_scaffold(tex_path))
    if tex_path is not None and tex_path.exists():
        tex_text = tex_path.read_text(encoding="utf-8")
        tex_cites = latex_citation_keys(tex_text)
        missing_tex_bib = sorted(tex_cites - keys)
        if missing_tex_bib:
            errors.append(
                "LaTeX citation keys missing from BibTeX: "
                + ", ".join(missing_tex_bib)
            )
    else:
        tex_text = None

    errors.extend(validate_latex_draft_alignment(text, tex_text))

    if getattr(args, "check_run_status_claims", True):
        errors.extend(validate_run_status_claims(text, tex_text))
        errors.extend(validate_run_status_document(Path("docs/LM4SCI_RUN_STATUS_20260623.md")))
        errors.extend(
            validate_rerun_manifest_readme(
                Path("data/eval/rerun_manifests/lm4sci_20260623/README.md")
            )
        )
        errors.extend(validate_audit_proposal())

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--draft",
        type=Path,
        default=Path("docs/paper_workshop_compact_20260623.md"),
    )
    parser.add_argument(
        "--bib",
        type=Path,
        default=Path("docs/paper_references.bib"),
    )
    parser.add_argument(
        "--tex",
        type=Path,
        default=Path("docs/workshop_submission/main.tex"),
        help="LaTeX scaffold to sanity-check; pass an empty value only via tests.",
    )
    parser.add_argument("--min-words", type=int, default=3000)
    parser.add_argument("--max-words", type=int, default=5000)
    parser.add_argument(
        "--stale-pattern",
        action="append",
        default=list(DEFAULT_STALE_PATTERNS),
    )
    parser.add_argument(
        "--required-string",
        action="append",
        default=list(DEFAULT_REQUIRED_STRINGS),
    )
    parser.add_argument(
        "--required-file",
        action="append",
        type=Path,
        default=[Path(path) for path in DEFAULT_REQUIRED_FILES],
    )
    parser.add_argument(
        "--skip-run-status-claims",
        action="store_false",
        dest="check_run_status_claims",
        help="Skip validation that draft/TeX frontier numbers match paper_run_status.py.",
    )
    args = parser.parse_args(argv)

    errors = validate(args)
    if errors:
        print("Paper package validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    words = word_count(args.draft.read_text(encoding="utf-8"))
    cites = citation_keys(args.draft.read_text(encoding="utf-8"))
    images = image_paths(args.draft.read_text(encoding="utf-8"))
    print(
        f"Paper package validation passed: {words} words, "
        f"{len(cites)} citation keys, {len(images)} embedded images."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
