"""Broadcast newly-detected resets to a public Telegram channel.

Broadcast only, so there's no server and no subscriber list: the poller POSTs
each fresh event to the channel via the Bot API, and Telegram hosts the channel
and its members. Needs TELEGRAM_BOT_TOKEN + TELEGRAM_CHANNEL_ID (GitHub secrets);
without them it no-ops. Only events from the last FRESH_HOURS are sent, so a run
that (re)seeds months of backfill can't spam the channel.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from html import escape

import httpx

from ..detector import event_time
from ..models import ResetEvent

log = logging.getLogger("resetradar.outputs.telegram")

FRESH_HOURS = 24


def _format(event: ResetEvent) -> str:
    # detail/title come from untrusted post text, so escape before interpolating
    # into an HTML-parsed message (prevents broken sends + link injection).
    lines = [f"🔄 <b>{escape(event.title)}</b>", "", escape(event.detail)]
    if event.source_urls:
        lines += ["", f"Source: {escape(event.source_urls[0])}"]
    return "\n".join(lines)


def _fresh(events: list[ResetEvent], now: datetime) -> list[ResetEvent]:
    cutoff = now - timedelta(hours=FRESH_HOURS)
    return [e for e in events if event_time(e) >= cutoff]


def broadcast(events: list[ResetEvent], *, now: datetime | None = None) -> int:
    """POST each fresh event to the channel. Returns the number actually sent."""
    now = now or datetime.now(timezone.utc)
    fresh = _fresh(events, now)
    if not fresh:
        return 0
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    if not token or not channel:
        for event in fresh:
            log.info("[telegram] no token/channel set; would post:\n%s", _format(event))
        return 0

    sent = 0
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    with httpx.Client(timeout=15) as client:
        for event in fresh:
            resp = client.post(
                url,
                json={
                    "chat_id": channel,
                    "text": _format(event),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
            )
            if resp.is_success:
                sent += 1
            else:
                log.warning("telegram send failed (%s): %s", resp.status_code, resp.text)
    return sent
