# LM4Sci/COLM LaTeX Scaffold

This directory contains the LaTeX conversion scaffold for the compact workshop draft. The target venue
is LM4Sci 2026, which requires the COLM 2026 template.

- Latest handoff for the paper package: `../HANDOFF_20260624.md`
- Source Markdown: `../paper_workshop_compact_20260623.md`
- LaTeX scaffold: `main.tex`
- Bibliography source: `../paper_references.bib`
- Figure sources: `../paper_figures/`
- Generated PDF figures for LaTeX: `figures/figure1_three_stage_funnel.pdf`,
  `figures/figure2_judge_variance_floor.pdf`
- Vendored COLM 2026 files from <https://github.com/COLM-org/Template/releases/tag/2026>:
  `colm2026_conference.sty`, `colm2026_conference.bst`, `fancyhdr.sty`, `natbib.sty`,
  `math_commands.tex`

The scaffold now uses `\usepackage[submission]{colm2026_conference}` and the COLM bibliography style.
Do not add `geometry` or font packages that alter template dimensions. The TeX source includes generated
PDF versions of the two SVG figures; regenerate them with `python3.11 scripts/build_paper_figures.py`
after changing figure content. The scaffold checker also rejects non-ASCII TeX, Markdown leftovers,
placeholder markers, unbalanced core figure/table environments, missing float captions/labels,
incorrect `fig:`/`tab:` label prefixes, duplicate labels, and unresolved `\ref`-style references. Keep
the caveats from `../WORKSHOP_CLAIM_EVIDENCE_MATRIX_20260623.md`.

Before treating the submission package as current, run:

```bash
python3.11 scripts/validate_workshop_submission.py
PYTHONPATH=src python3.11 -m unittest discover -s tests
```

Use `python3.11 scripts/validate_workshop_submission.py --check-only` when generated artifacts have
already been refreshed and you only want the validators/status checks.

The preflight also stages a portable source bundle under `build/lm4sci_submission_source/`, writes the
audit cleanup preview under `build/audit_arbitration_preview/`, and regenerates the user-veto packet at
`../AUDIT_ARBITRATION_APPROVAL_PACKET_20260623.md`. To compile on another machine, copy the source
bundle directory and run the LaTeX build from `build/lm4sci_submission_source/workshop_submission` so
`main.tex` can resolve `../paper_references.bib`.

The package validator checks both Markdown and LaTeX citation coverage: compact-draft inline references,
BibTeX duplicate keys and required fields, DOI-or-URL coverage, and `main.tex` citation keys resolving
against `../paper_references.bib`. It also checks that frontier-model and harness numeric claims in the
compact draft/LaTeX source match `scripts/paper_run_status.py`, that
`../LM4SCI_RUN_STATUS_20260623.md` matches the script-rendered Markdown, and that the generated rerun
manifest README matches the JSONL files on disk. Finally, it checks that `main.tex` preserves the
compact draft's core scientific sections, Results subsections, and required reporting caveats, and scans
submission-facing files for local paths, private-source names, user names, and API-key-like tokens.

To compile on a machine with LaTeX installed:

```bash
python3.11 scripts/build_workshop_submission.py --build
```

The current Codex environment may not have `latexmk` or `pdflatex`; in that case the check command still
validates scaffold inputs and reports that no builder is installed.
