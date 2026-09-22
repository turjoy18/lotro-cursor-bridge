# Lagent (LOTRO plugin)

In-game mailbox UI for [lotro-cursor-bridge](https://github.com/turjoy18/lotro-cursor-bridge).

**Version:** 0.1.3

## Install

1. Copy this `Lagent` folder to:

   `Documents/The Lord of the Rings Online/Plugins/Lagent/`

2. In LOTRO: **Plugin Manager** → enable **Lagent**.

3. Chat should show `AddCommand=1` on load. Use `/lagent` to toggle (X only hides). If `AddCommand=0`, `/plugins unload` then `/plugins load Lagent`.

## Controls

| Control | Action |
|---------|--------|
| **Send ping** | Writes `LagentOut` with `type=ping` |
| **Sync** | Loads `LagentIn`: bridge status, last reply, session list |
| **Send prompt** | New `prompt` (no `agentId`) |
| **Follow up** | Same prompt text, plus the clicked session’s `agentId` |
| `/lagent ping` | Same as Send ping |
| `/lagent sync` | Same as Sync (also prints sessions in chat) |

There is no live stream. Send, wait for the bridge, then Sync. Session rows come from inbox `sessions` (`running` / `finished` / `error`). Follow up does nothing until a row with an `agentId` is selected.

PluginData scope: **Account** (`LagentOut` / `LagentIn`).

Bridge `--path` must be:

`Documents/.../PluginData/<AccountName>/AllServers/`
