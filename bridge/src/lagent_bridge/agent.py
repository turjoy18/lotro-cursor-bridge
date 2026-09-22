"""Local Cursor agent runner for outbound prompt requests.

Uses the async SDK client on purpose: sync ``Agent.create`` /
``Bridge.launch`` hits WinError 10038 on native Windows (select on pipes).
See https://forum.cursor.com/t/170001

On Windows, also expand ``cursor-sdk-bridge.cmd`` to ``node.exe`` + the
bridge ``.js`` so asyncio ``create_subprocess_exec`` can spawn a real
executable (``.cmd`` alone times out on discovery).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_MODEL = "composer-2.5"
DEFAULT_MAX_REPLY_BODY = 8000


class PromptError(Exception):
    """User-facing prompt failure (missing config, SDK, or run error)."""


@dataclass(frozen=True)
class PromptOutcome:
    agent_id: str
    status: str  # finished | error | cancelled | expired
    text: str


def truncate_body(body: str, max_len: int = DEFAULT_MAX_REPLY_BODY) -> str:
    if max_len < 32:
        max_len = 32
    if len(body) <= max_len:
        return body
    marker = "\n…[truncated]"
    keep = max_len - len(marker)
    return body[:keep] + marker


def local_config_candidates(cwd: Path | None = None) -> list[Path]:
    """Gitignored files checked when ``CURSOR_API_KEY`` is unset.

    Search is the process cwd (where you launched the bridge), not ``--cwd``.
    """
    root = Path.cwd() if cwd is None else Path(cwd)
    return [
        root / "bridge" / "config.local.toml",
        root / "config.local.toml",
        root / ".env",
        root / "bridge" / ".env",
    ]


def _key_from_toml(path: Path) -> str:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PromptError(
            f"Could not parse {path.name}. Expected: CURSOR_API_KEY = \"…\""
        ) from exc
    if not isinstance(data, dict):
        return ""
    raw = data.get("CURSOR_API_KEY", "")
    if raw is None:
        return ""
    return str(raw).strip()


def _key_from_env_file(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PromptError(f"Could not read {path.name}") from exc
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if not line.startswith("CURSOR_API_KEY="):
            continue
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value.strip()
    return ""


def key_from_local_file(path: Path) -> str:
    if path.suffix.lower() == ".toml":
        return _key_from_toml(path)
    return _key_from_env_file(path)


def require_api_key(cwd: Path | None = None) -> str:
    """Resolve the Cursor user API key. Env wins over local files.

    Never log or return the key in error text.
    """
    key = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if key:
        return key
    for path in local_config_candidates(cwd):
        if not path.is_file():
            continue
        found = key_from_local_file(path)
        if found:
            log.debug("Using CURSOR_API_KEY from %s", path)
            return found
    raise PromptError(
        "CURSOR_API_KEY not set. Export it in the bridge process, or copy "
        "bridge/config.example.toml to bridge/config.local.toml (gitignored). "
        "Mint a user key at https://cursor.com/dashboard/api"
    )


def expand_bridge_command(launcher: str | Path) -> list[str]:
    """Turn a bridge launcher path into argv safe for ``create_subprocess_exec``.

    Windows wheels ship ``cursor-sdk-bridge.cmd`` which only wraps:
    ``node.exe …/cursor-sdk-bridge.js``. Spawning the ``.cmd`` directly via
    asyncio often never yields the discovery line; invoke node+js instead.
    """
    path = Path(launcher)
    if path.suffix.lower() != ".cmd":
        return [str(path)]

    node = path.with_name("node.exe")
    # .cmd lives in …/bridge/bin/; js is …/bridge/dist/bin/cursor-sdk-bridge.js
    js = path.parent.parent / "dist" / "bin" / "cursor-sdk-bridge.js"
    if not node.is_file():
        raise PromptError(f"cursor-sdk bridge node.exe missing next to launcher: {node}")
    if not js.is_file():
        raise PromptError(f"cursor-sdk bridge script missing: {js}")
    return [str(node), str(js)]


def resolve_bridge_launch_command() -> list[str]:
    """Resolve bundled bridge launcher and expand Windows ``.cmd`` if needed."""
    try:
        from cursor_sdk._vendor import resolve_bridge_path
    except ImportError as exc:
        raise PromptError(
            'cursor-sdk not installed; run: pip install -e ".[cursor]"'
        ) from exc

    launcher = resolve_bridge_path()
    cmd = expand_bridge_command(launcher)
    if sys.platform == "win32" and len(cmd) > 1:
        log.debug("Launching cursor-sdk-bridge via node+js: %s", cmd)
    return cmd


def run_local_prompt(
    text: str,
    *,
    cwd: Path | str,
    agent_id: str | None = None,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
) -> PromptOutcome:
    """Create or resume a local Cursor agent and send one prompt.

    Sync wrapper around the async SDK path (required on Windows).
    """
    prompt = (text or "").strip()
    if not prompt:
        raise PromptError("prompt text is empty")

    workdir = Path(cwd).expanduser().resolve()
    if not workdir.is_dir():
        raise PromptError(f"cwd is not a directory: {workdir}")

    key = (api_key if api_key is not None else require_api_key()).strip()
    if not key:
        raise PromptError("CURSOR_API_KEY is empty")

    try:
        return asyncio.run(
            _run_local_prompt_async(
                prompt,
                workdir=workdir,
                agent_id=agent_id,
                model=model,
                api_key=key,
            )
        )
    except PromptError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface to mailbox
        log.exception("Async agent run failed")
        raise PromptError(f"agent start failed: {exc}") from exc


async def _run_local_prompt_async(
    prompt: str,
    *,
    workdir: Path,
    agent_id: str | None,
    model: str,
    api_key: str,
) -> PromptOutcome:
    try:
        from cursor_sdk import AgentOptions, LocalAgentOptions
        from cursor_sdk.asyncio import AsyncAgent, AsyncClient
    except ImportError as exc:
        raise PromptError(
            'cursor-sdk not installed; run: pip install -e ".[cursor]"'
        ) from exc

    local = LocalAgentOptions(cwd=str(workdir))
    options = AgentOptions(
        api_key=api_key,
        model=model,
        local=local,
    )
    bridge_cmd = resolve_bridge_launch_command()

    try:
        async with await AsyncClient.launch_bridge(
            command=bridge_cmd,
            workspace=str(workdir),
        ) as client:
            if agent_id:
                agent = await AsyncAgent.resume(agent_id, options, client=client)
            else:
                agent = await AsyncAgent.create(options, client=client)
            try:
                run = await agent.send(prompt)
                result = await run.wait()
                status = getattr(result, "status", None) or getattr(run, "status", "error")
                body = getattr(result, "result", None)
                if body is None:
                    body = getattr(run, "result", "") or ""
                resolved_id = getattr(agent, "agent_id", None) or agent_id or ""
                return PromptOutcome(
                    agent_id=str(resolved_id),
                    status=str(status),
                    text=str(body) if body is not None else "",
                )
            finally:
                try:
                    await agent.close()
                except Exception:  # noqa: BLE001
                    log.debug("agent.close() failed", exc_info=True)
    except PromptError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("Agent create/resume/send failed")
        raise PromptError(f"agent start failed: {exc}") from exc
