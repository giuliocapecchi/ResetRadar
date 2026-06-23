"""The events.json ledger and its idempotent merge.

Detected events match existing ones by time proximity (same platform/type within
the cluster window), not exact id, so re-runs and drifting timestamps don't
duplicate. A re-sighting just folds its source url into the existing event.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .detector import event_time, within_window
from .models import ResetEvent, by_recent

# Cap the committed ledger so it (and git history) can't grow without bound.
MAX_EVENTS = 365

_TWEET_ID = re.compile(r"/status/(\d+)")


def known_tweet_ids(events: dict[str, ResetEvent]) -> set[str]:
    """Tweet IDs already in the ledger - lets the backfill skip re-fetching them."""
    return {m.group(1) for e in events.values() for u in e.source_urls
            if (m := _TWEET_ID.search(u))}


def read_events(path: Path) -> dict[str, ResetEvent]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {e["id"]: ResetEvent.from_dict(e) for e in raw}


def _find_match(events: list[ResetEvent], event: ResetEvent) -> ResetEvent | None:
    for existing in events:
        if (
            existing.platform == event.platform
            and existing.type == event.type
            and within_window(event_time(existing), event_time(event))
        ):
            return existing
    return None


def merge(
    existing: dict[str, ResetEvent], detected: list[ResetEvent]
) -> tuple[dict[str, ResetEvent], list[ResetEvent]]:
    """Merge detected events into existing. Return (all, newly_announced)."""
    new: list[ResetEvent] = []
    pool = list(existing.values())
    for event in detected:
        match = _find_match(pool, event)
        if match is None:
            existing[event.id] = event
            pool.append(event)
            new.append(event)
        else:
            match.merge_in(event)  # extra source urls / earlier sighting
    return existing, new


def write_events(path: Path, events: dict[str, ResetEvent]) -> None:
    ordered = by_recent(events.values())[:MAX_EVENTS]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([e.to_dict() for e in ordered], indent=2) + "\n")
