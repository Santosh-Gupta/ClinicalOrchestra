import threading
import time
import unittest

from clinical_harness.ratelimit import (
    NoOpRateLimiter,
    SlidingWindowRateLimiter,
)


class RateLimitTests(unittest.TestCase):
    def test_noop_never_blocks(self) -> None:
        limiter = NoOpRateLimiter()
        start = time.monotonic()
        for _ in range(1000):
            limiter.acquire(tokens=10_000)
        self.assertLess(time.monotonic() - start, 0.5)

    def test_requires_at_least_one_limit(self) -> None:
        with self.assertRaises(ValueError):
            SlidingWindowRateLimiter()

    def test_request_rate_blocks_until_window_frees(self) -> None:
        # 2 requests per 0.3s window: the 3rd must wait ~one window.
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=0.3)
        limiter.acquire()
        limiter.acquire()
        start = time.monotonic()
        limiter.acquire()  # blocks until the first ages out
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.2)

    def test_token_budget_blocks(self) -> None:
        limiter = SlidingWindowRateLimiter(max_tokens=100, window_seconds=0.3)
        limiter.acquire(tokens=80)
        start = time.monotonic()
        limiter.acquire(tokens=80)  # 160 > 100 -> wait for the first to expire
        self.assertGreaterEqual(time.monotonic() - start, 0.2)

    def test_oversized_single_request_does_not_deadlock(self) -> None:
        limiter = SlidingWindowRateLimiter(max_tokens=100, window_seconds=5.0)
        start = time.monotonic()
        limiter.acquire(tokens=10_000)  # bigger than the whole budget: admit, don't hang
        self.assertLess(time.monotonic() - start, 0.5)

    def test_thread_safe_and_respects_request_ceiling(self) -> None:
        # 5 req / 0.5s window; 4 threads x 5 acquires = 20 requests must take >= ~3 windows.
        limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=0.5)
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(5):
                    limiter.acquire()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        start = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.monotonic() - start
        self.assertEqual(errors, [])
        # 20 requests at 5 per 0.5s => at least 3 full windows of waiting.
        self.assertGreaterEqual(elapsed, 1.0)

    def test_model_client_defaults_to_noop(self) -> None:
        from clinical_harness.model_client import OpenAICompatibleChatClient
        client = OpenAICompatibleChatClient(api_key="k", base_url="http://x", model="m")
        self.assertIsInstance(client.rate_limiter, NoOpRateLimiter)

    def test_responses_text_extracts_output_parts(self) -> None:
        from clinical_harness.model_client import _responses_text

        raw = {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": '{"final_diagnosis": "x"'},
                        {"type": "output_text", "text": '}'},
                    ]
                }
            ]
        }
        self.assertEqual(_responses_text(raw), '{"final_diagnosis": "x"}')


if __name__ == "__main__":
    unittest.main()
