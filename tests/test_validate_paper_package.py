from __future__ import annotations

import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_validator_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_paper_package.py"
    spec = importlib.util.spec_from_file_location("validate_paper_package", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load validate_paper_package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PaperPackageValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_validator_module()

    def args_for(self, draft: Path, bib: Path, **overrides):
        args = {
            "draft": draft,
            "bib": bib,
            "min_words": 1,
            "max_words": 1000,
            "stale_pattern": ["TODO"],
            "required_string": ["audit arbitration"],
            "required_file": [],
            "tex": None,
            "check_run_status_claims": False,
        }
        args.update(overrides)
        return argparse.Namespace(**args)

    def test_required_string_ignores_markdown_line_wrapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft.md"
            bib = root / "refs.bib"
            draft.write_text(
                "# Title\n\nThis mentions audit\narbitration across a line break.\n",
                encoding="utf-8",
            )
            bib.write_text("", encoding="utf-8")

            errors = self.validator.validate(self.args_for(draft, bib))

        self.assertEqual(errors, [])

    def test_missing_citation_key_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft.md"
            bib = root / "refs.bib"
            draft.write_text(
                "# Title\n\nThis cites [Known; Missing] and mentions audit arbitration.\n\n"
                "[Known] Inline reference.\n[Missing] Inline reference.\n",
                encoding="utf-8",
            )
            bib.write_text("@article{Known,\n  title={Known}\n}\n", encoding="utf-8")

            errors = self.validator.validate(self.args_for(draft, bib))

        self.assertIn("citation keys missing from BibTeX: Missing", errors)

    def test_missing_inline_reference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft.md"
            bib = root / "refs.bib"
            draft.write_text(
                "# Title\n\nThis cites [Known] and mentions audit arbitration.\n",
                encoding="utf-8",
            )
            bib.write_text("@article{Known,\n  title={Known}\n}\n", encoding="utf-8")

            errors = self.validator.validate(self.args_for(draft, bib))

        self.assertIn("citation keys missing inline reference entries: Known", errors)

    def test_missing_required_package_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft.md"
            bib = root / "refs.bib"
            missing = root / "missing.md"
            draft.write_text(
                "# Title\n\nThis mentions audit arbitration.\n",
                encoding="utf-8",
            )
            bib.write_text("", encoding="utf-8")

            errors = self.validator.validate(
                self.args_for(draft, bib, required_file=[missing])
            )

        self.assertIn(f"required package file does not exist: {missing}", errors)

    def test_latex_scaffold_requires_document_and_bibliography(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.tex"
            path.write_text(
                "\\title{Title}\n\\begin{document}\n\\begin{abstract}A\\end{abstract}\n"
                "\\bibliography{wrong}\n\\end{document}\n",
                encoding="utf-8",
            )

            errors = self.validator.validate_latex_scaffold(path)

        self.assertIn(
            f"LaTeX scaffold does not reference ../paper_references bibliography: {path}",
            errors,
        )

    def test_latex_scaffold_runs_colm_submission_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            submission = docs / "workshop_submission"
            submission.mkdir(parents=True)
            tex = submission / "main.tex"
            tex.write_text(
                "\\documentclass{article}\n"
                "\\usepackage[submission]{colm2026_conference}\n"
                "\\title{Title}\n"
                "\\begin{document}\n"
                "\\begin{abstract}A\\end{abstract}\n"
                "\\includegraphics{figures/figure1_three_stage_funnel.pdf}\n"
                "\\includegraphics{figures/figure2_judge_variance_floor.pdf}\n"
                "\\bibliographystyle{colm2026_conference}\n"
                "\\bibliography{../paper_references}\n"
                "\\end{document}\n",
                encoding="utf-8",
            )

            errors = self.validator.validate_latex_scaffold(tex)

        self.assertTrue(any("missing COLM template file" in error for error in errors))
        self.assertTrue(any("missing figure asset" in error for error in errors))

    def test_latex_citation_key_extraction(self) -> None:
        text = "\\citep{MedPaLM, MedMCQA}\\citet{RAG}"

        keys = self.validator.latex_citation_keys(text)

        self.assertEqual(keys, {"MedPaLM", "MedMCQA", "RAG"})

    def test_bibliography_validation_reports_duplicate_and_missing_fields(self) -> None:
        bib = (
            "@article{Known,\n"
            "  title = {Known},\n"
            "  author = {A. Author},\n"
            "  year = {2026},\n"
            "  journal = {Journal}\n"
            "}\n"
            "@inproceedings{MissingFields,\n"
            "  title = {Missing},\n"
            "  url = {https://example.com}\n"
            "}\n"
            "@misc{Known,\n"
            "  title = {Duplicate},\n"
            "  author = {A. Author},\n"
            "  year = {2026},\n"
            "  url = {https://example.com}\n"
            "}\n"
        )

        errors = self.validator.validate_bibliography(bib)

        self.assertIn("duplicate BibTeX keys: Known", errors)
        self.assertIn("BibTeX entry Known missing DOI or URL", errors)
        self.assertIn("BibTeX entry MissingFields missing required field: author", errors)
        self.assertIn("BibTeX entry MissingFields missing required field: year", errors)
        self.assertIn("BibTeX entry MissingFields missing journal/booktitle", errors)

    def test_validate_reports_latex_citation_missing_from_bibtex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft.md"
            bib = root / "refs.bib"
            tex = root / "main.tex"
            draft.write_text(
                "# Title\n\nThis mentions audit arbitration.\n",
                encoding="utf-8",
            )
            bib.write_text(
                "@article{Known,\n"
                "  title = {Known},\n"
                "  author = {A. Author},\n"
                "  year = {2026},\n"
                "  doi = {10.1234/example},\n"
                "  journal = {Journal}\n"
                "}\n",
                encoding="utf-8",
            )
            tex.write_text(
                "\\title{Title}\n"
                "\\begin{document}\n"
                "\\begin{abstract}A\\end{abstract}\n"
                "\\citep{Known,Missing}\n"
                "\\bibliography{../paper_references}\n"
                "\\end{document}\n",
                encoding="utf-8",
            )

            errors = self.validator.validate(self.args_for(draft, bib, tex=tex))

        self.assertIn("LaTeX citation keys missing from BibTeX: Missing", errors)

    def test_submission_privacy_allows_policy_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.md"
            path.write_text(
                "Private or uncertain-license materials are excluded from public artifacts.",
                encoding="utf-8",
            )

            errors = self.validator.validate_submission_privacy([path])

        self.assertEqual(errors, [])

    def test_submission_privacy_reports_paths_private_sources_and_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.md"
            path.write_text(
                "Local path /Users/santoshg/Coding/NeurologyBM appears.\n"
                "DO NOT COMMIT materials and NEJM notes should not appear.\n"
                "A leaked key sk-1234567890abcdef should fail.\n"
                "OPENAI_API_KEY should fail too.\n",
                encoding="utf-8",
            )

            errors = self.validator.validate_submission_privacy([path])

        self.assertTrue(any("local absolute user path" in error for error in errors))
        self.assertTrue(any("external/private benchmark repo name" in error for error in errors))
        self.assertTrue(any("private-material directory marker" in error for error in errors))
        self.assertTrue(any("private/non-public source family" in error for error in errors))
        self.assertTrue(any("API key-like token" in error for error in errors))
        self.assertTrue(any("API key environment variable" in error for error in errors))

    def test_validate_audit_proposal_delegates_to_audit_validator(self) -> None:
        original = self.validator.audit_proposal_module

        class FakeAuditValidator:
            @staticmethod
            def validate(proposal, crossref, manifest):
                return [f"checked {proposal.name} {crossref.name} {manifest.name}"]

        self.validator.audit_proposal_module = lambda: FakeAuditValidator
        try:
            errors = self.validator.validate_audit_proposal()
        finally:
            self.validator.audit_proposal_module = original

        self.assertEqual(
            errors,
            ["checked AUDIT_ARBITRATION_PROPOSAL_20260623.md _crossref.csv flash_fail_postcutoff.jsonl"],
        )

    def test_heading_extraction_normalizes_numbered_markdown(self) -> None:
        markdown = "## 1. Introduction\n### 5.2 Post-Cutoff Contamination Control\n"
        tex = "\\section{Introduction}\n\\subsection{Post-Cutoff Contamination Control}\n"

        self.assertEqual(
            self.validator.markdown_heading_titles(markdown, 2),
            ["Introduction"],
        )
        self.assertEqual(
            self.validator.markdown_heading_titles(markdown, 3),
            ["Post-Cutoff Contamination Control"],
        )
        self.assertEqual(
            self.validator.latex_section_titles(tex, "subsection"),
            ["Post-Cutoff Contamination Control"],
        )

    def test_latex_draft_alignment_reports_missing_section_subsection_and_caveat(self) -> None:
        draft = (
            "## 1. Introduction\n"
            "## 5. Results\n"
            "### 5.1 Development Waves and Held-Out Generalization\n"
        )
        tex = (
            "\\section{Results}\n"
            "GPT-5.5 remains provisional. provider-default temperature. "
            "failure-selected rescue set. not a neutral leaderboard. "
            "\\texttt{not\\_run}."
        )

        errors = self.validator.validate_latex_draft_alignment(draft, tex)

        self.assertIn("LaTeX source missing core section from compact draft: Introduction", errors)
        self.assertIn(
            "LaTeX source missing Results subsection from compact draft: Development Waves and Held-Out Generalization",
            errors,
        )
        self.assertIn(
            "LaTeX source missing required reporting caveat: \\texttt{JUDGE\\_VOTES=3}",
            errors,
        )

    def test_latex_draft_alignment_accepts_core_structure_and_caveats(self) -> None:
        draft = "\n".join(
            [
                "## 1. Introduction",
                "## 2. Benchmark Construction",
                "## 3. ClinicalHarness",
                "## 4. Evaluation Protocol",
                "## 5. Results",
                "### 5.1 Generalization Across Waves",
                "### 5.2 Post-Cutoff Contamination Control",
                "### 5.3 Residual Failures Are Mostly Gold Artifacts",
                "### 5.4 Secondary Frontier-Model Panel",
                "## 6. Negative Ablations",
                "## 7. Discussion",
                "## 8. Limitations",
                "## 9. Data, Code, and Ethics",
            ]
        )
        tex = "\n".join(
            [
                "\\section{Introduction}",
                "\\section{Benchmark Construction}",
                "\\section{ClinicalHarness}",
                "\\section{Evaluation Protocol}",
                "\\section{Results}",
                "\\subsection{Generalization Across Waves}",
                "\\subsection{Post-Cutoff Contamination Control}",
                "\\subsection{Residual Failures Are Mostly Gold Artifacts}",
                "\\subsection{Secondary Frontier-Model Panel}",
                "\\section{Negative Ablations}",
                "\\section{Discussion}",
                "\\section{Limitations}",
                "\\section{Data, Code, and Ethics}",
                "GPT-5.5 remains provisional; provider-default temperature.",
                "This is a failure-selected rescue set, not a neutral leaderboard.",
                "\\texttt{not\\_run} and \\texttt{JUDGE\\_VOTES=3}.",
            ]
        )

        errors = self.validator.validate_latex_draft_alignment(draft, tex)

        self.assertEqual(errors, [])

    def test_run_status_claim_validation_accepts_current_cross_model_counts(self) -> None:
        original = self.validator.load_run_status
        self.validator.load_run_status = lambda: (
            68,
            {
                "gpt-5.4 bare Responses": {"score_pass": 49},
                "gpt-5.4 answerer + v4-pro reader": {
                    "pass_at_1": 40,
                    "pass_at_5": 52,
                    "score_not_run": 0,
                },
            },
        )
        try:
            draft = "| GPT-5.4 | 49 / 68 | 40 / 68 | 52 / 68 |"
            tex = "GPT-5.4 & 49 / 68 & 40 / 68 & 52 / 68"

            errors = self.validator.validate_run_status_claims(draft, tex)
        finally:
            self.validator.load_run_status = original

        self.assertEqual(errors, [])

    def test_run_status_claim_validation_reports_stale_counts(self) -> None:
        original = self.validator.load_run_status
        self.validator.load_run_status = lambda: (
            68,
            {
                "gpt-5.4 bare Responses": {"score_pass": 49},
                "gpt-5.4 answerer + v4-pro reader": {
                    "pass_at_1": 40,
                    "pass_at_5": 52,
                    "score_not_run": 0,
                },
            },
        )
        try:
            # draft has a stale bare top-1 (48 instead of 49) but correct harness cells
            draft = "| GPT-5.4 | 48 / 68 | 40 / 68 | 52 / 68 |"
            tex = "GPT-5.4 & 48 / 68 & 40 / 68 & 52 / 68"

            errors = self.validator.validate_run_status_claims(draft, tex)
        finally:
            self.validator.load_run_status = original

        self.assertTrue(any("GPT-5.4" in error and "bare top-1" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
