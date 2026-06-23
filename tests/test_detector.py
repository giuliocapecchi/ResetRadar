from datetime import datetime, timedelta, timezone

from resetradar.detector import detect
from resetradar.fixtures import sample_posts
from resetradar.models import CandidatePost

NOW = datetime(2026, 6, 22, 18, 0, tzinfo=timezone.utc)
ACCOUNTS = {
    "claudedevs": "claude",
    "anthropicai": "claude",
    "claudeai": "claude",
    "openaidevs": "codex",
    "thsottiaux": "codex",
}


def test_detects_official_claude_reset():
    events = detect(sample_posts(), account_platform=ACCOUNTS, now=NOW)
    resets = [e for e in events if e.platform == "claude" and e.type == "goodwill_reset"]
    assert len(resets) == 1
    assert resets[0].account == "ClaudeDevs"


def test_detects_claude_limit_increase():
    events = detect(sample_posts(), account_platform=ACCOUNTS, now=NOW)
    inc = [e for e in events if e.platform == "claude" and e.type == "limit_increase"]
    assert len(inc) == 1


def test_detects_codex_reset():
    events = detect(sample_posts(), account_platform=ACCOUNTS, now=NOW)
    codex = [e for e in events if e.platform == "codex"]
    assert len(codex) == 1
    assert codex[0].type == "goodwill_reset"


def test_only_official_accounts_mint_events():
    # A non-mapped account, even with perfect reset wording, never mints an event.
    post = CandidatePost(
        source="nitter",
        url="https://x.com/random_user/status/1",
        text="Anthropic just reset everyone's 5-hour and weekly usage limits.",
        account="random_user",
        posted_at=NOW,
    )
    assert detect([post], account_platform=ACCOUNTS, now=NOW) == []


def test_no_false_positives_on_official_decoys():
    # Outage chatter and "service restored" from official accounts must not trigger.
    decoys = [
        CandidatePost(
            source="nitter",
            url="https://x.com/ClaudeDevs/status/d1",
            text="We're investigating elevated error rates on Claude; team is on the incident.",
            account="ClaudeDevs",
            posted_at=NOW,
        ),
        CandidatePost(
            source="nitter",
            url="https://x.com/thsottiaux/status/d2",
            text="Service restored after the outage earlier. Thanks for your patience.",
            account="thsottiaux",
            posted_at=NOW,
        ),
    ]
    assert detect(decoys, account_platform=ACCOUNTS, now=NOW) == []


def test_official_bare_reset_without_limit_noun_is_detected():
    # Casually-worded official posts ("reset button pressed", "double reset") carry
    # no limit/quota word but still mean a usage reset on an official account.
    posts = [
        CandidatePost(
            source="fxtwitter",
            url="https://x.com/thsottiaux/status/2031605592352313567",
            text="OK, Codex is back and stable. Reset button pressed, should see it in a bit",
            account="thsottiaux",
            posted_at=NOW,
        ),
        CandidatePost(
            source="fxtwitter",
            url="https://x.com/thsottiaux/status/2067399435009622521",
            text="We did a sneaky double reset. Not only do you get a full reset on us, "
            "you also get one into the reset bank to use at your leisure.",
            account="thsottiaux",
            posted_at=NOW + timedelta(days=1),
        ),
    ]
    events = detect(posts, account_platform=ACCOUNTS, now=NOW + timedelta(days=2))
    assert len(events) == 2
    assert all(e.platform == "codex" for e in events)


def test_feature_chatter_question_is_not_a_reset():
    # An official account discussing the "bank resets" feature, phrased as a question
    # with no limit noun, must not trigger (real false positive, @thsottiaux Jun 2026).
    post = CandidatePost(
        source="nitter",
        url="https://x.com/thsottiaux/status/2068000000000000000",
        text="Now that you can bank usage resets in Codex. Are you a hoarder or do you "
        "use them without breaking a sweat? How do you think about them?",
        account="thsottiaux",
        posted_at=NOW,
    )
    assert detect([post], account_platform=ACCOUNTS, now=NOW) == []


def test_two_distinct_same_day_resets_stay_separate():
    # Two official resets 12h apart on the same UTC day must NOT collapse.
    morning = CandidatePost(
        source="nitter", url="https://x.com/ClaudeDevs/status/1",
        text="We've reset everyone's 5-hour and weekly rate limits.",
        account="ClaudeDevs", posted_at=datetime(2026, 6, 22, 8, 0, tzinfo=timezone.utc),
    )
    evening = CandidatePost(
        source="nitter", url="https://x.com/ClaudeDevs/status/2",
        text="We've reset everyone's 5-hour and weekly rate limits again.",
        account="ClaudeDevs", posted_at=datetime(2026, 6, 22, 20, 0, tzinfo=timezone.utc),
    )
    events = detect([morning, evening], account_platform=ACCOUNTS, now=NOW)
    assert len(events) == 2


def test_same_reset_merges_across_midnight():
    # The same reset seen on two readers at 23:59 and 00:05 is ONE event, 2 source urls.
    a = CandidatePost(
        source="nitter", url="https://x.com/ClaudeDevs/status/3",
        text="We've reset everyone's rate limits.",
        account="ClaudeDevs", posted_at=datetime(2026, 6, 22, 23, 59, tzinfo=timezone.utc),
    )
    b = CandidatePost(
        source="fxtwitter", url="https://x.com/ClaudeDevs/status/3?fx",
        text="We've reset everyone's rate limits.",
        account="ClaudeDevs", posted_at=datetime(2026, 6, 23, 0, 5, tzinfo=timezone.utc),
    )
    events = detect([a, b], account_platform=ACCOUNTS, now=NOW)
    assert len(events) == 1
    assert len(events[0].source_urls) == 2


def test_detects_resetting_wording():
    # "we're resetting ... limits" must match (regression: \breset\b missed "resetting").
    post = CandidatePost(
        source="nitter", url="https://x.com/ClaudeDevs/status/2067802163498352929",
        text="This is fixed, and we're resetting 5-hour and weekly limits for everyone affected.",
        account="ClaudeDevs", posted_at=datetime(2026, 6, 19, 2, 50, tzinfo=timezone.utc),
    )
    events = detect([post], account_platform=ACCOUNTS, now=NOW)
    assert len(events) == 1 and events[0].platform == "claude"


def test_funding_tweet_is_not_a_reset():
    # Official account, but it's a funding/marketing tweet — no limit noun.
    post = CandidatePost(
        source="nitter", url="https://x.com/AnthropicAI/status/9",
        text="Anthropic raised $3.5B. Everyone is excited about usage of Claude.",
        account="AnthropicAI", posted_at=NOW,
    )
    assert detect([post], account_platform=ACCOUNTS, now=NOW) == []
