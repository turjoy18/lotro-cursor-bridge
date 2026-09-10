# Lagent (LOTRO plugin)

In-game mailbox UI for [lotro-cursor-bridge](https://github.com/turjoy18/lotro-cursor-bridge).

## Install

1. Copy this `Lagent` folder to:

   `Documents/The Lord of the Rings Online/Plugins/Lagent/`

2. In LOTRO: **Plugin Manager** → enable **Lagent** (or `/plugins load Lagent` if available).

3. Use `/lagent` to toggle the window.

## Milestone 1 controls

| Control | Action |
|---------|--------|
| **Send ping** | Writes `LagentOut` with `type=ping` |
| **Sync** | Loads `LagentIn` and shows bridge status + last reply |
| **Send prompt** | Writes a `prompt` request (handled in Milestone 2) |
| `/lagent ping` | Same as Send ping |
| `/lagent sync` | Same as Sync |

PluginData scope: **Account** (`LagentOut` / `LagentIn`). Point the Python bridge `--path` at your Account PluginData directory.
