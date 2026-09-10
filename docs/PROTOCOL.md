# Mailbox protocol

LOTRO plugins cannot open sockets. The bridge and plugin share two PluginData documents (Lua tables serialized by the client / bridge).

| Direction | PluginData key | Default filename | Role |
|-----------|----------------|------------------|------|
| Plugin → bridge | `LagentOut` | `LagentOut.plugindata` | Requests |
| Bridge → plugin | `LagentIn` | `LagentIn.plugindata` | Status + replies |

**Scope (M1 plugin):** `Turbine.DataScope.Account`  
Point `lagent-bridge --path` at the matching Account PluginData directory (see [LOTRO_SETUP.md](LOTRO_SETUP.md)).

## Outbound (`LagentOut`)

Single request table (M1 writes one request at a time):

```lua
{
  id = "req-1234-5678",   -- required, unique; bridge ignores duplicates
  type = "ping",          -- "ping" | "prompt" (prompt handled in M2)
  text = "optional",      -- used for prompt
  ts = 123456,            -- optional ordering hint
  agentId = "optional",   -- M2 follow-up
}
```

## Inbound (`LagentIn`)

```lua
{
  bridge = "on",          -- "on" while watcher is running
  lastSeen = 1234567890,  -- unix seconds from bridge host
  replies = {
    [1] = {
      id = "req-1234-5678",
      type = "pong",      -- "pong" | "error" | (M2) agent summary types
      body = "ok",
      ts = 1234567890,
    },
  },
  sessions = {            -- empty in M1; filled in M2
  },
}
```

## File format

Documents are Turbine-style Lua:

```lua
return
{
	["bridge"] = "on";
	["lastSeen"] = 1700000000;
	["replies"] = {
		[1] = {
			["id"] = "req-1";
			["type"] = "pong";
			["body"] = "ok";
			["ts"] = 1700000001;
		};
	};
	["sessions"] = {
	};
};
```

The Python bridge both reads and writes this shape (`lagent_bridge.protocol`).

## Idempotency

- Every request **must** include a stable `id`.
- The bridge keeps seen ids (and reloads them from existing inbox replies on startup).
- Re-sending the same outbox content after a mtime bump does not create a second reply for the same id.

## Sync UX

There is **no** live push into the game client:

1. **Send** → plugin `PluginData.Save` outbox (may be delayed by the client)
2. Bridge polls, handles request, rewrites inbox
3. **Sync** → plugin `PluginData.Load` inbox (async at runtime)

If Load looks stale, unload/reload the plugin or use the client’s reload flow, then Sync again.
