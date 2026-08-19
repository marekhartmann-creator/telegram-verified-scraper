"""HTTP layer.

Plain httpx against the server-rendered preview. No browser: a headless Chrome
would multiply this Actor's memory footprint (and therefore the customer's bill)
for pages that are static HTML anyway.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any

import httpx

BASE = "https://t.me"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class FetchResult:
    """One HTTP attempt, success or not — never silently collapsed to ''."""

    url: str
    status: int | None = None
    html: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == 200 and bool(self.html)


@dataclass
class FetchStats:
    requests: int = 0
    retries: int = 0
    failures: list[str] = field(default_factory=list)


class TelegramClient:
    """Retrying fetcher for t.me pages."""

    def __init__(
        self,
        *,
        proxy_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        min_delay: float = 0.25,
    ) -> None:
        self._client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            follow_redirects=True,
            proxy=proxy_url,
        )
        self.max_retries = max_retries
        self.min_delay = min_delay
        self.stats = FetchStats()

    async def __aenter__(self) -> "TelegramClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def get(self, url: str) -> FetchResult:
        last = FetchResult(url=url)
        for attempt in range(self.max_retries):
            if attempt:
                self.stats.retries += 1
                await asyncio.sleep(min(8.0, 2**attempt) + random.random())
            try:
                self.stats.requests += 1
                response = await self._client.get(url)
            except Exception as exc:  # noqa: BLE001 - reported, never swallowed
                last = FetchResult(url=url, error=f"{type(exc).__name__}: {exc}")
                continue

            if response.status_code == 200:
                await asyncio.sleep(self.min_delay)
                return FetchResult(url=url, status=200, html=response.text)

            last = FetchResult(
                url=url,
                status=response.status_code,
                error=f"HTTP {response.status_code}",
            )
            # 4xx other than rate limiting will not improve on retry.
            if response.status_code < 500 and response.status_code != 429:
                break

        if last.error:
            self.stats.failures.append(f"{url} -> {last.error}")
        return last

    async def preview_page(self, handle: str, before: int | None = None) -> FetchResult:
        url = f"{BASE}/s/{handle}"
        if before is not None:
            url = f"{url}?before={before}"
        return await self.get(url)

    async def plain_page(self, handle: str) -> FetchResult:
        return await self.get(f"{BASE}/{handle}")
