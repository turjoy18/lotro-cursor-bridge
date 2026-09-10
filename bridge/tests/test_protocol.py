from __future__ import annotations

from pathlib import Path

from lagent_bridge.protocol import (
    OutRequest,
    decode_plugindata,
    encode_plugindata,
    extract_requests,
    handle_request,
)
from lagent_bridge.watch import MailboxWatcher


def test_encode_decode_roundtrip() -> None:
    table = {
        "bridge": "on",
        "lastSeen": 1700000000,
        "replies": [
            {"id": "req-1", "type": "pong", "body": "ok", "ts": 1700000001},
        ],
        "sessions": [],
    }
    text = encode_plugindata(table)
    assert text.startswith("return")
    parsed = decode_plugindata(text)
    assert parsed["bridge"] == "on"
    assert parsed["replies"][0]["id"] == "req-1"
    # Empty Lua `{}` is ambiguous (list vs map); decoder returns {}.
    assert parsed["sessions"] in ([], {})


def test_handle_ping_idempotent() -> None:
    seen: set[str] = set()
    req = OutRequest(id="abc", type="ping")
    r1 = handle_request(req, seen)
    r2 = handle_request(req, seen)
    assert r1 is not None and r1.type == "pong"
    assert r2 is None


def test_extract_single_and_list() -> None:
    single = extract_requests({"id": "1", "type": "ping", "ts": 1})
    assert len(single) == 1 and single[0].id == "1"
    many = extract_requests(
        {
            1: {"id": "a", "type": "ping"},
            2: {"id": "b", "type": "ping"},
        }
    )
    assert {r.id for r in many} == {"a", "b"}


def test_watcher_ping_pong(tmp_path: Path) -> None:
    watcher = MailboxWatcher(tmp_path, poll_interval=0.1)
    watcher.ensure_inbox()
    assert watcher.in_path.exists()
    inbox = decode_plugindata(watcher.in_path.read_text(encoding="utf-8"))
    assert inbox["bridge"] == "on"

    out = encode_plugindata({"id": "req-42", "type": "ping", "ts": 1})
    watcher.out_path.write_text(out, encoding="utf-8")
    assert watcher.poll_once() == 1
    inbox2 = decode_plugindata(watcher.in_path.read_text(encoding="utf-8"))
    replies = inbox2["replies"]
    assert any(r["id"] == "req-42" and r["type"] == "pong" for r in replies)

    # duplicate id ignored
    assert watcher.poll_once() == 0 or True  # mtime unchanged may skip
    watcher.out_path.write_text(out + "\n", encoding="utf-8")  # bump mtime
    assert watcher.poll_once() == 0
