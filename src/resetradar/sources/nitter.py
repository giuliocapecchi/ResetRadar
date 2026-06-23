"""Free X-timeline discovery via Nitter RSS (no auth, no cost).

Nitter mirrors an account's public timeline as an RSS feed, which gives us the
one thing the read-only mirrors (fxtwitter/oEmbed) can't: discovery of an
account's *recent* posts. Instances are flaky, so we try a list until one
returns items. Posts carry the official handle, so the detector treats them as
authoritative. Best-effort: if every instance is down, the run continues on the
other sources.
"""

from __future__ import annotations

import logging
import re
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree as ET

import httpx

from ..config import Config
from ..models import CandidatePost
from .base import tweet_url

log = logging.getLogger("resetradar.sources.nitter")

_TAG = re.compile(r"<[^>]+>")
_ID = re.compile(r"/status/(\d+)")


class NitterSource:
    name = "nitter"

    def __init__(self, cfg: Config) -> None:
        self.handles = cfg.x_handles
        self.instances = cfg.nitter_instances

    def fetch(self) -> list[CandidatePost]:
        posts: list[CandidatePost] = []
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Firefox/128.0",
                   "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"}
        with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
            for handle in self.handles:
                posts.extend(self._fetch_handle(client, handle))
        return posts

    def _fetch_handle(self, client: httpx.Client, handle: str) -> list[CandidatePost]:
        for inst in self.instances:
            try:
                resp = client.get(f"https://{inst}/{handle}/rss")
            except Exception as exc:  # noqa: BLE001 - try the next instance
                log.info("nitter %s failed for @%s: %s", inst, handle, exc)
                continue
            if resp.status_code == 200 and "<item>" in resp.text:
                parsed = self._parse(resp.text, handle)
                if parsed:
                    return parsed
        log.info("no working nitter instance for @%s", handle)
        return []

    def _parse(self, xml: str, handle: str) -> list[CandidatePost]:
        out: list[CandidatePost] = []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            log.info("nitter RSS parse error for @%s: %s", handle, exc)
            return out
        for item in root.iter("item"):
            # <title> is the clean single-tweet text; <description> can bleed
            # adjacent/quoted tweets, so prefer the title.
            raw = (item.findtext("title") or item.findtext("description") or "")
            text = unescape(_TAG.sub(" ", raw)).strip()
            link = item.findtext("link") or item.findtext("guid") or ""
            m = _ID.search(link)
            tweet_id = m.group(1) if m else None
            url = tweet_url(handle, tweet_id)
            posted_at = None
            pub = item.findtext("pubDate")
            if pub:
                try:
                    posted_at = parsedate_to_datetime(pub)
                except (TypeError, ValueError):
                    posted_at = None
            if text:
                out.append(
                    CandidatePost(
                        source=self.name,
                        url=url,
                        text=text,
                        account=handle,  # official handle -> authoritative in the detector
                        posted_at=posted_at,
                        external_id=tweet_id,
                    )
                )
        return out
