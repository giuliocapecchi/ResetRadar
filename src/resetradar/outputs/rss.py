"""Write the RSS feeds: minimal, valid RSS 2.0, newest first.

One combined feed plus a per-platform feed each, so a reader can subscribe to
Claude Code, Codex, or both. Hand-rolled to avoid a dependency.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from ..detector import event_time
from ..models import ResetEvent, by_recent

SITE_URL = "https://giuliocapecchi.github.io/ResetRadar/"

# filename -> (channel title suffix, platform filter or None for all)
FEEDS = {
    "feed.xml": ("Claude Code & Codex usage-limit resets", None),
    "feed-claude.xml": ("Claude Code usage-limit resets", "claude"),
    "feed-codex.xml": ("Codex usage-limit resets", "codex"),
}


def _item(event: ResetEvent) -> str:
    link = event.source_urls[0] if event.source_urls else SITE_URL
    pub = event_time(event).astimezone(timezone.utc)
    return (
        "    <item>\n"
        f"      <title>{escape(event.title)}</title>\n"
        f"      <link>{escape(link)}</link>\n"
        f"      <guid isPermaLink=\"false\">{escape(event.id)}</guid>\n"
        f"      <category>{escape(event.platform)}</category>\n"
        f"      <pubDate>{format_datetime(pub)}</pubDate>\n"
        f"      <description>{escape(event.detail)}</description>\n"
        "    </item>"
    )


def write_feed(
    path: Path,
    events: dict[str, ResetEvent],
    *,
    generated_at: datetime,
    title: str = "Claude Code & Codex usage-limit resets",
    self_name: str = "feed.xml",
) -> None:
    items = "\n".join(_item(e) for e in by_recent(events.values())[:50])
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>ResetRadar: {escape(title)}</title>\n"
        f"    <link>{SITE_URL}</link>\n"
        f'    <atom:link href="{SITE_URL}{self_name}" rel="self" type="application/rss+xml" />\n'
        f"    <description>Global {escape(title)}.</description>\n"
        f"    <lastBuildDate>{format_datetime(generated_at.astimezone(timezone.utc))}</lastBuildDate>\n"
        f"{items}\n"
        "  </channel>\n"
        "</rss>\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml)


def write_feeds(data_dir: Path, events: dict[str, ResetEvent], *, generated_at: datetime) -> None:
    """Write the combined feed plus one feed per platform."""
    for name, (title, platform) in FEEDS.items():
        subset = {k: v for k, v in events.items() if platform is None or v.platform == platform}
        write_feed(data_dir / name, subset, generated_at=generated_at, title=title, self_name=name)
