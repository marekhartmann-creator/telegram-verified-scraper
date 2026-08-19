"""Turn t.me/s/<channel> HTML into structured posts.

Deliberately defensive: every field is optional, a missing field is reported as
None rather than crashing the run or silently dropping the post.
"""
from __future__ import annotations

import re
from typing import Any

from selectolax.parser import HTMLParser, Node

_BG_URL_RE = re.compile(r"background-image\s*:\s*url\(['\"]?(.*?)['\"]?\)", re.I)
_COUNT_RE = re.compile(r"([\d.,]+)\s*([KMB]?)", re.I)
_HASHTAG_RE = re.compile(r"(?<!\w)#(\w{2,64})")
_MENTION_RE = re.compile(r"(?<!\w)@(\w{4,32})")
_MULTIPLIER = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def parse_human_count(raw: str | None) -> int | None:
    """'1.2K' -> 1200, '147K subscribers' -> 147000, '' -> None."""
    if not raw:
        return None
    cleaned = re.sub(r"[\s\u00a0\u202f\u2009]", "", raw)
    match = _COUNT_RE.search(cleaned)
    if not match:
        return None
    number, suffix = match.groups()
    number = number.replace(",", "").replace(" ", "")
    try:
        value = float(number)
    except ValueError:
        return None
    return int(value * _MULTIPLIER[suffix.upper()])


def _attr(node: Node | None, name: str) -> str | None:
    if node is None:
        return None
    value = node.attributes.get(name)
    return value.strip() if value else None


def _text(node: Node | None) -> str | None:
    if node is None:
        return None
    text = node.text(separator="\n", strip=True)
    return text or None


def _bg_url(node: Node | None) -> str | None:
    style = _attr(node, "style")
    if not style:
        return None
    match = _BG_URL_RE.search(style)
    return match.group(1) if match else None


def parse_channel_info(html: str) -> dict[str, Any]:
    """Channel sidebar of the /s/ page."""
    tree = HTMLParser(html)
    info: dict[str, Any] = {
        "title": _text(tree.css_first(".tgme_channel_info_header_title")),
        "username": _text(tree.css_first(".tgme_channel_info_header_username")),
        "description": _text(tree.css_first(".tgme_channel_info_description")),
        "avatarUrl": _attr(tree.css_first(".tgme_page_photo_image img"), "src")
        or _attr(tree.css_first(".tgme_channel_info_header_photo img"), "src"),
    }
    for counter in tree.css(".tgme_channel_info_counter"):
        kind = _text(counter.css_first(".counter_type"))
        value = parse_human_count(_text(counter.css_first(".counter_value")))
        if kind:
            info[f"{kind.strip().lower()}Count"] = value
    return info


def _parse_reactions(message: Node) -> tuple[list[dict[str, Any]], int | None]:
    """Reactions as Telegram really renders them on t.me/s/ pages.

    Three shapes live inside `.tgme_widget_message_reactions`:
        <span class="tgme_reaction"><i class="emoji"><b>EMOJI</b></i>171</span>
        <span class="tgme_reaction"><tg-emoji emoji-id="123"></tg-emoji>55.2K</span>
        <span class="tgme_reaction tgme_reaction_paid"><i class="icon ..."></i>7.03K</span>
    The count is the bare text node after the emoji, so it is recovered by
    subtracting the emoji text from the span text rather than by a selector.
    """
    reactions: list[dict[str, Any]] = []
    container = message.css_first(".tgme_widget_message_reactions")
    if container is None:
        return reactions, None

    total = 0
    for item in container.css(".tgme_reaction"):
        raw = item.text(strip=True) or ""
        emoji_node = item.css_first("b")
        custom_node = item.css_first("tg-emoji")
        is_paid = "tgme_reaction_paid" in (item.attributes.get("class") or "")

        emoji: str | None = None
        if emoji_node is not None:
            emoji = emoji_node.text(strip=True) or None
        elif custom_node is not None:
            emoji_id = custom_node.attributes.get("emoji-id")
            emoji = f"custom:{emoji_id}" if emoji_id else "custom"
        elif is_paid:
            emoji = "paid-star"

        count_text = raw
        if emoji_node is not None:
            count_text = raw.replace(emoji_node.text(strip=True) or "", "", 1)
        count = parse_human_count(count_text) or 0

        reactions.append({"emoji": emoji, "count": count, "isPaid": is_paid})
        total += count

    return reactions, total


