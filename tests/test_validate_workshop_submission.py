from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


def load_preflight_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_workshop_submission.py"
    spec = importlib.util.spec_from_file_location("validate_workshop_submission", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load validate_workshop_submission.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WorkshopSubmissionPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preflight = load_preflight_module()

    def test_planned_steps_refresh_before_checks_by_default(self) -> None:
        names = [step.name for step in self.preflight.planned_steps()]

        self.assertEqual(names[0:6], [
            "build figure PDFs",
            "stage workshop source bundle",
            "preview audit cleanup manifests",
            "build audit approval packet",
            "export rerun manifests",
            "refresh run-status Markdown",
        ])
        self.assertIn("validate audit cleanup preview", names)
        self.assertIn("validate audit approval packet", names)
        self.assertIn("validate paper package", names)

    def test_check_only_skips_refresh_steps(self) -> None:
        names = [step.name for step in self.preflight.planned_steps(check_only=True)]

        self.assertNotIn("build figure PDFs", names)
        self.assertNotIn("stage workshop source bundle", names)
        self.assertNotIn("preview audit cleanup manifests", names)
        self.assertNotIn("build audit approval packet", names)
        self.assertEqual(names[0], "validate audit arbitration proposal")
        self.assertEqual(names[1], "validate audit cleanup preview")
        self.assertEqual(names[2], "validate audit approval packet")

    def test_run_preflight_returns_failing_step_code(self) -> None:
        original = self.preflight.planned_steps
        original_run = self.preflight.run_step

        self.preflight.planned_steps = lambda check_only=False: [
            self.preflight.Step("bad", ["false"])
        ]

        def fake_run_step(step):
            raise subprocess.CalledProcessError(7, step.command)

        self.preflight.run_step = fake_run_step
        try:
            code = self.preflight.run_preflight()
        finally:
            self.preflight.planned_steps = original
            self.preflight.run_step = original_run

        self.assertEqual(code, 7)


if __name__ == "__main__":
    unittest.main()
