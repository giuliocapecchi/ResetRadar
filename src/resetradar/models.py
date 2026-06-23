"""Core data structures shared across sources, detection, and storage."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class CandidatePost:
    """A normalized post from any source adapter, ready for detection."""

    source: str  # adapter name, e.g. "nitter", "fxtwitter"
    url: str
    text: str
    account: str | None = None  # handle / author, when known
    posted_at: datetime | None = None
    external_id: str | None = None  # stable id within the source, for de-dup


@dataclass(slots=True)
class ResetEvent:
    """A detected global usage-limit reset/grant for one platform.

    Identity is ``id`` = ``platform:type:ISO-timestamp``, so the same reset seen
    across sources on the same day collapses into one event.
    """

    id: str
    platform: str  # "claude" | "codex"
    type: str  # "goodwill_reset" | "free_reset" | "limit_increase" | "credit"
    title: str
    detail: str
    first_seen: datetime
    effective_at: datetime | None = None
    account: str | None = None  # handle that posted it, e.g. "ClaudeDevs"
    source_urls: list[str] = field(default_factory=list)

    def merge_in(self, other: ResetEvent) -> None:
        """Fold in another sighting of the same reset: dedup source urls and keep
        the earliest sighting."""
        for url in other.source_urls:
            if url not in self.source_urls:
                self.source_urls.append(url)
        self.first_seen = min(self.first_seen, other.first_seen)
        self.effective_at = self.effective_at or other.effective_at

    def to_dict(self) -> dict:
        """Serialize for events.json and latest.json (round-trips via from_dict).
        Optional fields are omitted when empty so the JSON carries no null keys."""
        d = {
            "id": self.id,
            "platform": self.platform,
            "type": self.type,
            "title": self.title,
            "detail": self.detail,
            "first_seen": self.first_seen.isoformat(),
            "source_urls": self.source_urls,
        }
        if self.effective_at:
            d["effective_at"] = self.effective_at.isoformat()
        if self.account:
            d["account"] = self.account
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ResetEvent:
        return cls(
            id=d["id"],
            platform=d["platform"],
            type=d["type"],
            title=d["title"],
            detail=d["detail"],
            first_seen=datetime.fromisoformat(d["first_seen"]),
            effective_at=datetime.fromisoformat(d["effective_at"]) if d.get("effective_at") else None,
            account=d.get("account"),
            source_urls=list(d.get("source_urls", [])),
        )


def by_recent(events: Iterable[ResetEvent]) -> list[ResetEvent]:
    """Events newest-first by first_seen - the canonical display ordering."""
    return sorted(events, key=lambda e: e.first_seen, reverse=True)
