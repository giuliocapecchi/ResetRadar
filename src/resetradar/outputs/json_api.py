"""Write ``latest.json`` - the public JSON API consumed by the dashboard."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..models import ResetEvent, by_recent

PLATFORMS = ("claude", "codex")
RECENT_LIMIT = 25


def write_latest(path: Path, events: dict[str, ResetEvent], *, generated_at: datetime) -> None:
    ordered = by_recent(events.values())
    latest_by_platform: dict[str, dict | None] = {p: None for p in PLATFORMS}
    for event in ordered:
        if event.platform in latest_by_platform and latest_by_platform[event.platform] is None:
            latest_by_platform[event.platform] = event.to_dict()

    payload = {
        "generated_at": generated_at.isoformat(),
        "platforms": latest_by_platform,
        "recent": [e.to_dict() for e in ordered[:RECENT_LIMIT]],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
