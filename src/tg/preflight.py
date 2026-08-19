"""Decide what a handle actually is, BEFORE trusting any post count.

Telegram answers HTTP 200 for every handle, existing or not, and the differences
between "no such handle", "real channel we may not show you" and "this is a
group" live in one sentence of boilerplate. Getting that sentence wrong is how a
scraper ends up telling a customer to check the spelling of a channel with
400 000 subscribers.

Signatures captured from live t.me pages on 2026-08-19:

    handle that does not exist
        desc "If you have Telegram, you can contact @X right away."
        action "Send Message", no title, no counters, stock og:image
    real channel, web preview withheld (e.g. rt_russian)
        desc "If you have Telegram, you can view posts by @X right away."
        action "View in Telegram", no title, no counters, stock og:image
    real channel, no preview but page intact (e.g. zerohedge)
        title + "14 909 subscribers"
    group (e.g. durovschat)
        "9 767 members, 1 295 online"
    handle Telegram refuses to serve at all (e.g. mdk)
        no .tgme_page block; og:title is the generic "Telegram - a new era..."
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from .errors import ChannelState

# The /s/ preview page always carries the channel sidebar + history container.
_PREVIEW_MARKERS = (".tgme_channel_info", ".tgme_channel_history")

_VIEW_POSTS_RE = re.compile(r"view posts by", re.I)
_CONTACT_RE = re.compile(r"you can\s*(contact|send)", re.I)
_JOIN_RE = re.compile(r"(view and join|join (this )?(channel|group)|invite link)", re.I)
_RESTRICTED_RE = re.compile(
    r"(can'?t be displayed|is restricted|was used to spread|violat\w+)", re.I
)
_SUBSCRIBER_RE = re.compile(r"\bsubscriber", re.I)
_MEMBER_RE = re.compile(r"\bmembers?\b", re.I)
_GENERIC_SITE_TITLE_RE = re.compile(r"a new era of messaging", re.I)


def _text(tree: HTMLParser, selector: str) -> str:
    node = tree.css_first(selector)
    return node.text(separator=" ", strip=True) if node else ""


def _meta(tree: HTMLParser, prop: str) -> str:
    node = tree.css_first(f'meta[property="{prop}"]')
    return (node.attributes.get("content") or "") if node else ""


def looks_like_preview(html: str) -> bool:
    """True when the /s/ page really rendered a channel preview."""
    tree = HTMLParser(html)
    return all(tree.css_first(sel) is not None for sel in _PREVIEW_MARKERS)


def classify(preview_html: str | None, plain_html: str | None) -> ChannelState:
    """Classify a handle from the /s/ page and the plain t.me page.

    `preview_html` is https://t.me/s/<handle>, `plain_html` is https://t.me/<handle>.
    Either may be None when that request failed.
    """
    if preview_html and looks_like_preview(preview_html):
        return ChannelState.PUBLIC_PREVIEWABLE

    if plain_html is None:
        return ChannelState.UNREACHABLE

    tree = HTMLParser(plain_html)

    # Telegram served its marketing page instead of a handle page: the handle is
    # blocked or reserved. Not "missing" - we simply are not allowed to see it.
    if tree.css_first(".tgme_page") is None:
        if _GENERIC_SITE_TITLE_RE.search(_meta(tree, "og:title")):
            return ChannelState.RESTRICTED
        return ChannelState.UNREACHABLE

    title = _text(tree, ".tgme_page_title")
    extra = _text(tree, ".tgme_page_extra")
    description = _text(tree, ".tgme_page_description")
    action = _text(tree, ".tgme_page_action")
    og_description = _meta(tree, "og:description")
    blob = f"{description} {action} {og_description}"

    if _RESTRICTED_RE.search(blob):
        return ChannelState.RESTRICTED

    # Counters are the strongest positive evidence and outrank any boilerplate.
    if _SUBSCRIBER_RE.search(extra):
        return ChannelState.EXISTS_NO_PREVIEW
    if _MEMBER_RE.search(extra):
        return ChannelState.NOT_A_CHANNEL

    # "view posts by @X" - a real channel whose preview Telegram withholds.
    if _VIEW_POSTS_RE.search(blob):
        return ChannelState.EXISTS_NO_PREVIEW

    if _JOIN_RE.search(blob):
        return ChannelState.PRIVATE

    # "contact @X" / "Send Message" - a person-shaped handle. With a title it is
    # a real account; without one, nothing lives here.
    if _CONTACT_RE.search(blob):
        return ChannelState.NOT_A_CHANNEL if title else ChannelState.NOT_FOUND

    if title:
        return ChannelState.NOT_A_CHANNEL

    return ChannelState.UNREACHABLE
