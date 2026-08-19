"""Živý smoke test - spusti MIMO Apify, na stroji so sieťou:

    python3 scripts/smoke.py

Overuje, že selektory a klasifikátor sedia proti reálnemu Telegramu.
Nič nezapisuje, len vypíše verdikt pre každý kanál.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Windows consoles default to cp1250/cp1252 and would crash on emoji.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg.fetch import TelegramClient  # noqa: E402
from tg.scraper import ScrapeOptions, scrape_channel  # noqa: E402

# Handles below were classified against live Telegram on 2026-08-19.
# expected state -> what the classifier must say, or the promise is broken.
CASES = [
    ("durov", "PUBLIC_PREVIEWABLE", "veľký verejný kanál"),
    ("telegram", "PUBLIC_PREVIEWABLE", "oficiálny kanál, reakcie vypnuté"),
    ("georgenews", "PUBLIC_PREVIEWABLE", "kanál zo sťažnosti na incumbenta"),
    ("nonexistentchannel12345xyzqq", "NOT_FOUND", "PREKLEP"),
    ("rt_russian", "EXISTS_NO_PREVIEW", "reálny kanál, Telegram nedá preview"),
    ("zerohedge", "EXISTS_NO_PREVIEW", "reálny kanál s počtom odberateľov, bez preview"),
    ("durovschat", "NOT_A_CHANNEL", "skupina, nie kanál"),
    ("mdk", "RESTRICTED", "handle, ku ktorému Telegram nedá stránku"),
]


async def main() -> None:
    options = ScrapeOptions(max_posts=25)
    failures = 0
    async with TelegramClient() as client:
        for handle, expected, note in CASES:
            posts, report = await scrape_channel(client, handle, options)
            actual = report.state.value
            mark = "OK " if actual == expected else "!! "
            if actual != expected:
                failures += 1
            print(f"\n{mark}=== {handle}  ({note})")
            print(f"    ocakavane={expected} skutocne={actual} verdict={report.verdict} "
                  f"posts={len(posts)} gaps={report.idGaps} coverage={report.coverageRatio}")
            print(f"    {report.message}")
            if posts:
                p = posts[0]
                print(f"    najnovsi: id={p['postId']} date={p['datetime']} "
                      f"views={p['views']} reakcie={p['reactionsTotal']} "
                      f"media={len(p.get('media') or [])}")
                print(f"    text: {(p['text'] or '')[:80]!r}")

    print(f"\n=== {len(CASES) - failures}/{len(CASES)} zhoda so ocakavanim")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
