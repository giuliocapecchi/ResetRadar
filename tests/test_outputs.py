from datetime import datetime, timedelta, timezone

from resetradar.models import ResetEvent
from resetradar.outputs.telegram import _format, _fresh

NOW = datetime(2026, 6, 22, 18, 0, tzinfo=timezone.utc)


def _event(first_seen, detail="reset everyone's limits", title="Claude: Limits reset"):
    return ResetEvent(
        id="claude:goodwill_reset:x",
        platform="claude",
        type="goodwill_reset",
        title=title,
        detail=detail,
        first_seen=first_seen,
        source_urls=["https://example.com/p?a=1&b=2"],
    )


def test_telegram_escapes_untrusted_text():
    # Attacker-controlled detail/title must not inject HTML/links into the message.
    event = _event(NOW, detail='reset <b>everyone</b> & <a href="http://evil">click</a> me')
    msg = _format(event)
    assert "<a href=" not in msg
    assert "<b>everyone</b>" not in msg
    assert "&lt;b&gt;everyone&lt;/b&gt;" in msg
    assert "&amp;" in msg
    # Our own intentional markup is still there.
    assert "<b>Claude: Limits reset</b>" in msg


def test_only_recent_events_are_broadcast():
    # A months-old backfill event must be filtered out (no channel spam on reseed);
    # a just-detected one passes.
    old = _event(NOW - timedelta(days=40))
    fresh = _event(NOW - timedelta(hours=2))
    assert _fresh([old, fresh], NOW) == [fresh]
