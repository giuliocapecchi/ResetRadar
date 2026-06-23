"""Command-line entrypoint: ``resetradar poll`` and ``resetradar serve``."""

from __future__ import annotations

import argparse
import functools
import http.server
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .detector import detect
from .outputs import json_api, rss, telegram
from .store import known_tweet_ids, merge, read_events, write_events

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"


def run_poll(cfg: Config, data_dir: Path, *, fixtures: bool):
    """The full pipeline: collect -> detect -> merge -> write outputs.

    Returns (posts, detected, new_events, all_events)."""
    now = datetime.now(timezone.utc)
    events_path = data_dir / "events.json"
    existing = read_events(events_path)
    if fixtures:
        from .fixtures import sample_posts

        posts = sample_posts()
    else:
        from .sources import build_sources, gather

        # backfill skips tweets already in the ledger
        posts = gather(build_sources(cfg, known_tweet_ids(existing)))

    logging.info("collected %d candidate posts", len(posts))
    detected = detect(posts, account_platform=cfg.account_platform, now=now)
    logging.info("detected %d reset event(s)", len(detected))

    all_events, new_events = merge(existing, detected)
    write_events(events_path, all_events)
    json_api.write_latest(data_dir / "latest.json", all_events, generated_at=now)
    rss.write_feeds(data_dir, all_events, generated_at=now)
    telegram.broadcast(new_events, now=now)  # no-op without secrets; only events < 24h old
    return posts, detected, new_events, all_events


def poll(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config)
    posts, detected, new_events, all_events = run_poll(
        cfg, Path(args.data_dir), fixtures=args.fixtures
    )
    print(
        f"posts={len(posts)} detected={len(detected)} "
        f"new={len(new_events)} total_events={len(all_events)}"
    )
    for event in new_events:
        print(f"  NEW {event.id}  {event.title}")
    if not args.fixtures and not detected:
        # The normal case most of the time - make that clear.
        print(
            "  no global reset right now (expected). Detection relies on the official "
            "X accounts via Nitter; try --fixtures to see the UI."
        )
    return 0


def _write_empty(data_dir: Path) -> None:
    """Write an empty status so the page renders 'no reset on record', not an error."""
    now = datetime.now(timezone.utc)
    json_api.write_latest(data_dir / "latest.json", {}, generated_at=now)
    rss.write_feeds(data_dir, {}, generated_at=now)


def serve(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    # Serve cached data; only poll on the first run (no cache) or with --poll,
    # so repeated `make dev` is instant and offline.
    cached = (data_dir / "latest.json").exists()
    if args.poll or not cached:
        print("seeding local cache…" if not cached else "refreshing (--poll)…")
        try:
            run_poll(Config.load(args.config), data_dir, fixtures=False)
        except Exception as exc:  # noqa: BLE001 - never let a flaky source block serving
            logging.warning("poll failed: %s", exc)
    if not (data_dir / "latest.json").exists():
        _write_empty(data_dir)

    served_from_data = {"/latest.json", "/events.json",
                        "/feed.xml", "/feed-claude.xml", "/feed-codex.xml"}

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path: str) -> str:
            clean = "/" + path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
            if clean in served_from_data:
                return str(data_dir / clean.lstrip("/"))
            return super().translate_path(path)

        def log_message(self, *a):  # quieter console
            pass

    handler = functools.partial(Handler, directory=str(SITE_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://localhost:{args.port}"
    print(f"ResetRadar dashboard -> {url}  (serving cached data; --poll to refresh · Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="resetradar")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)

    p_poll = sub.add_parser("poll", help="fetch sources, detect resets, emit outputs")
    p_poll.add_argument("--config", type=Path, default=None, help="path to config.toml")
    p_poll.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p_poll.add_argument("--fixtures", action="store_true", help="use bundled sample posts")
    p_poll.set_defaults(func=poll)

    p_serve = sub.add_parser("serve", help="serve the dashboard locally (seeds sample data if empty)")
    p_serve.add_argument("--config", type=Path, default=None)
    p_serve.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--poll", action="store_true", help="refresh the cache with a live poll before serving")
    p_serve.set_defaults(func=serve)

    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s %(name)s: %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
