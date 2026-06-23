"""Sample posts for offline runs and tests (`--fixtures`).

Real, verified historical reset announcements (verbatim wording, real post URLs,
handles, and dates) plus two official-account decoys that MUST NOT trigger.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import CandidatePost


def _utc(y: int, mo: int, d: int, h: int = 12, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def sample_posts() -> list[CandidatePost]:
    return [
        # Claude goodwill reset - @ClaudeDevs, 2026-05-15.
        CandidatePost(
            source="nitter",
            url="https://x.com/ClaudeDevs/status/2068122937308426676",
            text="Happy Friday! We've reset everyone's 5-hour and weekly rate limits.",
            account="ClaudeDevs",
            posted_at=_utc(2026, 5, 15, 14, 0),
            external_id="2068122937308426676",
        ),
        # Claude limit increase - @ClaudeDevs, 2026-05-13.
        CandidatePost(
            source="nitter",
            url="https://x.com/ClaudeDevs/status/2054639777685934564",
            text="Claude Code weekly limits are increasing 50%, now through July 13. Live now for all Pro, Max, Team, and seat-based Enterprise users.",
            account="ClaudeDevs",
            posted_at=_utc(2026, 5, 13, 17, 0),
            external_id="2054639777685934564",
        ),
        # Codex goodwill reset - @thsottiaux, 2026-04-28.
        CandidatePost(
            source="nitter",
            url="https://x.com/thsottiaux/status/2058280452851638313",
            text="I have reset Codex rate limits for ALL paid plans to celebrate a good week and allow everyone to build more with GPT-5.5.",
            account="thsottiaux",
            posted_at=_utc(2026, 4, 28, 18, 0),
            external_id="2058280452851638313",
        ),
        # Decoy - official account, outage chatter, no reset. MUST NOT trigger.
        CandidatePost(
            source="nitter",
            url="https://x.com/ClaudeDevs/status/decoy_incident",
            text="We're investigating elevated error rates on Claude right now; updates to follow.",
            account="ClaudeDevs",
            posted_at=_utc(2026, 5, 15, 9, 0),
            external_id="decoy_incident",
        ),
        # Decoy - official account, service restored after an outage. MUST NOT trigger.
        CandidatePost(
            source="nitter",
            url="https://x.com/thsottiaux/status/decoy_restored",
            text="Service restored after the outage earlier. Thanks for your patience.",
            account="thsottiaux",
            posted_at=_utc(2026, 4, 28, 10, 0),
            external_id="decoy_restored",
        ),
    ]
