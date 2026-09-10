# Lagent bridge

Python watcher that reads LOTRO PluginData outbox files and writes inbox replies.

Milestone 1: ping/pong mailbox only.
Milestone 2: local Cursor agents via `cursor-sdk`.

## Install

```bash
cd bridge
python -m pip install -e .
```

## Run

```bash
lagent-bridge --help
```

Implementation lands in PR for issue #2.
