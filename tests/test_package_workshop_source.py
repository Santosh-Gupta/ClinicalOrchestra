from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_package_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "package_workshop_source.py"
    spec = importlib.util.spec_from_file_location("package_workshop_source", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load package_workshop_source.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkshopSourcePackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.packager = load_package_module()

    def test_validate_bundle_reports_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            errors = self.packager.validate_bundle(Path(tmp))

        self.assertTrue(any("paper_references.bib" in error for error in errors))
        self.assertTrue(any("main.tex" in error for error in errors))

    def test_stage_bundle_preserves_expected_relative_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "bundle"

            staged = self.packager.stage_bundle(out_dir)
            errors = self.packager.validate_bundle(out_dir)

            main = out_dir / "workshop_submission" / "main.tex"
            bib = out_dir / "paper_references.bib"
            figure = out_dir / "workshop_submission" / "figures" / "figure1_three_stage_funnel.pdf"

            self.assertEqual(errors, [])
            self.assertIn(bib, staged)
            self.assertTrue(main.exists())
            self.assertTrue(bib.exists())
            self.assertTrue(figure.exists())


if __name__ == "__main__":
    unittest.main()
