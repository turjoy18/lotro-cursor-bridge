# LOTRO setup and M1 smoke checklist

## Paths

Plugin install:

```text
<Documents>/The Lord of the Rings Online/Plugins/Lagent/
```

PluginData for **Account** scope (Lagent M1 keys `LagentOut` / `LagentIn`):

```text
<Documents>/The Lord of the Rings Online/PluginData/<AccountName>/AllServers/
```

That `AllServers` folder is required. Point the bridge `--path` here — **not** at the account root. If you watch only `PluginData/<AccountName>/`, the game will write the outbox under `AllServers/` and Sync will report no inbox.

Character-scoped data (not used by M1 keys) lives under:

```text
.../PluginData/<AccountName>/<ServerName>/<CharacterName>/
```

`<Documents>` is usually `C:\Users\<you>\Documents`. If OneDrive redirects Documents, you may see `...\OneDrive\Documents\...`. Prefer a **local** Documents folder for PluginData when possible; cloud sync can race with the bridge.

## Install plugin

1. Copy the repo’s `plugin/Lagent/` folder into `Plugins/Lagent/` as above (`Lagent.plugin` must sit inside that folder).
2. At character select or in-game, open **Plugin Manager** and enable **Lagent**.
3. Confirm chat shows `[Lagent] v0.1.3 loaded — AddCommand=1 /lagent` (`AddCommand=0` means the slash name did not bind).
4. Closing the window with **X** only hides it — `/lagent` should still reopen it.
5. In-world reload: `/plugins manager` (character-select Manage Plugins greys Load/Unload). Or `/plugins unload` then `/plugins load Lagent`.

## Install bridge

```bash
cd bridge
python -m pip install -e ".[dev]"
```

Run (adjust the path; include **AllServers**):

```bash
python -m lagent_bridge.main --path "C:/Users/<you>/Documents/The Lord of the Rings Online/PluginData/<AccountName>/AllServers" -v
```

If `lagent-bridge` is not on your PATH, `python -m lagent_bridge.main` is equivalent.

You should see `Watching ...` and an initial `LagentIn.plugindata` written with `bridge = "on"`.

## Milestone 1 smoke checklist

Do this **without** Cursor / API keys.

1. Start the bridge with `--path` pointing at `PluginData/<AccountName>/AllServers`.
2. Load **Lagent** in LOTRO (or `/plugins load` if you use that workflow).
3. `/lagent` — window opens.
4. Click **Send ping** (or `/lagent ping`).
5. Wait a few seconds for the client to flush PluginData (saves can be delayed; OneDrive can add more).
6. Confirm the bridge log shows `Handled ping id=... -> pong`.
7. Click **Sync** (or `/lagent sync`).
8. Status should show `bridge: on` and last reply `[pong] ... — ok`.
9. Close the window with X, then `/lagent` again — window should reopen.

### If Sync shows nothing

- Confirm `--path` ends in **`AllServers`** (same folder as `LagentOut.plugindata` / `LagentIn.plugindata`).
- Wait longer after Send; try Sync again.
- Unload and reload Lagent, then Sync (client may cache PluginData).
- Check bridge `-v` logs for parse errors (wrong file encoding / partial write).

### Offline bridge-only test (no LOTRO)

Use a real Windows path (Git Bash `/tmp` is not visible to Windows Python):

```bash
PD="C:/Users/<you>/AppData/Local/Temp/lagent-pd"
mkdir -p "$PD"
python -c "from pathlib import Path; from lagent_bridge.protocol import encode_plugindata; Path(r'C:/Users/<you>/AppData/Local/Temp/lagent-pd/LagentOut.plugindata').write_text(encode_plugindata({'id':'req-test','type':'ping','ts':1}), encoding='utf-8')"
python -m lagent_bridge.main --path "C:/Users/<you>/AppData/Local/Temp/lagent-pd" --once -v
# Inspect LagentIn.plugindata for type=pong
```

## Milestone 2 (local prompts)

```bash
cd bridge
python -m pip install -e ".[dev,cursor]"
export CURSOR_API_KEY="…"   # or copy config.example.toml → config.local.toml — never commit the key
python -m lagent_bridge.main \
  --path ".../PluginData/<account>/AllServers" \
  --cwd "/path/to/workspace" \
  -v
```

Key setup (env, PowerShell, local file, gitignore): [API_KEY.md](API_KEY.md).

Send prompt in-game → wait for bridge → **Sync**. Inbox `replies` get `type=result` (capped body); the session list shows `running` / `finished` / `error`. Click a row, type the next prompt, **Follow up** (outbox includes that `agentId`). **Send prompt** always starts a new agent. Still Sync-only — no live stream. Do not put API keys in the repo.

Bridge **0.1.2+** uses the async SDK path and launches the Windows bridge via `node.exe` + JS (avoids WinError 10038 and `.cmd` discovery timeouts).
