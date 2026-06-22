"""Minimal OpenAI-compatible chat client for benchmark runs."""

from __future__ import annotations

import http.client
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .ratelimit import NoOpRateLimiter, RateLimiter, SlidingWindowRateLimiter

# Transient HTTP statuses worth retrying: 429 (concurrency limit exceeded) and common gateway
# errors. DeepSeek returns 429 when the account-level concurrency cap (500 pro / 2500 flash) is hit.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def _estimate_tokens(prompt: str, max_tokens: int) -> int:
    """Rough upper bound for TPM budgeting: prompt tokens (~4 chars/token) + reserved completion."""
    return len(prompt) // 4 + max_tokens


_shared_rate_limiter: RateLimiter | None = None
_shared_rate_limiter_lock = threading.Lock()


def _env_rate_limiter() -> RateLimiter | None:
    """Build one process-wide limiter from MODEL_MAX_RPM / MODEL_MAX_TPM, shared across clients.

    Rate caps are account-level, so the answer client, judge client, and every worker thread must
    share a single limiter instance. Returns None (no throttle) when neither env var is set, which
    is the DeepSeek default.
    """
    global _shared_rate_limiter
    rpm = os.getenv("MODEL_MAX_RPM")
    tpm = os.getenv("MODEL_MAX_TPM")
    if not rpm and not tpm:
        return None
    with _shared_rate_limiter_lock:
        if _shared_rate_limiter is None:
            _shared_rate_limiter = SlidingWindowRateLimiter(
                max_requests=int(rpm) if rpm else None,
                max_tokens=int(tpm) if tpm else None,
            )
    return _shared_rate_limiter


@dataclass(frozen=True)
class ChatCompletionResult:
    model: str
    content: str
    raw: dict[str, Any]
    latency_ms: int


class OpenAICompatibleChatClient:
    """Small standard-library client for /chat/completions APIs."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
        backoff_cap_seconds: float = 30.0,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_cap_seconds = backoff_cap_seconds
        # No-op by default (DeepSeek is concurrency-limited, not rate-limited). Providers with
        # RPM/TPM caps pass a shared SlidingWindowRateLimiter so requests are throttled proactively.
        self.rate_limiter: RateLimiter = rate_limiter or NoOpRateLimiter()

    @classmethod
    def from_env(cls, *, model: str | None = None) -> "OpenAICompatibleChatClient":
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com"
        resolved_model = model or os.getenv("DEEPSEEK_MODEL") or os.getenv("OPENAI_MODEL") or "deepseek-v4-flash"
        timeout_seconds = float(os.getenv("MODEL_TIMEOUT_SECONDS", "120"))
        max_retries = int(os.getenv("MODEL_MAX_RETRIES", "5"))
        if not api_key:
            raise ValueError(
                "No model API key found. Set DEEPSEEK_API_KEY for DeepSeek or OPENAI_API_KEY for another "
                "OpenAI-compatible endpoint."
            )
        return cls(
            api_key=api_key,
            base_url=base_url,
            model=resolved_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            rate_limiter=_env_rate_limiter(),
        )

    def _retry_delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.backoff_cap_seconds)
            except ValueError:
                pass
        # Exponential backoff with full jitter so concurrent workers don't retry in lockstep.
        ceiling = min(self.backoff_base_seconds * (2**attempt), self.backoff_cap_seconds)
        return random.uniform(0.0, ceiling)

    def chat(self, *, prompt: str, temperature: float = 0.0, max_tokens: int = 4096) -> ChatCompletionResult:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a benchmark diagnostic reasoning model. Return only valid JSON. "
                        "Do not include hidden chain-of-thought."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        token_estimate = _estimate_tokens(prompt, max_tokens)
        started = time.monotonic()
        raw: dict[str, Any] | None = None
        for attempt in range(self.max_retries + 1):
            # Proactively wait for RPM/TPM headroom before sending. Each retry is a real request to
            # the provider, so it must re-acquire (no-op under the DeepSeek default).
            self.rate_limiter.acquire(tokens=token_estimate)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code in _RETRYABLE_STATUS and attempt < self.max_retries:
                    time.sleep(self._retry_delay(attempt, exc.headers.get("Retry-After")))
                    continue
                body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"model API HTTP {exc.code}: {body[:1000]}") from exc
            except (urllib.error.URLError, TimeoutError, http.client.HTTPException, OSError) as exc:
                # Transient connection faults (incl. RemoteDisconnected / reset sockets) are common
                # under concurrency; retry with backoff before giving up.
                if attempt < self.max_retries:
                    time.sleep(self._retry_delay(attempt, None))
                    continue
                raise RuntimeError(f"model API request failed after {attempt + 1} attempts: {exc}") from exc
        assert raw is not None
        latency_ms = int((time.monotonic() - started) * 1000)
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("model API response did not contain choices")
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise RuntimeError("model API response did not contain message.content")
        return ChatCompletionResult(model=self.model, content=message["content"], raw=raw, latency_ms=latency_ms)
