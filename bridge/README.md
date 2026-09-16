# Lagent bridge

Python watcher that reads LOTRO PluginData outbox files and writes inbox replies.

**Milestone 1:** ping/pong mailbox.  
**Milestone 2:** local Cursor agents on `type=prompt` via `cursor-sdk`.

## Install

```bash
cd bridge
python -m pip install -e ".[dev,cursor]"
```

Set a user API key (Dashboard → API Keys) in the shell that runs the bridge:

```bash
export CURSOR_API_KEY="…"   # never commit this
```

## Run

For the stock Lagent plugin (Account scope), point `--path` at **AllServers**:

```bash
python -m lagent_bridge.main \
  --path "C:/Users/<you>/Documents/The Lord of the Rings Online/PluginData/<account>/AllServers" \
  --cwd "E:/Code/your-workspace" \
  -v
```

OneDrive users often have Documents under `.../OneDrive/Documents/...`.

If the `lagent-bridge` script is not on PATH, prefer `python -m lagent_bridge.main`.

Options:

- `--cwd` — workspace for local agents (`type=prompt`); required for prompts
- `--model` — optional model id (default `composer-2.5`)
- `--out-name` / `--in-name` — mailbox filenames (default `LagentOut.plugindata` / `LagentIn.plugindata`)
- `--interval` — poll seconds (default `1`)
- `--once` — single poll then exit
- `-v` — debug logs

Bridge package version: **0.1.1**. Local prompts use the **async** `cursor-sdk` client (sync `Agent.create` hits WinError 10038 on native Windows).

## Tests

```bash
cd bridge
python -m pip install -e ".[dev]"
python -m pytest
```
