"""Per-channel orchestration: preflight -> paginate -> verify."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .errors import ChannelState
from .fetch import TelegramClient
from .parse import parse_channel_info, parse_page
from .preflight import classify, looks_like_preview
from .verify import ChannelReport, build_report

_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{4,64}$")


def normalize_handle(raw: str) -> str | None:
    """'https://t.me/s/durov?before=1', '@durov', 'durov' -> 'durov'."""
    if not raw:
        return None
    value = raw.strip()
    value = re.sub(r"^https?://", "", value, flags=re.I)
    value = re.sub(r"^(www\.)?(t(elegram)?\.me|telegram\.dog)/", "", value, flags=re.I)
    value = re.sub(r"^s/", "", value, flags=re.I)
    value = value.split("?")[0].split("#")[0].strip("/@ ")
    return value if _HANDLE_RE.match(value) else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass
class ScrapeOptions:
    max_posts: int = 100          # 0 == no limit
    min_date: datetime | None = None
    max_date: datetime | None = None
    search_terms: tuple[str, ...] = ()
    include_media: bool = True
    include_html: bool = False    # raw post HTML roughly doubles item size
    max_pages: int = 500          # hard stop, protects the customer's bill
    concurrency: int = 5          # channels fetched in parallel


def _matches_terms(post: dict[str, Any], terms: tuple[str, ...]) -> bool:
    if not terms:
        return True
    haystack = (post.get("text") or "").lower()
    return any(term.lower() in haystack for term in terms)


async def scrape_channel(
    client: TelegramClient,
    handle: str,
    options: ScrapeOptions,
    on_posts: Callable[[list[dict[str, Any]]], Any] | None = None,
) -> tuple[list[dict[str, Any]], ChannelReport]:
    """Scrape one channel. Never returns an unexplained empty list."""
    first = await client.preview_page(handle)

    if not first.ok or not looks_like_preview(first.html or ""):
        plain = await client.plain_page(handle)
        state = classify(first.html, plain.html if plain.ok else None)
        if state is ChannelState.PUBLIC_PREVIEWABLE:
            state = ChannelState.UNREACHABLE
        failures = [f for f in (first.error, plain.error) if f]
        return [], build_report(
            handle=handle,
            state=state,
            post_ids=[],
            channel_info={},
            pages_fetched=0,
            page_failures=failures,
            requested_limit=options.max_posts or None,
            reached_end=False,
            stopped_by="preflight",
        )

    channel_info = parse_channel_info(first.html or "")
    collected: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    page_failures: list[str] = []
    pages = 0
    reached_end = False
    stopped_by: str | None = None
    result = first
    before: int | None = None

    while True:
        pages += 1
        posts, next_before = parse_page(result.html or "", handle)
        # Telegram renders oldest-first inside a page; emit newest-first.
        posts.sort(key=lambda p: p["postId"], reverse=True)

        page_batch: list[dict[str, Any]] = []
        too_old = False
        for post in posts:
            if post["postId"] in seen_ids:
                continue
            seen_ids.add(post["postId"])

            when = parse_iso(post.get("datetime"))
            if options.min_date and when and when < options.min_date:
                too_old = True
                continue
            if options.max_date and when and when > options.max_date:
                continue
            if not _matches_terms(post, options.search_terms):
                continue
            drop = set()
            if not options.include_media:
                drop.add("media")
            if not options.include_html:
                drop.add("textHtml")
            if drop:
                post = {k: v for k, v in post.items() if k not in drop}
            page_batch.append(post)

        if options.max_posts:
            room = options.max_posts - len(collected)
            if room <= 0:
                page_batch = []
            else:
                page_batch = page_batch[:room]

        collected.extend(page_batch)
        if on_posts and page_batch:
            await on_posts(page_batch)

        if options.max_posts and len(collected) >= options.max_posts:
            stopped_by = "maxPosts"
            break
        if too_old:
            stopped_by = "minDate"
            break
        if next_before is None:
            reached_end = True
            stopped_by = "endOfHistory"
            break
        if pages >= options.max_pages:
            stopped_by = "maxPages"
            break

        before = next_before
        result = await client.preview_page(handle, before=before)
        if not result.ok:
            page_failures.append(f"before={before}: {result.error or 'empty body'}")
            stopped_by = "pageFailure"
            break

    report = build_report(
        handle=handle,
        state=ChannelState.PUBLIC_PREVIEWABLE,
        post_ids=sorted(seen_ids),
        channel_info=channel_info,
        pages_fetched=pages,
        page_failures=page_failures,
        requested_limit=options.max_posts or None,
        reached_end=reached_end,
        stopped_by=stopped_by,
        emitted=len(collected),
    )
    return collected, report


async def scrape_channels(
    client: TelegramClient,
    handles: list[str],
    options: ScrapeOptions,
    on_posts: Callable[[list[dict[str, Any]]], Any] | None = None,
    on_report: Callable[[str, ChannelReport], Any] | None = None,
) -> list[tuple[list[dict[str, Any]], ChannelReport]]:
    """Scrape several channels with bounded concurrency.

    Telegram round-trips dominate the wall clock, so serial channels burn the
    customer's compute minutes on waiting. Results keep the input order.
    """
    semaphore = asyncio.Semaphore(max(1, options.concurrency))

    async def one(handle: str) -> tuple[list[dict[str, Any]], ChannelReport]:
        async with semaphore:
            posts, report = await scrape_channel(client, handle, options, on_posts)
            if on_report is not None:
                await on_report(handle, report)
            return posts, report

    return list(await asyncio.gather(*(one(h) for h in handles)))
