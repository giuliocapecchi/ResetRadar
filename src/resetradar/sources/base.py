"""Source adapter protocol."""

from __future__ import annotations

from typing import Protocol

from ..models import CandidatePost


class Source(Protocol):
    name: str

    def fetch(self) -> list[CandidatePost]:
        """Return recent candidate posts; should not raise for routine failures."""
        ...


def tweet_url(handle: str, tweet_id: str | None) -> str:
    """Canonical x.com URL for a tweet (or the profile if id is unknown)."""
    return f"https://x.com/{handle}/status/{tweet_id}" if tweet_id else f"https://x.com/{handle}"
