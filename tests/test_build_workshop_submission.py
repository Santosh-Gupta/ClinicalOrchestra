from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_build_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_workshop_submission.py"
    spec = importlib.util.spec_from_file_location("build_workshop_submission", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load build_workshop_submission.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkshopSubmissionBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = load_build_module()

    def _write_template_files(self, submission: Path) -> None:
        for name in (
            "colm2026_conference.sty",
            "colm2026_conference.bst",
            "fancyhdr.sty",
            "natbib.sty",
        ):
            (submission / name).write_text("% test fixture\n", encoding="utf-8")

    def _write_figure_files(self, submission: Path) -> None:
        figures = submission / "figures"
        figures.mkdir()
        for name in ("figure1_three_stage_funnel.pdf", "figure2_judge_variance_floor.pdf"):
            (figures / name).write_bytes(b"%PDF-1.4\n%%EOF\n")

    def _minimal_tex(self, *, extra: str = "") -> str:
        return (
            "\\documentclass{article}\n"
            "\\usepackage[submission]{colm2026_conference}\n"
            "\\author{Anonymous Authors}\n"
            "\\begin{document}\n"
            "\\includegraphics{figures/figure1_three_stage_funnel.pdf}\n"
            "\\includegraphics{figures/figure2_judge_variance_floor.pdf}\n"
            f"{extra}\n"
            "\\bibliographystyle{colm2026_conference}\n"
            "\\bibliography{../paper_references}\n"
            "\\end{document}\n"
        )

    def test_check_inputs_accepts_minimal_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            submission = docs / "workshop_submission"
            submission.mkdir(parents=True)
            self._write_template_files(submission)
            self._write_figure_files(submission)
            tex = submission / "main.tex"
            tex.write_text(self._minimal_tex(), encoding="utf-8")
            (docs / "paper_references.bib").write_text("", encoding="utf-8")

            errors = self.builder.check_inputs(tex)

        self.assertEqual(errors, [])

    def test_check_inputs_reports_missing_bibliography(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tex = Path(tmp) / "docs" / "workshop_submission" / "main.tex"
            tex.parent.mkdir(parents=True)
            self._write_template_files(tex.parent)
            self._write_figure_files(tex.parent)
            tex.write_text(self._minimal_tex(), encoding="utf-8")

            errors = self.builder.check_inputs(tex)

        self.assertTrue(any("missing bibliography" in error for error in errors))

    def test_check_inputs_rejects_generic_geometry_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            submission = docs / "workshop_submission"
            submission.mkdir(parents=True)
            self._write_template_files(submission)
            self._write_figure_files(submission)
            tex = submission / "main.tex"
            tex.write_text(
                self._minimal_tex(
                    extra="\\usepackage[margin=1in]{geometry}\n\\bibliographystyle{plainnat}"
                ),
                encoding="utf-8",
            )
            (docs / "paper_references.bib").write_text("", encoding="utf-8")

            errors = self.builder.check_inputs(tex)

        self.assertTrue(any("geometry" in error for error in errors))
        self.assertTrue(any("plainnat" in error for error in errors))

    def test_check_inputs_rejects_identifying_author_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            submission = docs / "workshop_submission"
            submission.mkdir(parents=True)
            self._write_template_files(submission)
            self._write_figure_files(submission)
            tex = submission / "main.tex"
            tex.write_text(
                self._minimal_tex(extra="ClinicalHarness Contributors\nDepartment of Diagnosis"),
                encoding="utf-8",
            )
            (docs / "paper_references.bib").write_text("", encoding="utf-8")

            errors = self.builder.check_inputs(tex)

        self.assertTrue(any("ClinicalHarness Contributors" in error for error in errors))
        self.assertTrue(any("Department of" in error for error in errors))

    def test_check_inputs_reports_missing_figure_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            submission = docs / "workshop_submission"
            submission.mkdir(parents=True)
            self._write_template_files(submission)
            tex = submission / "main.tex"
            tex.write_text(self._minimal_tex(), encoding="utf-8")
            (docs / "paper_references.bib").write_text("", encoding="utf-8")

            errors = self.builder.check_inputs(tex)

        self.assertTrue(any("missing figure asset" in error for error in errors))

    def test_check_inputs_rejects_unicode_and_markdown_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            submission = docs / "workshop_submission"
            submission.mkdir(parents=True)
            self._write_template_files(submission)
            self._write_figure_files(submission)
            tex = submission / "main.tex"
            tex.write_text(
                self._minimal_tex(extra="# Markdown heading\nTODO: tighten claim\nnaive cafe"),
                encoding="utf-8",
            )
            tex.write_text(tex.read_text(encoding="utf-8").replace("naive cafe", "naive cafe é"), encoding="utf-8")
            (docs / "paper_references.bib").write_text("", encoding="utf-8")

            errors = self.builder.check_inputs(tex)

        self.assertTrue(any("non-ASCII" in error for error in errors))
        self.assertTrue(any("TODO" in error for error in errors))
        self.assertTrue(any("markdown heading" in error for error in errors))

    def test_check_inputs_rejects_placeholder_fbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            submission = docs / "workshop_submission"
            submission.mkdir(parents=True)
            self._write_template_files(submission)
            self._write_figure_files(submission)
            tex = submission / "main.tex"
            tex.write_text(self._minimal_tex(extra="\\fbox{placeholder figure}"), encoding="utf-8")
            (docs / "paper_references.bib").write_text("", encoding="utf-8")

            errors = self.builder.check_inputs(tex)

        self.assertTrue(any("\\fbox" in error for error in errors))

    def test_check_inputs_rejects_unbalanced_core_environments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            submission = docs / "workshop_submission"
            submission.mkdir(parents=True)
            self._write_template_files(submission)
            self._write_figure_files(submission)
            tex = submission / "main.tex"
            tex.write_text(self._minimal_tex(extra="\\begin{figure}\nmissing close"), encoding="utf-8")
            (docs / "paper_references.bib").write_text("", encoding="utf-8")

            errors = self.builder.check_inputs(tex)

        self.assertTrue(any("unbalanced figure" in error for error in errors))

    def test_float_hygiene_accepts_captioned_labeled_float_and_reference(self) -> None:
        text = (
            "\\begin{figure}[t]\n"
            "\\caption{A figure.}\n"
            "\\label{fig:one}\n"
            "\\end{figure}\n"
            "See Figure~\\ref{fig:one}.\n"
            "\\begin{table}[t]\n"
            "\\caption{A table.}\n"
            "\\label{tab:one}\n"
            "\\end{table}\n"
        )

        errors = self.builder.validate_float_and_label_hygiene(text, Path("main.tex"))

        self.assertEqual(errors, [])

    def test_float_hygiene_rejects_missing_caption_label_and_bad_prefix(self) -> None:
        text = (
            "\\begin{figure}[t]\n"
            "\\label{tab:wrong}\n"
            "\\end{figure}\n"
            "\\begin{table}[t]\n"
            "\\caption{A table.}\n"
            "\\end{table}\n"
        )

        errors = self.builder.validate_float_and_label_hygiene(text, Path("main.tex"))

        self.assertTrue(any("figure environment missing caption" in error for error in errors))
        self.assertTrue(any("figure label tab:wrong should start with fig:" in error for error in errors))
        self.assertTrue(any("table environment missing label" in error for error in errors))

    def test_float_hygiene_rejects_duplicate_labels_and_unresolved_refs(self) -> None:
        text = (
            "\\begin{figure}[t]\n"
            "\\caption{A figure.}\n"
            "\\label{fig:dup}\n"
            "\\end{figure}\n"
            "\\begin{figure}[t]\n"
            "\\caption{Another figure.}\n"
            "\\label{fig:dup}\n"
            "\\end{figure}\n"
            "\\ref{fig:missing}\n"
        )

        errors = self.builder.validate_float_and_label_hygiene(text, Path("main.tex"))

        self.assertIn("duplicate LaTeX label fig:dup: main.tex", errors)
        self.assertIn("LaTeX reference has no matching label fig:missing: main.tex", errors)


if __name__ == "__main__":
    unittest.main()
