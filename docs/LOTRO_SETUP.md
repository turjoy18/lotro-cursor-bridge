# LOTRO setup and M1 smoke checklist

## Paths

Plugin install:

```text
<Documents>/The Lord of the Rings Online/Plugins/Lagent/
```

PluginData (Account scope — used by Lagent M1):

```text
<Documents>/The Lord of the Rings Online/PluginData/<AccountName>/
```

Character-scoped data (not used by M1 keys, but useful for other plugins) lives under:

```text
.../PluginData/<AccountName>/<ServerName>/<CharacterName>/
```

`<Documents>` is usually `C:\Users\<you>\Documents`. If OneDrive redirects Documents, you may see `...\OneDrive\Documents\...`. Prefer a **local** Documents folder for PluginData when possible; cloud sync can race with the bridge.

## Install plugin

1. Copy the repo’s `plugin/Lagent/` folder into `Plugins/Lagent/` as above (`Lagent.plugin` must sit inside that folder).
2. At character select or in-game, open **Plugin Manager** and enable **Lagent**.
3. Confirm chat shows `[Lagent] v0.1.0 loaded — /lagent`.

## Install bridge

```bash
cd bridge
python -m pip install -e ".[dev]"
```

Run (adjust the path):

```bash
lagent-bridge --path "/c/Users/<you>/Documents/The Lord of the Rings Online/PluginData/<AccountName>" -v
```

You should see `Watching ...` and an initial `LagentIn.plugindata` written with `bridge = "on"`.

## Milestone 1 smoke checklist

Do this **without** Cursor / API keys.

1. Start `lagent-bridge` with `--path` pointing at your Account PluginData directory.
2. Load **Lagent** in LOTRO (or `/plugins load` if you use that workflow).
3. `/lagent` — window opens.
4. Click **Send ping** (or `/lagent ping`).
5. Wait a few seconds for the client to flush PluginData (saves can be delayed).
6. Confirm the bridge log shows `Handled ping id=... -> pong`.
7. Click **Sync** (or `/lagent sync`).
8. Status should show `bridge: on` and last reply `[pong] ... — ok`.

### If Sync shows nothing

- Confirm `--path` is the **Account** folder (same place `LagentOut.plugindata` / `LagentIn.plugindata` appear).
- Wait longer after Send; try Sync again.
- Unload and reload Lagent, then Sync.
- Check bridge `-v` logs for parse errors (wrong file encoding / partial write).

### Offline bridge-only test (no LOTRO)

```bash
mkdir -p /tmp/lagent-pd
# write a ping outbox using the bridge encoder, or:
python -c "from pathlib import Path; from lagent_bridge.protocol import encode_plugindata; Path('/tmp/lagent-pd/LagentOut.plugindata').write_text(encode_plugindata({'id':'req-test','type':'ping','ts':1}), encoding='utf-8')"
lagent-bridge --path /tmp/lagent-pd --once -v
# Inspect LagentIn.plugindata for type=pong
```

On Windows, use a temp directory under `%TEMP%` instead of `/tmp`.

## Next (Milestone 2)

Local Cursor agents on `type = "prompt"` — see issues labeled milestone **M2: Local Cursor agent**. Do not put API keys in the repo.
