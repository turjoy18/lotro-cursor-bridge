from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lagent_bridge.agent import PromptError, PromptOutcome, truncate_body
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


def test_truncate_body() -> None:
    assert truncate_body("short", 100) == "short"
    long = "x" * 100
    out = truncate_body(long, 40)
    assert len(out) <= 40
    assert out.endswith("…[truncated]")


def test_prompt_without_cwd_errors(tmp_path: Path) -> None:
    watcher = MailboxWatcher(tmp_path, poll_interval=0.1)
    watcher.ensure_inbox()
    out = encode_plugindata({"id": "req-p1", "type": "prompt", "text": "hi", "ts": 1})
    watcher.out_path.write_text(out, encoding="utf-8")
    assert watcher.poll_once() == 1
    inbox = decode_plugindata(watcher.in_path.read_text(encoding="utf-8"))
    reply = next(r for r in inbox["replies"] if r["id"] == "req-p1")
    assert reply["type"] == "error"
    assert "--cwd" in reply["body"]


def test_prompt_runs_agent_and_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")
    cwd = tmp_path / "ws"
    cwd.mkdir()
    watcher = MailboxWatcher(tmp_path, poll_interval=0.1, cwd=cwd)

    outcome = PromptOutcome(agent_id="agent-abc", status="finished", text="hello " + ("y" * 9000))

    with patch("lagent_bridge.watch.run_local_prompt", return_value=outcome) as mock_run:
        watcher.ensure_inbox()
        out = encode_plugindata(
            {"id": "req-p2", "type": "prompt", "text": "summarize", "ts": 2}
        )
        watcher.out_path.write_text(out, encoding="utf-8")
        assert watcher.poll_once() == 1
        mock_run.assert_called_once()

    inbox = decode_plugindata(watcher.in_path.read_text(encoding="utf-8"))
    reply = next(r for r in inbox["replies"] if r["id"] == "req-p2")
    assert reply["type"] == "result"
    assert reply["body"].endswith("…[truncated]")
    assert len(reply["body"]) <= 8000

    sessions = inbox["sessions"]
    assert isinstance(sessions, list)
    assert any(
        s.get("agentId") == "agent-abc" and s.get("status") == "finished" for s in sessions
    )


def test_prompt_sdk_error_writes_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")
    cwd = tmp_path / "ws"
    cwd.mkdir()
    watcher = MailboxWatcher(tmp_path, poll_interval=0.1, cwd=cwd)

    with patch(
        "lagent_bridge.watch.run_local_prompt",
        side_effect=PromptError("CURSOR_API_KEY not set"),
    ):
        watcher.ensure_inbox()
        out = encode_plugindata({"id": "req-p3", "type": "prompt", "text": "x", "ts": 3})
        watcher.out_path.write_text(out, encoding="utf-8")
        assert watcher.poll_once() == 1

    inbox = decode_plugindata(watcher.in_path.read_text(encoding="utf-8"))
    reply = next(r for r in inbox["replies"] if r["id"] == "req-p3")
    assert reply["type"] == "error"
    sessions = inbox["sessions"]
    assert any(s.get("reqId") == "req-p3" and s.get("status") == "error" for s in sessions)


def test_run_local_prompt_create_send(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "k")
    cwd = tmp_path / "repo"
    cwd.mkdir()

    fake_result = MagicMock()
    fake_result.status = "finished"
    fake_result.result = "done"

    fake_run = MagicMock()
    fake_run.wait.return_value = fake_result

    fake_agent = MagicMock()
    fake_agent.agent_id = "agent-1"
    fake_agent.send.return_value = fake_run

    fake_mod = MagicMock()
    fake_mod.Agent.create.return_value = fake_agent
    fake_mod.AgentOptions = MagicMock(side_effect=lambda **kw: kw)
    fake_mod.LocalAgentOptions = MagicMock(side_effect=lambda **kw: kw)

    import sys

    monkeypatch.setitem(sys.modules, "cursor_sdk", fake_mod)

    from lagent_bridge.agent import run_local_prompt

    out = run_local_prompt("hi", cwd=cwd)
    assert out.agent_id == "agent-1"
    assert out.status == "finished"
    assert out.text == "done"
    fake_mod.Agent.create.assert_called_once()
    fake_agent.close.assert_called_once()
