"""Provider-independent LLM access for OpenAI-compatible chat endpoints (Groq, Gemini, OpenRouter, ...).

Reliability rules:
- every call has a timeout and a bounded number of retries;
- a shared per-minute budget protects free-tier quotas (calls beyond it are skipped, not queued);
- on failure or rate-limiting the next provider in LLM_PROVIDER_ORDER is tried;
- ``complete`` never raises: it returns None, and callers fall back to deterministic behaviour.
API keys are only placed in the Authorization header and never logged or returned.
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.config import ProviderConfig, Settings

log = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    latency_ms: int

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


class LLMError(Exception):
    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


class ChatProvider(Protocol):
    name: str
    model: str

    async def chat(self, messages: list[dict[str, str]], *, max_tokens: int, temperature: float) -> str: ...


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig, client: httpx.AsyncClient, timeout: float):
        self.name = config.name
        self.model = config.model
        self._config = config
        self._client = client
        self._timeout = timeout

    async def chat(self, messages: list[dict[str, str]], *, max_tokens: int, temperature: float) -> str:
        headers = {"Authorization": f"Bearer {self._config.api_key.get_secret_value()}"}
        if self.name == "openrouter":
            headers["X-Title"] = "Off Script: The Last Light of Aether"
        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        try:
            r = await self._client.post(f"{self._config.base_url}/chat/completions", json=body, headers=headers,
                                        timeout=self._timeout)
        except httpx.TimeoutException:
            raise LLMError(f"{self.name}: timed out", retryable=True) from None
        except httpx.HTTPError as e:
            raise LLMError(f"{self.name}: network error ({type(e).__name__})", retryable=True) from None
        if r.status_code >= 400:
            # 429 / 5xx may succeed later or on another provider; 4xx (bad model, bad key) will not.
            retryable = r.status_code == 429 or r.status_code >= 500
            raise LLMError(f"{self.name}: HTTP {r.status_code} {r.text[:160]}", retryable=retryable)
        try:
            content = r.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError(f"{self.name}: malformed response", retryable=False) from None
        if not isinstance(content, str) or not content.strip():
            raise LLMError(f"{self.name}: empty response", retryable=False)
        return content.strip()


@dataclass
class LLMStats:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    skipped_budget: int = 0
    total_latency_ms: int = 0
    by_provider: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None

    def as_dict(self) -> dict:
        avg = self.total_latency_ms // self.successes if self.successes else 0
        return {"calls": self.calls, "successes": self.successes, "failures": self.failures,
                "skipped_budget": self.skipped_budget, "avg_latency_ms": avg,
                "by_provider": dict(self.by_provider), "last_error": self.last_error}


class LLMService:
    def __init__(self, providers: list[ChatProvider], *, max_calls_per_minute: int, max_retries: int,
                 concurrency: int = 2, clock=time.monotonic):
        self.providers = providers
        self.max_calls_per_minute = max_calls_per_minute
        self.max_retries = max_retries
        self.stats = LLMStats()
        self._recent: deque[float] = deque()
        self._clock = clock
        self._semaphore = asyncio.Semaphore(concurrency)

    @classmethod
    def from_settings(cls, settings: Settings, client: httpx.AsyncClient) -> "LLMService | None":
        if not settings.is_live_llm:
            return None
        providers = [OpenAICompatibleProvider(p, client, settings.llm_timeout_seconds) for p in settings.llm_providers]
        return cls(providers, max_calls_per_minute=settings.llm_max_calls_per_minute,
                   max_retries=settings.llm_max_retries)

    @property
    def labels(self) -> list[str]:
        return [f"{p.name}:{p.model}" for p in self.providers]

    def _take_budget(self) -> bool:
        now = self._clock()
        while self._recent and now - self._recent[0] >= 60:
            self._recent.popleft()
        if len(self._recent) >= self.max_calls_per_minute:
            return False
        self._recent.append(now)
        return True

    async def complete(self, messages: list[dict[str, str]], *, max_tokens: int = 200,
                       temperature: float = 0.7) -> LLMResponse | None:
        async with self._semaphore:
            for provider in self.providers:
                for attempt in range(self.max_retries + 1):
                    if not self._take_budget():
                        self.stats.skipped_budget += 1
                        return None
                    self.stats.calls += 1
                    started = self._clock()
                    try:
                        text = await provider.chat(messages, max_tokens=max_tokens, temperature=temperature)
                    except LLMError as e:
                        self.stats.failures += 1
                        self.stats.last_error = str(e)
                        log.warning("LLM call failed: %s", e)
                        if not e.retryable:
                            break  # try the next provider
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    latency = int((self._clock() - started) * 1000)
                    self.stats.successes += 1
                    self.stats.total_latency_ms += latency
                    self.stats.by_provider[provider.name] = self.stats.by_provider.get(provider.name, 0) + 1
                    return LLMResponse(text=text, provider=provider.name, model=provider.model, latency_ms=latency)
        return None
