import pytest
from conftest import fixture  # noqa: F401  (ensures src/ is on sys.path)

from tg.scraper import normalize_handle, parse_iso


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("durov", "durov"),
        ("@durov", "durov"),
        ("  DUROV  ", "DUROV"),
        ("t.me/durov", "durov"),
        ("https://t.me/durov", "durov"),
        ("http://www.t.me/s/durov?before=100", "durov"),
        ("https://telegram.me/durov/", "durov"),
        ("https://t.me/durov/1234", None),      # link to a single post, not a channel
        ("https://t.me/+AbCdEf", None),         # private invite
        ("t.me/joinchat/AAA", None),
        ("ab", None),                            # too short to be a handle
        ("", None),
        ("has spaces", None),
    ],
)
def test_normalize_handle(raw, expected):
    assert normalize_handle(raw) == expected


def test_parse_iso():
    assert parse_iso("2026-08-01").isoformat() == "2026-08-01T00:00:00+00:00"
    assert parse_iso("2026-08-01T10:00:00Z").isoformat() == "2026-08-01T10:00:00+00:00"
    assert parse_iso("nonsense") is None
    assert parse_iso(None) is None
