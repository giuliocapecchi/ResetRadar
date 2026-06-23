from resetradar.config import Config
from resetradar.sources.nitter import NitterSource

SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>We've reset 5-hour and weekly rate limits for all users.</title>
    <link>https://nitter.net/ClaudeDevs/status/2065621176735646006#m</link>
    <pubDate>Fri, 13 Jun 2026 02:24:00 GMT</pubDate>
  </item>
  <item>
    <title>Artifacts are now live in Claude Code.</title>
    <link>https://nitter.net/ClaudeDevs/status/2067672094209675373#m</link>
    <pubDate>Thu, 18 Jun 2026 18:13:37 GMT</pubDate>
  </item>
</channel></rss>"""


def test_parses_nitter_rss_into_candidate_posts():
    posts = NitterSource(Config())._parse(SAMPLE, "ClaudeDevs")
    assert len(posts) == 2
    first = posts[0]
    assert first.account == "ClaudeDevs"
    assert first.source == "nitter"
    assert first.external_id == "2065621176735646006"
    # nitter link is rewritten to the canonical x.com URL
    assert first.url == "https://x.com/ClaudeDevs/status/2065621176735646006"
    assert first.posted_at is not None and first.posted_at.year == 2026
    assert "reset" in first.text.lower()


def test_malformed_rss_returns_empty_not_raises():
    assert NitterSource(Config())._parse("<not xml", "ClaudeDevs") == []
