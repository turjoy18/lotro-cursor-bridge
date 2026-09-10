# Lagent bridge

Python watcher that reads LOTRO PluginData outbox files and writes inbox replies.

**Milestone 1:** ping/pong mailbox only (no Cursor SDK).

## Install

```bash
cd bridge
python -m pip install -e ".[dev]"
```

## Run

For the stock Lagent plugin (Account scope), point `--path` at **AllServers**:

```bash
python -m lagent_bridge.main --path "C:/Users/<you>/Documents/The Lord of the Rings Online/PluginData/<account>/AllServers" -v
```

OneDrive users often have Documents under `.../OneDrive/Documents/...`.

If the `lagent-bridge` script is not on PATH, prefer `python -m lagent_bridge.main`.

Options:

- `--out-name` / `--in-name` — mailbox filenames (default `LagentOut.plugindata` / `LagentIn.plugindata`)
- `--interval` — poll seconds (default `1`)
- `--once` — single poll then exit
- `-v` — debug logs

## Tests

```bash
cd bridge
python -m pytest
```
