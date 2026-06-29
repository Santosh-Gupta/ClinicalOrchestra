from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_budget_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_workshop_page_budget.py"
    spec = importlib.util.spec_from_file_location("validate_workshop_page_budget", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load validate_workshop_page_budget.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkshopPageBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.budget = load_budget_module()

    def test_main_content_excludes_references_and_readiness_note(self) -> None:
        markdown = (
            "# Title\n\n"
            "preface words\n"
            "## Abstract\nmain words here\n"
            "## References\nreference words ignored\n"
            "## Submission Readiness Note\nalso ignored\n"
        )

        main = self.budget.main_content_markdown(markdown)

        self.assertIn("main words here", main)
        self.assertNotIn("reference words ignored", main)
        self.assertNotIn("preface words", main)

    def test_float_counts(self) -> None:
        tex = "\\begin{figure}\n\\end{figure}\n\\begin{table}\n\\end{table}\n"

        self.assertEqual(self.budget.float_counts(tex), (1, 1))

    def test_validate_passes_current_sized_fixture_and_fails_too_large(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft.md"
            tex = root / "main.tex"
            draft.write_text("## Abstract\n" + ("word " * 650), encoding="utf-8")
            tex.write_text("\\begin{figure}\n\\end{figure}\n", encoding="utf-8")

            errors, metrics = self.budget.validate(draft, tex, max_pages=2.0)
            too_large, _ = self.budget.validate(draft, tex, max_pages=1.0)

        self.assertEqual(errors, [])
        self.assertEqual(metrics["words"], 651)
        self.assertTrue(any("exceeds local budget" in error for error in too_large))


if __name__ == "__main__":
    unittest.main()
