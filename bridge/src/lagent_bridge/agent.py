"""Local Cursor agent runner for outbound prompt requests.

Uses the async SDK client on purpose: sync ``Agent.create`` /
``Bridge.launch`` hits WinError 10038 on native Windows (select on pipes).
See https://forum.cursor.com/t/170001
"""

from __future__ import annotations

import asyncio
import logging
import os
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


def require_api_key() -> str:
    key = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if not key:
        raise PromptError(
            "CURSOR_API_KEY not set. Mint a user key at https://cursor.com/dashboard/api "
            "and export it in the bridge process environment."
        )
    return key


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

    try:
        async with await AsyncClient.launch_bridge(workspace=str(workdir)) as client:
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
