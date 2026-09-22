# Cursor API key

The bridge reads a **user** API key to run local agents. It does not log the key. Do not commit it.

Mint one at [cursor.com/dashboard/api](https://cursor.com/dashboard/api).

## Environment variable

The process that starts the bridge must see `CURSOR_API_KEY`. This wins over any local file.

Git Bash / macOS / Linux:

```bash
export CURSOR_API_KEY="paste-your-user-key"
python -m lagent_bridge.main --path ".../AllServers" --cwd "/path/to/workspace" -v
```

PowerShell:

```powershell
$env:CURSOR_API_KEY = "paste-your-user-key"
python -m lagent_bridge.main --path ".../AllServers" --cwd "E:\Code\your-workspace" -v
```

Set it only in that shell (or your user environment). Do not put it in the repo, a plugin file, or chat logs.

## Local config file

If the env var is unset, the bridge reads the first existing file that has a non-empty key, from the **process working directory** (not `--cwd`):

1. `bridge/config.local.toml`
2. `config.local.toml`
3. `.env`
4. `bridge/.env`

From the repo root:

```bash
cp bridge/config.example.toml bridge/config.local.toml
# edit bridge/config.local.toml — set CURSOR_API_KEY, save, do not commit
```

`bridge/config.example.toml` is the committed template. Its value is empty. `config.local.toml` and `.env` are gitignored (any directory).

TOML:

```toml
CURSOR_API_KEY = "paste-your-user-key"
```

`.env` (optional `export`, optional quotes):

```bash
CURSOR_API_KEY="paste-your-user-key"
```

## Check before you commit

```bash
git status
```

`config.local.toml` and `.env` must not appear as files to be committed. If they do, do not `git add` them.
