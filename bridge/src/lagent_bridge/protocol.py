"""Mailbox protocol: Lua PluginData encode/decode and ping handling."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any


_STRING_ESCAPE = {
    "\\": "\\",
    '"': '"',
    "\n": "n",
    "\r": "r",
    "\t": "t",
}


def _escape_lua_string(value: str) -> str:
    out: list[str] = []
    for ch in value:
        if ch in _STRING_ESCAPE:
            out.append("\\" + _STRING_ESCAPE[ch])
        elif ord(ch) < 32:
            out.append(f"\\{ord(ch):03d}")
        else:
            out.append(ch)
    return "".join(out)


def encode_lua(value: Any, indent: int = 0) -> str:
    """Serialize a Python value to a Turbine-style Lua table literal."""
    pad = "\t" * indent
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, str):
        return f'"{_escape_lua_string(value)}"'
    if isinstance(value, list):
        if not value:
            return "{}"
        lines = ["{"]
        for i, item in enumerate(value, start=1):
            encoded = encode_lua(item, indent + 1)
            lines.append(f"{pad}\t[{i}] = {encoded};")
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for key, item in value.items():
            encoded = encode_lua(item, indent + 1)
            if isinstance(key, int):
                key_lit = f"[{key}]"
            else:
                key_lit = f'["{_escape_lua_string(str(key))}"]'
            lines.append(f"{pad}\t{key_lit} = {encoded};")
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    raise TypeError(f"Unsupported type for Lua encode: {type(value)!r}")


def encode_plugindata(table: dict[str, Any]) -> str:
    """Write a full .plugindata document Turbine can Load."""
    body = encode_lua(table, indent=0)
    return f"return\n{body};\n"


class _LuaDecoder:
    def __init__(self, text: str) -> None:
        self.text = text
        self.i = 0

    def decode(self) -> Any:
        self._skip_ws()
        if self.text.startswith("return", self.i):
            self.i += 6
            self._skip_ws()
        value = self._value()
        self._skip_ws()
        if self.i < len(self.text) and self.text[self.i] == ";":
            self.i += 1
        return value

    def _skip_ws(self) -> None:
        while self.i < len(self.text):
            ch = self.text[self.i]
            if ch in " \t\r\n":
                self.i += 1
                continue
            if ch == "-" and self.text.startswith("--", self.i):
                while self.i < len(self.text) and self.text[self.i] not in "\r\n":
                    self.i += 1
                continue
            break

    def _value(self) -> Any:
        self._skip_ws()
        if self.i >= len(self.text):
            raise ValueError("Unexpected end of PluginData")
        ch = self.text[self.i]
        if ch == "{":
            return self._table()
        if ch in "\"'":
            return self._string()
        if self.text.startswith("true", self.i) and self._is_word_end(self.i + 4):
            self.i += 4
            return True
        if self.text.startswith("false", self.i) and self._is_word_end(self.i + 5):
            self.i += 5
            return False
        if self.text.startswith("nil", self.i) and self._is_word_end(self.i + 3):
            self.i += 3
            return None
        return self._number()

    def _is_word_end(self, pos: int) -> bool:
        return pos >= len(self.text) or not (self.text[pos].isalnum() or self.text[pos] == "_")

    def _string(self) -> str:
        quote = self.text[self.i]
        self.i += 1
        out: list[str] = []
        while self.i < len(self.text):
            ch = self.text[self.i]
            if ch == "\\":
                self.i += 1
                if self.i >= len(self.text):
                    break
                esc = self.text[self.i]
                mapping = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
                if esc in mapping:
                    out.append(mapping[esc])
                    self.i += 1
                elif esc.isdigit():
                    m = re.match(r"\d{1,3}", self.text[self.i :])
                    assert m is not None
                    out.append(chr(int(m.group(0))))
                    self.i += len(m.group(0))
                else:
                    out.append(esc)
                    self.i += 1
                continue
            if ch == quote:
                self.i += 1
                return "".join(out)
            out.append(ch)
            self.i += 1
        raise ValueError("Unterminated string in PluginData")

    def _number(self) -> int | float:
        m = re.match(r"[+-]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][+-]?\d+)?", self.text[self.i :])
        if not m:
            raise ValueError(f"Expected number at {self.i}")
        token = m.group(0)
        self.i += len(token)
        if any(c in token for c in ".eE"):
            return float(token)
        return int(token)

    def _table(self) -> dict[Any, Any] | list[Any]:
        self.i += 1  # {
        items: dict[Any, Any] = {}
        array_items: list[Any] = []
        implicit_index = 1
        self._skip_ws()
        while self.i < len(self.text) and self.text[self.i] != "}":
            self._skip_ws()
            if self.text[self.i] == "}":
                break
            key: Any | None = None
            if self.text[self.i] == "[":
                self.i += 1
                self._skip_ws()
                key = self._value()
                self._skip_ws()
                if self.text[self.i] != "]":
                    raise ValueError("Expected ] after table key")
                self.i += 1
                self._skip_ws()
                if self.text[self.i] != "=":
                    raise ValueError("Expected = after table key")
                self.i += 1
                value = self._value()
            else:
                # bare identifier key or implicit array value
                m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", self.text[self.i :])
                if m and self._peek_after(m.end()) == "=":
                    key = m.group(0)
                    self.i += len(key)
                    self._skip_ws()
                    self.i += 1  # =
                    value = self._value()
                else:
                    value = self._value()
                    key = implicit_index
                    implicit_index += 1
            items[key] = value
            if isinstance(key, int):
                while len(array_items) < key:
                    array_items.append(None)
                array_items[key - 1] = value
            self._skip_ws()
            if self.i < len(self.text) and self.text[self.i] in ",;":
                self.i += 1
            self._skip_ws()
        if self.i >= len(self.text) or self.text[self.i] != "}":
            raise ValueError("Unterminated table")
        self.i += 1
        if items and all(isinstance(k, int) for k in items) and sorted(items) == list(range(1, len(items) + 1)):
            return [items[i] for i in range(1, len(items) + 1)]
        return items

    def _peek_after(self, rel: int) -> str:
        j = self.i + rel
        while j < len(self.text) and self.text[j] in " \t\r\n":
            j += 1
        return self.text[j] if j < len(self.text) else ""


def decode_plugindata(text: str) -> Any:
    """Parse a .plugindata document into Python values."""
    text = text.strip()
    if not text:
        return {}
    return _LuaDecoder(text).decode()


def as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    raise ValueError(f"Expected table/dict, got {type(value)!r}")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        keys = sorted(k for k in value if isinstance(k, int))
        if keys:
            return [value[k] for k in keys]
        return list(value.values())
    raise ValueError(f"Expected list/table, got {type(value)!r}")


@dataclass
class OutRequest:
    id: str
    type: str
    text: str | None = None
    ts: int | float | None = None
    agent_id: str | None = None

    @classmethod
    def from_table(cls, table: dict[str, Any]) -> OutRequest:
        return cls(
            id=str(table.get("id", "")),
            type=str(table.get("type", "")),
            text=None if table.get("text") is None else str(table["text"]),
            ts=table.get("ts"),
            agent_id=None if table.get("agentId") is None else str(table["agentId"]),
        )


@dataclass
class InReply:
    id: str
    type: str
    body: str
    ts: int | float

    def to_table(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "body": self.body, "ts": self.ts}


@dataclass
class InboxState:
    bridge: str = "on"
    last_seen: int | float = field(default_factory=lambda: int(time.time()))
    replies: list[InReply] = field(default_factory=list)
    sessions: list[dict[str, Any]] = field(default_factory=list)

    def to_table(self) -> dict[str, Any]:
        return {
            "bridge": self.bridge,
            "lastSeen": int(self.last_seen),
            "replies": [r.to_table() for r in self.replies[-20:]],
            "sessions": self.sessions,
        }

    @classmethod
    def from_table(cls, table: dict[str, Any]) -> InboxState:
        replies_raw = as_list(table.get("replies"))
        replies: list[InReply] = []
        for item in replies_raw:
            if not isinstance(item, dict):
                continue
            replies.append(
                InReply(
                    id=str(item.get("id", "")),
                    type=str(item.get("type", "")),
                    body=str(item.get("body", "")),
                    ts=item.get("ts") or int(time.time()),
                )
            )
        sessions_raw = as_list(table.get("sessions"))
        sessions = [as_dict(s) for s in sessions_raw if isinstance(s, dict)]
        return cls(
            bridge=str(table.get("bridge", "off")),
            last_seen=table.get("lastSeen") or int(time.time()),
            replies=replies,
            sessions=sessions,
        )


def handle_request(req: OutRequest, seen_ids: set[str]) -> InReply | None:
    """Process one outbound request. Returns None if duplicate or unsupported."""
    if not req.id or req.id in seen_ids:
        return None
    seen_ids.add(req.id)
    now = int(time.time())
    if req.type == "ping":
        return InReply(id=req.id, type="pong", body="ok", ts=now)
    if req.type == "prompt":
        # Milestone 2 — acknowledge so Sync still works before Cursor wiring.
        return InReply(
            id=req.id,
            type="error",
            body="prompt not implemented until Milestone 2",
            ts=now,
        )
    return InReply(id=req.id, type="error", body=f"unknown type: {req.type}", ts=now)


def extract_requests(out_value: Any) -> list[OutRequest]:
    """Accept a single request table or a list/map of requests."""
    if out_value is None:
        return []
    if isinstance(out_value, dict):
        if "id" in out_value and "type" in out_value:
            return [OutRequest.from_table(as_dict(out_value))]
        reqs: list[OutRequest] = []
        for item in as_list(out_value):
            if isinstance(item, dict) and "id" in item:
                reqs.append(OutRequest.from_table(as_dict(item)))
        if reqs:
            return reqs
        # map of id -> request
        for item in out_value.values():
            if isinstance(item, dict) and "id" in item:
                reqs.append(OutRequest.from_table(as_dict(item)))
        return reqs
    if isinstance(out_value, list):
        return [OutRequest.from_table(as_dict(item)) for item in out_value if isinstance(item, dict)]
    return []
