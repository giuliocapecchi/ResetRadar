"""Load and expose ``config.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"


@dataclass(slots=True)
class Config:
    account_platform: dict[str, str] = field(default_factory=dict)
    nitter_enabled: bool = True
    nitter_instances: list[str] = field(default_factory=list)
    backfill_tweets: list[str] = field(default_factory=list)

    @property
    def x_handles(self) -> list[str]:
        return sorted(self.account_platform)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or DEFAULT_CONFIG_PATH
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
        accounts = {k.lower(): v for k, v in raw.get("accounts", {}).items()}
        return cls(
            account_platform=accounts,
            nitter_enabled=bool(raw.get("nitter", {}).get("enabled", True)),
            nitter_instances=list(raw.get("nitter", {}).get("instances", [])),
            backfill_tweets=list(raw.get("backfill", {}).get("tweets", [])),
        )
