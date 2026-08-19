"""Explicit failure taxonomy.

The whole point of this Actor: an empty dataset is never an acceptable way to
report a problem. Every non-result gets a code from here.
"""
from __future__ import annotations

from enum import Enum


class ChannelState(str, Enum):
    """Result of the preflight classification."""

    PUBLIC_PREVIEWABLE = "PUBLIC_PREVIEWABLE"   # real channel, web preview works
    EXISTS_NO_PREVIEW = "EXISTS_NO_PREVIEW"     # real channel, preview disabled
    PRIVATE = "PRIVATE"                          # invite-only
    RESTRICTED = "RESTRICTED"                    # age/abuse restricted on web
    NOT_A_CHANNEL = "NOT_A_CHANNEL"              # user, bot or group
    NOT_FOUND = "NOT_FOUND"                      # nothing at this handle
    UNREACHABLE = "UNREACHABLE"                  # network/HTTP problem


#: States from which "zero posts" is a trustworthy answer.
TRUSTWORTHY_EMPTY = {ChannelState.PUBLIC_PREVIEWABLE}

#: Human explanation + hint, surfaced in the run summary and in the log.
STATE_MESSAGES: dict[ChannelState, str] = {
    ChannelState.PUBLIC_PREVIEWABLE: "Public channel with a working web preview.",
    ChannelState.EXISTS_NO_PREVIEW: (
        "The channel exists but Telegram withholds its web preview, so its posts "
        "cannot be read anonymously. This is NOT an empty channel and NOT a typo."
    ),
    ChannelState.PRIVATE: "Private / invite-only channel. Public data is not available.",
    ChannelState.RESTRICTED: (
        "Telegram serves no public page for this handle (age restriction, abuse "
        "block or a reserved name). Posts cannot be read anonymously."
    ),
    ChannelState.NOT_A_CHANNEL: (
        "This handle is a user, bot or group, not a broadcast channel."
    ),
    ChannelState.NOT_FOUND: (
        "No channel exists at this handle. Telegram answers HTTP 200 with a generic "
        "page for unknown handles, which is why naive scrapers report this as "
        "'channel has no posts'. Check the spelling."
    ),
    ChannelState.UNREACHABLE: "Telegram could not be reached for this handle.",
}


class ChannelFailure(Exception):
    """Raised when a channel cannot be read and must not be reported as empty."""

    def __init__(self, handle: str, state: ChannelState, detail: str = "") -> None:
        self.handle = handle
        self.state = state
        self.detail = detail
        message = f"[{state.value}] {handle}: {STATE_MESSAGES[state]}"
        if detail:
            message = f"{message} ({detail})"
        super().__init__(message)
