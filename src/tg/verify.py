"""The part that makes this Actor different.

Rule: a zero-post result is only ever emitted when we hold positive evidence
that the channel really is empty. Anything else fails with a code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import STATE_MESSAGES, TRUSTWORTHY_EMPTY, ChannelState


@dataclass
class ChannelReport:
    handle: str
    state: ChannelState
    postsCollected: int = 0
    postsSeen: int = 0
    requestedLimit: int | None = None
    firstPostId: int | None = None
    lastPostId: int | None = None
    idGaps: int = 0
    coverageRatio: float | None = None
    reachedEndOfHistory: bool = False
    stoppedBy: str | None = None
    pagesFetched: int = 0
    pageFailures: list[str] = field(default_factory=list)
    channelInfo: dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    verdict: str = ""
    message: str = ""

    def to_item(self) -> dict[str, Any]:
        item = {k: v for k, v in self.__dict__.items()}
        item["state"] = self.state.value
        item["_type"] = "channelReport"
        return item


def _id_stats(post_ids: list[int]) -> tuple[int | None, int | None, int, float | None]:
    if not post_ids:
        return None, None, 0, None
    lo, hi = min(post_ids), max(post_ids)
    span = hi - lo + 1
    gaps = span - len(set(post_ids))
    coverage = round(len(set(post_ids)) / span, 4) if span else None
    return lo, hi, gaps, coverage


def build_report(
    *,
    handle: str,
    state: ChannelState,
    post_ids: list[int],
    channel_info: dict[str, Any],
    pages_fetched: int,
    page_failures: list[str],
    requested_limit: int | None,
    reached_end: bool,
    stopped_by: str | None,
    emitted: int | None = None,
) -> ChannelReport:
    lo, hi, gaps, coverage = _id_stats(post_ids)
    report = ChannelReport(
        handle=handle,
        state=state,
        postsCollected=len(post_ids) if emitted is None else emitted,
        postsSeen=len(post_ids),
        requestedLimit=requested_limit,
        firstPostId=lo,
        lastPostId=hi,
        idGaps=gaps,
        coverageRatio=coverage,
        reachedEndOfHistory=reached_end,
        stoppedBy=stopped_by,
        pagesFetched=pages_fetched,
        pageFailures=page_failures,
        channelInfo=channel_info,
    )

    # 1. The channel could not be read at all.
    if state not in TRUSTWORTHY_EMPTY:
        report.verified = False
        report.verdict = "FAILED"
        report.message = STATE_MESSAGES[state]
        return report

    # 2. Preview rendered but not a single page came back.
    if pages_fetched == 0:
        report.verified = False
        report.verdict = "FAILED"
        report.message = (
            "The channel preview was classified as readable but no page could be "
            "fetched. Refusing to report this as an empty channel."
        )
        return report

    # 3. Cross-check: the sidebar advertises content, we collected none.
    advertised = sum(
        value
        for key, value in channel_info.items()
        if key.endswith("Count")
        and key != "subscribersCount"
        and isinstance(value, int)
    )
    if not post_ids and advertised > 0:
        report.verified = False
        report.verdict = "FAILED"
        report.message = (
            f"Channel metadata advertises {advertised} media items but the history "
            "returned zero posts. This is a load failure, not an empty channel."
        )
        return report

    # 4. Some pages failed while others worked -> partial, say so out loud.
    if page_failures:
        report.verified = False
        report.verdict = "PARTIAL"
        report.message = (
            f"Collected {report.postsCollected} posts but {len(page_failures)} page request(s) "
            "failed, so the history has holes. See pageFailures."
        )
        return report

    # 5. Genuinely empty, and we can prove it.
    if not post_ids:
        report.verified = True
        report.verdict = "EMPTY_VERIFIED"
        report.message = (
            "Channel is readable and really has no posts in the requested range. "
            "Verified against the rendered channel header."
        )
        return report

    report.verified = True
    report.verdict = "OK"
    report.message = (
        f"Collected {report.postsCollected} posts (ids {lo}-{hi}, {gaps} id gaps from "
        "deleted or service messages)."
    )
    return report
