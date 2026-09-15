"""Local Cursor agent runner for outbound prompt requests."""

from __future__ import annotations

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
    """Create or resume a local Cursor agent and send one prompt."""
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
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
    except ImportError as exc:
        raise PromptError(
            'cursor-sdk not installed; run: pip install -e ".[cursor]"'
        ) from exc

    options = AgentOptions(
        api_key=key,
        model=model,
        local=LocalAgentOptions(cwd=str(workdir)),
    )

    try:
        if agent_id:
            agent = Agent.resume(agent_id, options)
        else:
            agent = Agent.create(options)
    except Exception as exc:  # noqa: BLE001 — surface to mailbox
        log.exception("Agent create/resume failed")
        raise PromptError(f"agent start failed: {exc}") from exc

    try:
        run = agent.send(prompt)
        result = run.wait()
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
    except PromptError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("Agent send/wait failed")
        resolved_id = getattr(agent, "agent_id", None) or agent_id or ""
        raise PromptError(f"agent run failed: {exc}") from exc
    finally:
        try:
            agent.close()
        except Exception:  # noqa: BLE001
            log.debug("agent.close() failed", exc_info=True)
