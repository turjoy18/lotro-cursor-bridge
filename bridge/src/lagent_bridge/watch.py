"""Watch LOTRO PluginData mailbox files and apply protocol handlers."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from lagent_bridge.agent import PromptError, run_local_prompt, truncate_body
from lagent_bridge.protocol import (
    InboxState,
    InReply,
    OutRequest,
    as_dict,
    decode_plugindata,
    encode_plugindata,
    extract_requests,
    handle_request,
)

log = logging.getLogger(__name__)

DEFAULT_OUT_NAME = "LagentOut.plugindata"
DEFAULT_IN_NAME = "LagentIn.plugindata"
MAX_SESSIONS = 10


class MailboxWatcher:
    def __init__(
        self,
        path: Path,
        *,
        out_name: str = DEFAULT_OUT_NAME,
        in_name: str = DEFAULT_IN_NAME,
        poll_interval: float = 1.0,
        cwd: Path | None = None,
        model: str | None = None,
    ) -> None:
        self.path = path
        self.out_path = path / out_name
        self.in_path = path / in_name
        self.poll_interval = poll_interval
        self.cwd = cwd
        self.model = model
        self.seen_ids: set[str] = set()
        self._last_out_mtime: float | None = None
        self.inbox = InboxState(bridge="on")

    def ensure_inbox(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        if self.in_path.exists():
            try:
                parsed = decode_plugindata(self.in_path.read_text(encoding="utf-8"))
                self.inbox = InboxState.from_table(as_dict(parsed))
                for reply in self.inbox.replies:
                    if reply.id:
                        self.seen_ids.add(reply.id)
            except (OSError, ValueError) as exc:
                log.warning("Could not load existing inbox: %s", exc)
        self.inbox.bridge = "on"
        self.write_inbox()

    def write_inbox(self) -> None:
        self.inbox.bridge = "on"
        self.inbox.last_seen = int(time.time())
        payload = encode_plugindata(self.inbox.to_table())
        tmp = self.in_path.with_suffix(".plugindata.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self.in_path)
        log.debug("Wrote inbox %s", self.in_path)

    def upsert_session(self, session: dict) -> None:
        """Replace existing session with same agentId/reqId, else append (capped)."""
        agent_id = str(session.get("agentId") or "")
        req_id = str(session.get("reqId") or "")
        sessions = list(self.inbox.sessions)
        replaced = False
        for i, existing in enumerate(sessions):
            same_agent = agent_id and str(existing.get("agentId") or "") == agent_id
            same_req = req_id and str(existing.get("reqId") or "") == req_id
            if same_agent or same_req:
                sessions[i] = {**existing, **session}
                replaced = True
                break
        if not replaced:
            sessions.append(session)
        self.inbox.sessions = sessions[-MAX_SESSIONS:]

    def handle_prompt(self, req: OutRequest) -> InReply:
        now = int(time.time())
        if self.cwd is None:
            return InReply(
                id=req.id,
                type="error",
                body="prompt requires --cwd (local agent workspace)",
                ts=now,
            )

        self.upsert_session(
            {
                "agentId": req.agent_id or "",
                "reqId": req.id,
                "status": "running",
                "updatedAt": now,
            }
        )
        self.write_inbox()

        try:
            kwargs: dict = {
                "cwd": self.cwd,
                "agent_id": req.agent_id,
            }
            if self.model:
                kwargs["model"] = self.model
            outcome = run_local_prompt(req.text or "", **kwargs)
        except PromptError as exc:
            self.upsert_session(
                {
                    "agentId": req.agent_id or "",
                    "reqId": req.id,
                    "status": "error",
                    "updatedAt": int(time.time()),
                }
            )
            return InReply(id=req.id, type="error", body=truncate_body(str(exc)), ts=now)

        done_at = int(time.time())
        status = outcome.status if outcome.status else "error"
        self.upsert_session(
            {
                "agentId": outcome.agent_id,
                "reqId": req.id,
                "status": status,
                "updatedAt": done_at,
            }
        )
        body = truncate_body(outcome.text or "")
        if status == "finished":
            return InReply(id=req.id, type="result", body=body, ts=done_at)
        return InReply(
            id=req.id,
            type="error",
            body=body or f"agent status: {status}",
            ts=done_at,
        )

    def poll_once(self) -> int:
        """Process outbox if changed. Returns number of new replies."""
        if not self.out_path.exists():
            return 0
        mtime = self.out_path.stat().st_mtime
        if self._last_out_mtime is not None and mtime <= self._last_out_mtime:
            return 0
        try:
            text = self.out_path.read_text(encoding="utf-8")
            parsed = decode_plugindata(text)
        except (OSError, ValueError) as exc:
            log.warning("Failed reading outbox: %s", exc)
            return 0
        self._last_out_mtime = mtime
        requests = extract_requests(parsed)
        added = 0
        for req in requests:
            reply = handle_request(req, self.seen_ids, prompt_handler=self.handle_prompt)
            if reply is None:
                continue
            self.inbox.replies.append(reply)
            added += 1
            log.info("Handled %s id=%s -> %s", req.type, req.id, reply.type)
        if added:
            self.write_inbox()
        else:
            # Still refresh lastSeen / bridge on so Sync shows liveness.
            self.write_inbox()
        return added

    def run_forever(self) -> None:
        self.ensure_inbox()
        log.info("Watching %s (out=%s in=%s)", self.path, self.out_path.name, self.in_path.name)
        if self.cwd is not None:
            log.info("Local agent cwd=%s", self.cwd)
        while True:
            try:
                self.poll_once()
            except Exception:  # noqa: BLE001 — keep watcher alive
                log.exception("Poll failed")
            time.sleep(self.poll_interval)
