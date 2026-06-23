"""Backfill of known historical resets via fxtwitter (free, no auth).

Nitter discovers *recent* posts but can't reach back months. fxtwitter can read
a *specific* tweet by URL (clean JSON, no auth), so a short curated list of
verified historical reset tweets gives the ledger real, dated history before
the live poller has accumulated its own. Real data - every entry is a real,
linkable tweet.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

import httpx

from ..config import Config
from ..models import CandidatePost
from .base import tweet_url

log = logging.getLogger("resetradar.sources.fxtwitter")

_URL = re.compile(r"(?:x|twitter)\.com/([^/]+)/status/(\d+)", re.IGNORECASE)


def _fetch_tweet(client: httpx.Client, handle: str, tweet_id: str) -> dict | None:
    """Read one tweet's JSON, retrying through fxtwitter's rate limits."""
    for attempt in range(3):
        try:
            resp = client.get(f"https://api.fxtwitter.com/{handle}/status/{tweet_id}")
            if resp.status_code == 200:
                return resp.json().get("tweet")
            if resp.status_code not in (429, 500, 502, 503):
                return None
        except Exception as exc:  # noqa: BLE001
            log.info("fxtwitter attempt %d failed for %s: %s", attempt, tweet_id, exc)
        time.sleep(0.8 * (attempt + 1))
    return None


class FxTwitterSource:
    name = "fxtwitter"

    def __init__(self, cfg: Config, known_ids: set[str] | None = None) -> None:
        self.tweets = cfg.backfill_tweets
        self.known_ids = known_ids or set()  # tweet IDs already in the ledger - skip

    def fetch(self) -> list[CandidatePost]:
        posts: list[CandidatePost] = []
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ResetRadar/0.1)"}
        with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
            for url in self.tweets:
                m = _URL.search(url)
                if not m:
                    continue
                handle, tweet_id = m.group(1), m.group(2)
                if tweet_id in self.known_ids:
                    continue  # already recorded - don't re-fetch every run
                tweet = _fetch_tweet(client, handle, tweet_id)
                if not tweet:
                    log.info("fxtwitter could not read %s", tweet_id)
                    continue
                ts = tweet.get("created_timestamp")
                posts.append(
                    CandidatePost(
                        source=self.name,
                        url=tweet_url(handle, tweet_id),
                        text=tweet.get("text", ""),
                        account=handle,
                        posted_at=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None,
                        external_id=tweet_id,
                    )
                )
        return posts
