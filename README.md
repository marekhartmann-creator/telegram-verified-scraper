# Telegram Channel Scraper — verified results or an explicit error

Scrape **public Telegram channels** without an API key, a bot token or a phone
number: posts, views, reactions, media URLs, forwards, hashtags and mentions,
with date and keyword filtering.

The difference from every other Telegram scraper on this Store is one rule:

> **An empty result is never used to report a problem, and a run that returns
> nothing costs you nothing.**

## Why that matters

Telegram answers `HTTP 200` for channel handles that do not exist. The response
is a normal-looking page with no channel content in it. A scraper that only
counts posts on that page sees zero, calls the run a success, and bills you for
it. One typo in a channel name and you get a clean, empty, paid-for dataset.

The same silent failure happens when a channel exists but its web preview is not
served, when Telegram restricts the channel, when the handle is a group or a user
profile instead of a channel, and when a page fails halfway through pagination.

This Actor classifies the channel **before** it trusts any post count:

| State | What it means | What you get |
|---|---|---|
| `PUBLIC_PREVIEWABLE` | Real channel, readable | Posts |
| `EXISTS_NO_PREVIEW` | Real channel, Telegram serves no web preview | Explicit error |
| `PRIVATE` | Invite-only | Explicit error |
| `RESTRICTED` | Telegram serves no public page for the handle | Explicit error |
| `NOT_A_CHANNEL` | Handle is a user, bot or group | Explicit error |
| `NOT_FOUND` | Nothing at this handle (usually a typo) | Explicit error |
| `UNREACHABLE` | Telegram could not be reached | Explicit error |

Every one of those states except `PRIVATE` is checked against live Telegram by
`scripts/smoke.py`, which fails the build when a handle stops classifying the way
it did when the signature was captured.

On top of that, every channel gets a verification report:

* `verdict` — `OK`, `EMPTY_VERIFIED`, `PARTIAL` or `FAILED`
* `firstPostId` / `lastPostId` / `idGaps` / `coverageRatio` — how complete the
  history actually is (post ids are **not** contiguous; deleted and service
  messages leave holes, and a scraper that paginates by arithmetic walks past
  real posts)
* `reachedEndOfHistory`, `stoppedBy`, `pageFailures`

`EMPTY_VERIFIED` is only ever emitted when the channel header rendered, the
history container rendered, and the channel's own metadata does not contradict
the empty result.

## What this Actor deliberately does NOT do

**No members, no user profiles, no phone numbers, no personal data of any kind.**
Channel member lists are personal data under GDPR and their extraction conflicts
with Telegram's Terms of Service. This Actor reads public broadcast content only.
If you need member lists, this is the wrong tool — on purpose.

## Input

```json
{
  "channels": ["durov", "https://t.me/telegram"],
  "maxPostsPerChannel": 100,
  "minDate": "2026-01-01",
  "searchTerms": ["release", "update"],
  "includeMediaUrls": true,
  "maxConcurrency": 5,
  "failOnUnreadableChannel": true
}
```

Channels are fetched in parallel (`maxConcurrency`, 1-10). Telegram round-trips
dominate the wall clock, and compute time is billed, so waiting serially would be
your money spent on latency.

`failOnUnreadableChannel` (default **on**) ends the run as `FAILED` with a reason
when any requested channel could not be fully read. Turn it off to accept partial
results — the reports still tell you exactly what was missed.

## Output

One dataset item per post:

```json
{
  "channel": "durov",
  "postId": 385,
  "url": "https://t.me/durov/385",
  "datetime": "2026-08-01T10:00:00+00:00",
  "text": "…",
  "views": 1200000,
  "author": null,
  "isForwarded": false,
  "forwardedFrom": null,
  "isReply": false,
  "isEdited": false,
  "hashtags": ["telegram"],
  "mentions": [],
  "links": ["https://example.com"],
  "media": [{ "type": "photo", "url": "https://cdn.telegram.org/…" }],
  "linkPreview": { "title": "…", "url": "…" },
  "reactions": [{ "emoji": "👍", "count": 12 }],
  "reactionsTotal": 15
}
```

Plus one `channelReport` item per channel and one `runSummary` item per run
(also stored in the key-value store as `RUN_SUMMARY`).

## Pricing

Pay per event:

* **Actor start — $0** (deliberately: an empty run must not cost you anything)
* **$0.002 per verified post** written to the dataset

Posts that fail verification are never written, and therefore never charged.

## Use cases

News and OSINT monitoring, brand and competitor tracking, crypto signal channel
archiving, market and disinformation research, dataset building.
