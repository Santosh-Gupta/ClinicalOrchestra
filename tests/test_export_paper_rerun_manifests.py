from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def load_export_module():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    script = scripts / "export_paper_rerun_manifests.py"
    spec = importlib.util.spec_from_file_location("export_paper_rerun_manifests", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load export_paper_rerun_manifests.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ExportPaperRerunManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exporter = load_export_module()

    def test_slugify_lane_name(self) -> None:
        self.assertEqual(
            self.exporter.slugify("gpt-5.5 answerer + v4-pro reader"),
            "gpt_5_5_answerer_v4_pro_reader",
        )

    def test_provisional_lane_exports_all_case_ids(self) -> None:
        lane = self.exporter.paper_run_status.Lane(
            "fake",
            Path("does-not-exist.jsonl"),
            "bare",
            "provisional",
            "rerun all",
        )
        manifest_rows = {"a": {"case_id": "a"}, "b": {"case_id": "b"}}

        case_ids = self.exporter.incomplete_case_ids(lane, manifest_rows)

        self.assertEqual(case_ids, ["a", "b"])

    def test_remove_stale_jsonl_keeps_non_jsonl_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            stale = out_dir / "stale.jsonl"
            readme = out_dir / "README.md"
            stale.write_text("{}\n", encoding="utf-8")
            readme.write_text("# README\n", encoding="utf-8")

            self.exporter.remove_stale_jsonl(out_dir)

            self.assertFalse(stale.exists())
            self.assertTrue(readme.exists())


if __name__ == "__main__":
    unittest.main()
