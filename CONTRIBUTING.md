# Contributing

This project uses an issue-driven workflow even for solo work.

## Flow

1. Pick or open a GitHub **issue**
2. Create a branch from `main`: `feat/…`, `fix/…`, or `docs/…`
3. Open a **pull request** into `main`
4. Reference the issue with `Closes #N` in the PR body
5. Merge after review (self-review is fine for solo PRs)

Do **not** commit directly to `main` after the bootstrap commit.

## Scope

- Keep PRs small: one issue → one PR
- Milestone 1 is mailbox-only (no Cursor SDK)
- Never commit secrets (`CURSOR_API_KEY`, tokens, local absolute paths with credentials)

## Labels

- `plugin` — LOTRO Lua
- `bridge` — Python bridge
- `docs` — documentation
- `good first issue` — small onboarding tasks

## Local checks (bridge)

```bash
cd bridge
python -m pip install -e ".[dev]"
python -m pytest
```

## Plugin testing

Load/unload via LOTRO Plugin Manager. Prefer **Sync** over full `/reload` when possible; reload if PluginData Load is sticky.
