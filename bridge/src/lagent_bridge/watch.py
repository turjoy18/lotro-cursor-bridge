"""Watch LOTRO PluginData mailbox files and apply protocol handlers."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from lagent_bridge.protocol import (
    InboxState,
    as_dict,
    decode_plugindata,
    encode_plugindata,
    extract_requests,
    handle_request,
)

log = logging.getLogger(__name__)

DEFAULT_OUT_NAME = "LagentOut.plugindata"
DEFAULT_IN_NAME = "LagentIn.plugindata"


class MailboxWatcher:
    def __init__(
        self,
        path: Path,
        *,
        out_name: str = DEFAULT_OUT_NAME,
        in_name: str = DEFAULT_IN_NAME,
        poll_interval: float = 1.0,
    ) -> None:
        self.path = path
        self.out_path = path / out_name
        self.in_path = path / in_name
        self.poll_interval = poll_interval
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
            reply = handle_request(req, self.seen_ids)
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
        while True:
            try:
                self.poll_once()
            except Exception:  # noqa: BLE001 — keep watcher alive
                log.exception("Poll failed")
            time.sleep(self.poll_interval)
