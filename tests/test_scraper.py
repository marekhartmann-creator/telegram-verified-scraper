"""End-to-end behaviour with a fake HTTP layer.

These are the tests that encode the product promise: an unreadable channel is
never reported as an empty one.
"""
import asyncio
import re

import pytest
from conftest import fixture

from tg.errors import ChannelState
from tg.fetch import FetchResult
from tg.scraper import ScrapeOptions, parse_iso, scrape_channel


class FakeClient:
    """Serves canned pages; records what was requested."""

    def __init__(self, pages: dict[object, FetchResult], plain: FetchResult | None = None):
        self.pages = pages
        self.plain = plain or FetchResult(url="plain", status=200, html=fixture("not_found.html"))
        self.requested: list[object] = []

    async def preview_page(self, handle, before=None):
        self.requested.append(before)
        return self.pages.get(before, FetchResult(url=str(before), status=404, error="HTTP 404"))

    async def plain_page(self, handle):
        return self.plain


def ok(html: str) -> FetchResult:
    return FetchResult(url="x", status=200, html=html)


def run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def last_page(html: str) -> str:
    """Same fixture without the 'load more' link -> end of history."""
    return re.sub(r'<a class="tme_messages_more.*?</a>', "", html, flags=re.S)


# --- the bug we exist to fix -------------------------------------------------

def test_unknown_handle_fails_loudly_instead_of_returning_empty():
    client = FakeClient({None: ok(fixture("not_found.html"))})
    posts, report = run(scrape_channel(client, "nonexistentchannel12345xyzqq", ScrapeOptions()))

    assert posts == []
    assert report.state is ChannelState.NOT_FOUND
    assert report.verdict == "FAILED"
    assert report.verified is False
    assert "does not" in report.message or "No channel exists" in report.message


def test_channel_without_web_preview_is_not_empty():
    client = FakeClient(
        {None: ok(fixture("not_found.html"))},
        plain=ok(fixture("no_preview.html")),
    )
    _, report = run(scrape_channel(client, "somechannel", ScrapeOptions()))
    assert report.state is ChannelState.EXISTS_NO_PREVIEW
    assert report.verdict == "FAILED"


def test_metadata_contradiction_is_a_load_failure():
    """Sidebar advertises 1204 photos, history returns nothing."""
    client = FakeClient({None: ok(fixture("contradiction.html"))})
    posts, report = run(scrape_channel(client, "busychannel", ScrapeOptions()))
    assert posts == []
    assert report.verdict == "FAILED"
    assert "1204" in report.message


def test_genuinely_empty_channel_is_verified_as_empty():
    client = FakeClient({None: ok(fixture("empty_channel.html"))})
    posts, report = run(scrape_channel(client, "brandnew", ScrapeOptions()))
    assert posts == []
    assert report.verdict == "EMPTY_VERIFIED"
    assert report.verified is True


def test_partial_history_is_reported_not_hidden():
    """First page works, the next one 404s -> PARTIAL, never a silent success."""
    client = FakeClient({None: ok(fixture("channel_page.html"))})  # before=80 missing
    posts, report = run(scrape_channel(client, "testchannel", ScrapeOptions()))
    assert len(posts) == 3
    assert report.verdict == "PARTIAL"
    assert report.verified is False
    assert report.pageFailures


# --- normal operation --------------------------------------------------------

def test_full_history_walk():
    page2 = last_page(fixture("channel_page.html")).replace("testchannel/8", "testchannel/6")
    client = FakeClient({None: ok(fixture("channel_page.html")), 80: ok(page2)})
    posts, report = run(scrape_channel(client, "testchannel", ScrapeOptions(max_posts=0)))

    assert report.verdict == "OK"
    assert report.verified is True
    assert report.reachedEndOfHistory is True
    assert report.stoppedBy == "endOfHistory"
    assert client.requested == [None, 80]
    assert [p["postId"] for p in posts][:3] == [99, 85, 80]
    assert report.idGaps > 0  # deleted / service messages leave holes


def test_max_posts_is_respected():
    client = FakeClient({None: ok(fixture("channel_page.html"))})
    posts, report = run(scrape_channel(client, "testchannel", ScrapeOptions(max_posts=2)))
    assert len(posts) == 2
    assert report.stoppedBy == "maxPosts"
    assert report.verdict == "OK"


def test_min_date_stops_pagination():
    options = ScrapeOptions(max_posts=0, min_date=parse_iso("2026-08-03"))
    client = FakeClient({None: ok(fixture("channel_page.html"))})
    posts, report = run(scrape_channel(client, "testchannel", options))
    assert [p["postId"] for p in posts] == [99]
    assert report.stoppedBy == "minDate"


def test_keyword_filter():
    options = ScrapeOptions(max_posts=0, search_terms=("photo",))
    page2 = last_page(fixture("channel_page.html")).replace("testchannel/8", "testchannel/6")
    client = FakeClient({None: ok(fixture("channel_page.html")), 80: ok(page2)})
    posts, _ = run(scrape_channel(client, "testchannel", options))
    assert all("photo" in (p["text"] or "").lower() for p in posts)
    assert posts


def test_media_can_be_excluded():
    options = ScrapeOptions(include_media=False)
    client = FakeClient({None: ok(fixture("channel_page.html"))})
    posts, _ = run(scrape_channel(client, "testchannel", options))
    assert all("media" not in p for p in posts)


def test_scrape_channels_runs_in_parallel_and_keeps_order():
    from tg.scraper import scrape_channels

    clients = FakeClient({None: ok(fixture("channel_page.html"))})
    handles = ["one", "two", "three"]
    seen: list[str] = []

    async def on_report(handle, report):
        seen.append(handle)

    results = run(
        scrape_channels(clients, handles, ScrapeOptions(max_posts=1), None, on_report)
    )
    assert [r.handle for _, r in results] == handles       # input order preserved
    assert sorted(seen) == sorted(handles)                 # every channel reported
    assert all(len(posts) == 1 for posts, _ in results)


def test_scrape_channels_isolates_a_broken_channel():
    """One bad handle must not take the good ones down with it."""
    from tg.scraper import scrape_channels

    class Mixed(FakeClient):
        async def preview_page(self, handle, before=None):
            if handle == "broken":
                return FetchResult(url="x", status=200, html=fixture("not_found.html"))
            return ok(fixture("channel_page.html"))

    results = run(
        scrape_channels(Mixed({}), ["good", "broken"], ScrapeOptions(max_posts=1))
    )
    verdicts = {r.handle: r.verdict for _, r in results}
    assert verdicts == {"good": "OK", "broken": "FAILED"}