def _parse_media(message: Node) -> list[dict[str, Any]]:
    media: list[dict[str, Any]] = []
    for photo in message.css(".tgme_widget_message_photo_wrap"):
        media.append({"type": "photo", "url": _bg_url(photo)})
    for video in message.css("video.tgme_widget_message_video"):
        media.append({"type": "video", "url": _attr(video, "src")})
    for wrap in message.css(".tgme_widget_message_video_player"):
        thumb = _bg_url(wrap.css_first(".tgme_widget_message_video_thumb"))
        duration = _text(wrap.css_first(".message_video_duration"))
        if thumb or duration:
            media.append({"type": "videoThumb", "url": thumb, "duration": duration})
    for voice in message.css("audio.tgme_widget_message_voice"):
        media.append({"type": "voice", "url": _attr(voice, "src")})
    for doc in message.css(".tgme_widget_message_document"):
        media.append(
            {
                "type": "document",
                "url": None,
                "title": _text(doc.css_first(".tgme_widget_message_document_title")),
                "size": _text(doc.css_first(".tgme_widget_message_document_extra")),
            }
        )
    for sticker in message.css(".tgme_widget_message_sticker"):
        media.append({"type": "sticker", "url": _attr(sticker, "data-webp")})
    return [m for m in media if any(v for k, v in m.items() if k != "type")]


def _parse_link_preview(message: Node) -> dict[str, Any] | None:
    node = message.css_first(".tgme_widget_message_link_preview")
    if node is None:
        return None
    return {
        "url": _attr(node, "href"),
        "siteName": _text(node.css_first(".link_preview_site_name")),
        "title": _text(node.css_first(".link_preview_title")),
        "description": _text(node.css_first(".link_preview_description")),
        "imageUrl": _bg_url(node.css_first(".link_preview_image")),
    }


def parse_post(message: Node, channel: str) -> dict[str, Any] | None:
    """One `.tgme_widget_message` node -> dict. None when it carries no post id."""
    data_post = _attr(message, "data-post")
    if not data_post or "/" not in data_post:
        return None
    channel_part, _, id_part = data_post.rpartition("/")
    try:
        post_id = int(id_part)
    except ValueError:
        return None

    text_node = message.css_first(".tgme_widget_message_text")
    text = _text(text_node)
    reactions, reactions_total = _parse_reactions(message)
    time_node = message.css_first(".tgme_widget_message_date time")
    edit_node = message.css_first(".tgme_widget_message_meta .tgme_widget_message_edited")
    forward_node = message.css_first(".tgme_widget_message_forwarded_from_name")
    reply_node = message.css_first(".tgme_widget_message_reply")
    unsupported = message.css_first(".message_media_not_supported_wrap") is not None

    return {
        "channel": channel_part or channel,
        "postId": post_id,
        "url": f"https://t.me/{data_post}",
        "datetime": _attr(time_node, "datetime"),
        "text": text,
        "textHtml": text_node.html if text_node is not None else None,
        "views": parse_human_count(_text(message.css_first(".tgme_widget_message_views"))),
        "author": _text(message.css_first(".tgme_widget_message_from_author")),
        "isForwarded": forward_node is not None,
        "forwardedFrom": _text(forward_node),
        "forwardedFromUrl": _attr(forward_node, "href"),
        "isReply": reply_node is not None,
        "replyToUrl": _attr(reply_node, "href"),
        "isEdited": edit_node is not None,
        "hashtags": sorted(set(_HASHTAG_RE.findall(text or ""))),
        "mentions": sorted(set(_MENTION_RE.findall(text or ""))),
        "links": [
            href
            for href in (
                _attr(a, "href") for a in (text_node.css("a") if text_node else [])
            )
            if href and href.startswith("http")
        ],
        "media": _parse_media(message),
        "linkPreview": _parse_link_preview(message),
        "reactions": reactions,
        "reactionsTotal": reactions_total,
        "hasUnsupportedMedia": unsupported,
    }


def parse_page(html: str, channel: str) -> tuple[list[dict[str, Any]], int | None]:
    """All posts on one preview page + the `before` cursor for the next page.

    The cursor comes from Telegram's own "load more" link, never from arithmetic
    on post ids: ids are NOT contiguous (deleted and service messages leave gaps),
    so `min_id - page_size` walks straight past real posts.
    """
    tree = HTMLParser(html)
    posts: list[dict[str, Any]] = []
    for message in tree.css(".tgme_widget_message"):
        post = parse_post(message, channel)
        if post is not None:
            posts.append(post)

    next_before: int | None = None
    for link in tree.css("a.tme_messages_more"):
        if _attr(link, "data-before") is not None:
            raw = _attr(link, "data-before")
            try:
                next_before = int(raw) if raw else None
            except ValueError:
                next_before = None
            break

    return posts, next_before
