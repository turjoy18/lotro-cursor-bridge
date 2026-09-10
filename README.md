# lotro-cursor-bridge

In-game [Lord of the Rings Online](https://www.lotro.com/) panel + local Python bridge that share PluginData files so you can talk to [Cursor](https://cursor.com/) agents **without Alt-Tab**.

LOTRO plugins cannot use the network. This project uses a mailbox pattern:

1. The **Lagent** plugin writes requests via `PluginData.Save`
2. A **Python bridge** on your PC watches those files and writes replies
3. You press **Sync** in-game to load status (and later, agent results)

## Status

- **Milestone 1 (Mailbox):** ping/pong Sync loop — no Cursor required
- **Milestone 2 (Local Cursor agent):** prompt agents from in-game (planned)
- **Milestone 3:** UI polish / cloud (later)

## Layout

```
plugin/Lagent/     LOTRO Lua plugin
bridge/            Python watcher CLI
docs/              Protocol and setup guides
```

## Quick start (Milestone 1)

Full steps and smoke checklist: **[docs/LOTRO_SETUP.md](docs/LOTRO_SETUP.md)**  
Message format: **[docs/PROTOCOL.md](docs/PROTOCOL.md)**

Summary:

1. Copy `plugin/Lagent` → `Documents/The Lord of the Rings Online/Plugins/Lagent/`
2. `cd bridge && python -m pip install -e .`
3. Run `python -m lagent_bridge.main --path <...>/PluginData/<account>/AllServers -v`
4. In-game: `/lagent` → **Send ping** → **Sync** → see pong

## Contributing

Issue → branch → PR. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
