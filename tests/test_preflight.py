from conftest import fixture

from tg.errors import ChannelState
from tg.preflight import classify, looks_like_preview


def test_real_preview_is_recognised():
    assert looks_like_preview(fixture("channel_page.html")) is True
    assert looks_like_preview(fixture("not_found.html")) is False


def test_unknown_handle_is_not_an_empty_channel():
    """The core bug this Actor exists to fix.

    Telegram returns HTTP 200 with a generic page for handles that do not exist.
    """
    state = classify(fixture("not_found.html"), fixture("not_found.html"))
    assert state is ChannelState.NOT_FOUND


def test_channel_without_web_preview():
    state = classify(fixture("not_found.html"), fixture("no_preview.html"))
    assert state is ChannelState.EXISTS_NO_PREVIEW


def test_private_and_restricted():
    assert classify(None, fixture("private.html")) is ChannelState.PRIVATE
    assert classify(None, fixture("restricted.html")) is ChannelState.RESTRICTED


def test_user_profile_is_not_a_channel():
    assert classify(None, fixture("user.html")) is ChannelState.NOT_A_CHANNEL


def test_public_preview_wins():
    assert (
        classify(fixture("channel_page.html"), fixture("no_preview.html"))
        is ChannelState.PUBLIC_PREVIEWABLE
    )


def test_no_html_at_all_is_unreachable():
    assert classify(None, None) is ChannelState.UNREACHABLE


def test_real_channel_with_withheld_preview_is_not_a_typo():
    """rt_russian: 'you can view posts by @X' -> the channel exists.

    Reporting NOT_FOUND here would tell a customer to check the spelling of a
    channel with hundreds of thousands of subscribers. This is the exact failure
    the Actor promises not to make.
    """
    state = classify(None, fixture("no_preview_boilerplate.html"))
    assert state is ChannelState.EXISTS_NO_PREVIEW


def test_contact_boilerplate_without_a_title_is_not_found():
    assert classify(None, fixture("not_found.html")) is ChannelState.NOT_FOUND


def test_handle_with_no_page_at_all_is_restricted_not_missing():
    """mdk: Telegram answers with its marketing page and no handle page."""
    assert classify(None, fixture("no_page_at_all.html")) is ChannelState.RESTRICTED


def test_group_is_not_a_channel():
    assert classify(None, fixture("group.html")) is ChannelState.NOT_A_CHANNEL


def test_subscriber_counter_outranks_join_boilerplate():
    """zerohedge says 'view and join' but has a subscriber count -> a channel."""
    assert classify(None, fixture("no_preview.html")) is ChannelState.EXISTS_NO_PREVIEW
