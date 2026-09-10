"""CLI for the LOTRO PluginData mailbox bridge."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from lagent_bridge.watch import MailboxWatcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lagent-bridge",
        description="Watch LOTRO PluginData mailbox files (Milestone 1: ping/pong).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        required=True,
        help="Character (or Account) PluginData directory to watch",
    )
    parser.add_argument(
        "--out-name",
        default="LagentOut.plugindata",
        help="Outbox filename (plugin → bridge)",
    )
    parser.add_argument(
        "--in-name",
        default="LagentIn.plugindata",
        help="Inbox filename (bridge → plugin)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Poll interval in seconds (default: 1)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one poll cycle and exit (for tests)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    path: Path = args.path.expanduser().resolve()
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        logging.info("Created watch path %s", path)

    watcher = MailboxWatcher(
        path,
        out_name=args.out_name,
        in_name=args.in_name,
        poll_interval=args.interval,
    )
    if args.once:
        watcher.ensure_inbox()
        n = watcher.poll_once()
        logging.info("Processed %s new replies", n)
        return

    try:
        watcher.run_forever()
    except KeyboardInterrupt:
        logging.info("Stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
