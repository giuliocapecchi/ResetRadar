"""Keyword detection of global usage-limit resets: CandidatePost -> ResetEvent.

Only posts from official mapped accounts mint events. A post needs a reset/grant
verb and a limit noun, or just a plain "reset" verb (enough on an official
account); outage chatter without a global signal is vetoed.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .models import CandidatePost, ResetEvent

# --- vocabularies -----------------------------------------------------------

RESET_TERMS = re.compile(
    r"\b(reset(?:ting|s|ted)?|grant(?:ed|ing)?|gave|giving|"
    r"credit(?:ed|ing|s)?|bonus|extra|doubl(?:e|ed|ing)|increas(?:e|ed|ing)|"
    r"rais(?:e|ed|ing)|bump(?:ed|ing)?)\b",
    re.IGNORECASE,
)
# Core reset verbs - enough on their own for an official account ("reset button
# pressed", "double reset"), see classify_post. "restore" is intentionally not
# here: it's used for service/model-access restoration ("restore access to Claude
# Mythos 5") and not for usage-limit resets in practice.
RESET_CORE = re.compile(r"\b(reset(?:ting|s|ted)?|wiped|cleared)\b", re.IGNORECASE)
# No bare "usage": it co-occurs with non-reset chatter; require a limit word.
LIMIT_TERMS = re.compile(
    r"(\blimits?\b|\bquota\b|rate.?limits?|\b5.?hour\b|\bweekly\b|\bcaps?\b)",
    re.IGNORECASE,
)
GLOBAL_TERMS = re.compile(
    r"(everyone|every ?one's|all users|all of you|for all|globally)",
    re.IGNORECASE,
)
NOW_TERMS = re.compile(r"\b(now|immediately|today|effective immediately|live)\b", re.IGNORECASE)

CLAUDE_TERMS = re.compile(r"\b(claude|anthropic|claude code)\b", re.IGNORECASE)
CODEX_TERMS = re.compile(r"\b(codex|openai|chatgpt|gpt)\b", re.IGNORECASE)

# Anything that smells like an outage post rather than a reset, used to veto.
OUTAGE_TERMS = re.compile(
    r"\b(outage|degraded|elevated errors?|incident|downtime|investigating|"
    r"experiencing issues)\b",
    re.IGNORECASE,
)


def _classify_type(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(one )?free reset\b", t) or "free reset" in t:
        return "free_reset"
    # An explicit reset verb wins over "increase" prose: "fully reset … increased
    # usage drains" describes a bug while announcing a reset, and "double reset"
    # is adjectival on the reset itself. Without this, the increase regex steals
    # the classification (regression: @thsottiaux Jun 18 & Jun 29 2026).
    if RESET_CORE.search(text):
        return "goodwill_reset"
    if re.search(r"\b(doubl|increas|rais|bump|higher|more generous)", t):
        return "limit_increase"
    if re.search(r"\b(credit|compensat|refund)", t):
        return "credit"
    return "goodwill_reset"


def _infer_platform(post: CandidatePost, account_platform: dict[str, str]) -> str | None:
    if post.account:
        key = post.account.lstrip("@").lower()
        if key in account_platform:
            return account_platform[key]
    has_claude = bool(CLAUDE_TERMS.search(post.text))
    has_codex = bool(CODEX_TERMS.search(post.text))
    if has_claude and not has_codex:
        return "claude"
    if has_codex and not has_claude:
        return "codex"
    return None  # unknown or ambiguous -> skip


def _is_official(post: CandidatePost, account_platform: dict[str, str]) -> bool:
    return bool(post.account and post.account.lstrip("@").lower() in account_platform)


def classify_post(
    post: CandidatePost,
    *,
    account_platform: dict[str, str],
    now: datetime,
) -> ResetEvent | None:
    """Return a ResetEvent for an official-account global reset, else None."""
    text = post.text or ""
    if not RESET_TERMS.search(text):
        return None
    if not _is_official(post, account_platform):
        return None  # only official accounts mint events

    platform = _infer_platform(post, account_platform)
    if platform is None:
        return None

    # Need a limit/quota word. An official account's bare "reset" verb also counts
    # ("reset button pressed"), but engagement chatter does not: a question about
    # resets ("bank usage resets ... are you a hoarder?") is discussion, not an
    # announcement, so a "?" on the bare path is vetoed.
    if not LIMIT_TERMS.search(text):
        if not RESET_CORE.search(text) or "?" in text:
            return None

    # Outage chatter without a global signal is vetoed ("restored service after the outage").
    if OUTAGE_TERMS.search(text) and not GLOBAL_TERMS.search(text):
        return None

    when = post.posted_at or now
    effective_at = when if NOW_TERMS.search(text) else None
    event_type = _classify_type(text)

    snippet = " ".join(text.split())
    if len(snippet) > 240:
        snippet = snippet[:237] + "…"

    label = {
        "goodwill_reset": "Usage limits reset for everyone",
        "free_reset": "Free usage-limit reset granted",
        "limit_increase": "Usage limits increased",
        "credit": "Usage credits granted",
    }[event_type]

    return ResetEvent(
        id=f"{platform}:{event_type}",  # group key; final id set in detect()
        platform=platform,
        type=event_type,
        title=f"{platform.capitalize()}: {label}",
        detail=snippet,
        first_seen=when,
        effective_at=effective_at,
        account=post.account,
        source_urls=[post.url] if post.url else [],
    )


# Same-(platform,type) hits within this window are one reset: wide enough to merge
# cross-source/cross-midnight sightings, narrow enough to keep two same-day resets apart.
CLUSTER_WINDOW = timedelta(hours=8)


def event_time(e: ResetEvent) -> datetime:
    return e.effective_at or e.first_seen


def within_window(a: datetime, b: datetime, window: timedelta = CLUSTER_WINDOW) -> bool:
    return abs(a - b) <= window


def detect(
    posts: list[CandidatePost],
    *,
    account_platform: dict[str, str],
    now: datetime | None = None,
) -> list[ResetEvent]:
    """Classify posts and cluster same-reset sightings by time proximity into events."""
    now = now or datetime.now(timezone.utc)
    by_group: dict[str, list[ResetEvent]] = {}
    for post in posts:
        hit = classify_post(post, account_platform=account_platform, now=now)
        if hit is not None:
            by_group.setdefault(hit.id, []).append(hit)

    results: list[ResetEvent] = []
    for hits in by_group.values():
        for cluster in _cluster_by_time(hits):
            event = _build_event(cluster)
            if event is not None:
                results.append(event)
    return results


def _cluster_by_time(hits: list[ResetEvent]) -> list[list[ResetEvent]]:
    """Greedily group same-(platform,type) hits whose times fall within one window."""
    clusters: list[list[ResetEvent]] = []
    for hit in sorted(hits, key=event_time):
        for cluster in clusters:
            if within_window(event_time(hit), event_time(cluster[0])):
                cluster.append(hit)
                break
        else:
            clusters.append([hit])
    return clusters


def _build_event(cluster: list[ResetEvent]) -> ResetEvent:
    """Collapse one time-cluster of sightings into a single event."""
    base = cluster[0]  # time-sorted, so [0] is the earliest sighting
    anchor = event_time(base)
    event = ResetEvent(
        id=f"{base.platform}:{base.type}:{anchor.astimezone(timezone.utc).isoformat()}",
        platform=base.platform,
        type=base.type,
        title=base.title,
        detail=base.detail,
        first_seen=base.first_seen,
        effective_at=base.effective_at,
        account=base.account,
    )
    for h in cluster:
        event.merge_in(h)  # converges source urls, earliest first_seen
    return event
