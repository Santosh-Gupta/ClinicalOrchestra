import json
import unittest

from clinical_harness import cli


class CliViewerTests(unittest.TestCase):
    def test_retrieval_guided_eval_accepts_viewer_url(self) -> None:
        parser = cli.build_parser()

        args = parser.parse_args(
            [
                "benchmark",
                "retrieval-guided-eval",
                "--out-dir",
                "runs/test",
                "--viewer-url",
                "http://127.0.0.1:8000",
            ]
        )

        self.assertEqual(args.viewer_url, "http://127.0.0.1:8000")

    def test_viewer_emitter_posts_event_payload(self) -> None:
        calls = []
        original = cli.urlopen

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        def fake_urlopen(request, timeout):
            calls.append((request, timeout))
            return _Response()

        cli.urlopen = fake_urlopen
        try:
            emitter = cli._viewer_emitter("http://viewer.local/")
            emitter({"type": "case_started", "run_id": "r", "case_id": "c"})
        finally:
            cli.urlopen = original

        request, timeout = calls[0]
        self.assertEqual(timeout, 2)
        self.assertEqual(request.full_url, "http://viewer.local/api/live/events")
        self.assertEqual(json.loads(request.data.decode("utf-8"))["type"], "case_started")
        self.assertEqual(request.get_method(), "POST")


if __name__ == "__main__":
    unittest.main()
