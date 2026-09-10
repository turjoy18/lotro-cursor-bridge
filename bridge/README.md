# Lagent bridge

Python watcher that reads LOTRO PluginData outbox files and writes inbox replies.

**Milestone 1:** ping/pong mailbox only (no Cursor SDK).

## Install

```bash
cd bridge
python -m pip install -e ".[dev]"
```

## Run

Point `--path` at the PluginData folder for your account/server/character (see docs):

```bash
lagent-bridge --path "$HOME/Documents/The Lord of the Rings Online/PluginData/<account>/<server>/<character>" -v
```

On Windows (Git Bash / PowerShell), use your real Documents path.

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
