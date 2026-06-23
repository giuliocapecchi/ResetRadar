"""Pluggable source adapters.

Every adapter exposes ``name`` and ``fetch() -> list[CandidatePost]``. Adding a
source is one new module; nothing else in the pipeline needs to change.
"""

from __future__ import annotations

import logging

from ..config import Config
from ..models import CandidatePost
from .base import Source
from .fxtwitter import FxTwitterSource
from .nitter import NitterSource

log = logging.getLogger("resetradar.sources")


def build_sources(cfg: Config, known_ids: set[str] | None = None) -> list[Source]:
    """Instantiate the enabled adapters for this run."""
    sources: list[Source] = []
    if cfg.nitter_enabled:
        sources.append(NitterSource(cfg))  # primary X reader - free, official timelines
    if cfg.backfill_tweets:
        sources.append(FxTwitterSource(cfg, known_ids))  # verified historical resets, dated
    return sources


def gather(sources: list[Source]) -> list[CandidatePost]:
    """Run every source, isolating failures so one bad source can't sink the run."""
    posts: list[CandidatePost] = []
    for source in sources:
        try:
            fetched = source.fetch()
            log.info("source %s returned %d posts", source.name, len(fetched))
            posts.extend(fetched)
        except Exception as exc:  # noqa: BLE001 - resilience is the point
            log.warning("source %s failed: %s", source.name, exc)
    return posts


__all__ = ["Source", "build_sources", "gather"]
