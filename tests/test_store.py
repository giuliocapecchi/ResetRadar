import json
from datetime import datetime, timezone

from resetradar.detector import detect
from resetradar.fixtures import sample_posts
from resetradar.outputs import json_api, rss
from resetradar.store import merge, read_events, write_events

NOW = datetime(2026, 6, 22, 18, 0, tzinfo=timezone.utc)
ACCOUNTS = {"claudedevs": "claude", "thsottiaux": "codex"}


def _detected():
    return detect(sample_posts(), account_platform=ACCOUNTS, now=NOW)


def test_first_run_marks_all_new(tmp_path):
    path = tmp_path / "events.json"
    existing = read_events(path)
    all_events, new = merge(existing, _detected())
    assert len(new) == len(all_events) >= 2
    write_events(path, all_events)
    assert path.exists()


def test_rerun_is_idempotent(tmp_path):
    path = tmp_path / "events.json"
    # First run persists events.
    all_events, first_new = merge(read_events(path), _detected())
    write_events(path, all_events)
    assert first_new
    # Second run over the same detections must yield zero new events.
    reloaded, second_new = merge(read_events(path), _detected())
    assert second_new == []
    # …and must not accumulate duplicate source urls.
    for event in reloaded.values():
        assert len(event.source_urls) == len(set(event.source_urls))


def test_outputs_are_wellformed(tmp_path):
    all_events, _ = merge({}, _detected())
    write_events(tmp_path / "events.json", all_events)
    json_api.write_latest(tmp_path / "latest.json", all_events, generated_at=NOW)
    rss.write_feed(tmp_path / "feed.xml", all_events, generated_at=NOW)

    latest = json.loads((tmp_path / "latest.json").read_text())
    assert set(latest["platforms"]) == {"claude", "codex"}
    assert latest["platforms"]["claude"] is not None

    feed = (tmp_path / "feed.xml").read_text()
    assert feed.startswith("<?xml")
    assert "<rss version=\"2.0\"" in feed
    assert 'rel="self"' in feed
    # well-formedness
    import xml.dom.minidom

    xml.dom.minidom.parseString(feed)


def test_per_platform_feeds(tmp_path):
    all_events, _ = merge({}, _detected())
    rss.write_feeds(tmp_path, all_events, generated_at=NOW)
    for name in ("feed.xml", "feed-claude.xml", "feed-codex.xml"):
        assert (tmp_path / name).exists()
    claude = (tmp_path / "feed-claude.xml").read_text()
    assert "<category>claude</category>" in claude
    assert "<category>codex</category>" not in claude
