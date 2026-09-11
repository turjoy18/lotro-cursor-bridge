# Lagent (LOTRO plugin)

In-game mailbox UI for [lotro-cursor-bridge](https://github.com/turjoy18/lotro-cursor-bridge).

**Version:** 0.1.2

## Install

1. Copy this `Lagent` folder to:

   `Documents/The Lord of the Rings Online/Plugins/Lagent/`

2. In LOTRO: **Plugin Manager** → enable **Lagent**.

3. Chat should show `AddCommand=1` on load. Use `/lagent` to toggle (X only hides). If `AddCommand=0`, `/plugins unload` then `/plugins load Lagent`.

## Milestone 1 controls

| Control | Action |
|---------|--------|
| **Send ping** | Writes `LagentOut` with `type=ping` |
| **Sync** | Loads `LagentIn` and shows bridge status + last reply |
| **Send prompt** | Writes a `prompt` request (handled in Milestone 2) |
| `/lagent ping` | Same as Send ping |
| `/lagent sync` | Same as Sync |

PluginData scope: **Account** (`LagentOut` / `LagentIn`).

Bridge `--path` must be:

`Documents/.../PluginData/<AccountName>/AllServers/`
