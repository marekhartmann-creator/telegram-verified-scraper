from conftest import fixture

from tg.parse import parse_channel_info, parse_human_count, parse_page


def test_parse_human_count():
    assert parse_human_count("1.2K") == 1200
    assert parse_human_count("147K subscribers") == 147000
    assert parse_human_count("2 404") == 2404
    assert parse_human_count("") is None
    assert parse_human_count(None) is None


def test_channel_info():
    info = parse_channel_info(fixture("channel_page.html"))
    assert info["title"] == "Test Channel"
    assert info["subscribersCount"] == 147000
    assert info["photosCount"] == 1204


def test_posts_are_parsed():
    posts, before = parse_page(fixture("channel_page.html"), "testchannel")
    assert [p["postId"] for p in posts] == [80, 85, 99]
    assert before == 80

    first = posts[0]
    assert first["channel"] == "testchannel"
    assert first["url"] == "https://t.me/testchannel/80"
    assert first["views"] == 1200
    assert first["datetime"].startswith("2026-08-01")
    assert first["hashtags"] == ["alpha"]
    assert first["mentions"] == ["somebody"]

    second = posts[1]
    assert second["isForwarded"] is True
    assert second["forwardedFrom"] == "Other Source"
    assert second["media"] == [{"type": "photo", "url": "https://cdn/photo85.jpg"}]
    assert second["reactionsTotal"] == 15
    assert second["reactions"] == [
        {"emoji": "paid-star", "count": 1, "isPaid": True},
        {"emoji": "\U0001f601", "count": 12, "isPaid": False},
        {"emoji": "custom:5465587407350942612", "count": 2, "isPaid": False},
    ]

    assert posts[2]["isEdited"] is True


def test_ids_are_not_contiguous():
    """80, 85, 99 - a scraper that assumes min_id-page_size would skip real posts."""
    posts, _ = parse_page(fixture("channel_page.html"), "testchannel")
    ids = [p["postId"] for p in posts]
    assert max(ids) - min(ids) + 1 > len(ids)


def test_empty_history_yields_no_posts_and_no_cursor():
    posts, before = parse_page(fixture("empty_channel.html"), "brandnew")
    assert posts == []
    assert before is None


def test_reactions_with_abbreviated_counts():
    """Real markup from t.me/s/durov: counts like 55.2K sit next to custom emoji."""
    from selectolax.parser import HTMLParser

    from tg.parse import parse_post

    html = (
        '<div class="tgme_widget_message" data-post="c/1">'
        '<div class="tgme_widget_message_reactions js-message_reactions">'
        '<span class="tgme_reaction tgme_reaction_paid"><i class="icon"></i>7.03K</span>'
        '<span class="tgme_reaction"><tg-emoji emoji-id="546"></tg-emoji>55.2K</span>'
        "</div></div>"
    )
    post = parse_post(HTMLParser(html).css_first(".tgme_widget_message"), "c")
    assert post["reactionsTotal"] == 7030 + 55200
    assert post["reactions"][0]["isPaid"] is True
    assert post["reactions"][1]["emoji"] == "custom:546"


def test_reactions_absent_means_none_not_zero():
    """A channel with reactions switched off must not look like zero engagement."""
    from selectolax.parser import HTMLParser

    from tg.parse import parse_post

    html = '<div class="tgme_widget_message" data-post="c/2"></div>'
    post = parse_post(HTMLParser(html).css_first(".tgme_widget_message"), "c")
    assert post["reactions"] == []
    assert post["reactionsTotal"] is None
