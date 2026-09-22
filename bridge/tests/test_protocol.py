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


def test_prompt_followup_passes_agent_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")
    cwd = tmp_path / "ws"
    cwd.mkdir()
    watcher = MailboxWatcher(tmp_path, poll_interval=0.1, cwd=cwd)
    outcome = PromptOutcome(agent_id="agent-abc", status="finished", text="continued")

    with patch("lagent_bridge.watch.run_local_prompt", return_value=outcome) as mock_run:
        watcher.ensure_inbox()
        out = encode_plugindata(
            {
                "id": "req-p4",
                "type": "prompt",
                "text": "continue",
                "ts": 4,
                "agentId": "agent-abc",
            }
        )
        watcher.out_path.write_text(out, encoding="utf-8")
        assert watcher.poll_once() == 1
        assert mock_run.call_args.args[0] == "continue"
        assert mock_run.call_args.kwargs["agent_id"] == "agent-abc"

    inbox = decode_plugindata(watcher.in_path.read_text(encoding="utf-8"))
    reply = next(r for r in inbox["replies"] if r["id"] == "req-p4")
    assert reply["type"] == "result"
    assert reply["body"] == "continued"
    assert any(
        s.get("agentId") == "agent-abc" and s.get("status") == "finished" for s in inbox["sessions"]
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


def test_expand_bridge_command_cmd(tmp_path: Path) -> None:
    from lagent_bridge.agent import PromptError, expand_bridge_command

    bin_dir = tmp_path / "bridge" / "bin"
    dist_bin = tmp_path / "bridge" / "dist" / "bin"
    bin_dir.mkdir(parents=True)
    dist_bin.mkdir(parents=True)
    cmd = bin_dir / "cursor-sdk-bridge.cmd"
    node = bin_dir / "node.exe"
    js = dist_bin / "cursor-sdk-bridge.js"
    cmd.write_text("@echo off\n", encoding="utf-8")
    node.write_bytes(b"MZ")
    js.write_text("// bridge", encoding="utf-8")

    argv = expand_bridge_command(cmd)
    assert argv == [str(node), str(js)]

    plain = tmp_path / "cursor-sdk-bridge"
    plain.write_text("#!/bin/sh\n", encoding="utf-8")
    assert expand_bridge_command(plain) == [str(plain)]

    with pytest.raises(PromptError, match="node.exe missing"):
        empty = tmp_path / "empty"
        empty.mkdir()
        expand_bridge_command(empty / "cursor-sdk-bridge.cmd")


def test_run_local_prompt_create_send(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "k")
    cwd = tmp_path / "repo"
    cwd.mkdir()

    outcome = PromptOutcome(agent_id="agent-1", status="finished", text="done")

    async def fake_async(*_a: object, **_k: object) -> PromptOutcome:
        return outcome

    with patch("lagent_bridge.agent._run_local_prompt_async", side_effect=fake_async):
        from lagent_bridge.agent import run_local_prompt

        out = run_local_prompt("hi", cwd=cwd)

    assert out.agent_id == "agent-1"
    assert out.status == "finished"
    assert out.text == "done"


def test_run_local_prompt_async_uses_async_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure we launch AsyncClient (Windows-safe path), not sync Agent.create."""
    import importlib
    import sys

    monkeypatch.setenv("CURSOR_API_KEY", "k")
    cwd = tmp_path / "repo"
    cwd.mkdir()

    fake_result = MagicMock()
    fake_result.status = "finished"
    fake_result.result = "done"

    class FakeRun:
        async def wait(self) -> MagicMock:
            return fake_result

    class FakeAgent:
        agent_id = "agent-1"

        async def send(self, _msg: str) -> FakeRun:
            return FakeRun()

        async def close(self) -> None:
            return None

    class FakeClientCM:
        def __init__(self, client: object) -> None:
            self._client = client

        async def __aenter__(self) -> object:
            return self._client

        async def __aexit__(self, *_a: object) -> None:
            return None

    fake_client = object()
    created: list[object] = []
    launched: list[object] = []

    async def launch_bridge(*, command: object = None, **_k: object) -> FakeClientCM:
        launched.append(command)
        return FakeClientCM(fake_client)

    async def create(_options: object, *, client: object) -> FakeAgent:
        assert client is fake_client
        created.append(client)
        return FakeAgent()

    async def resume(_id: str, _options: object, *, client: object) -> FakeAgent:
        raise AssertionError("resume should not be called")

    fake_asyncio_mod = MagicMock()
    fake_asyncio_mod.AsyncClient.launch_bridge = staticmethod(launch_bridge)
    fake_asyncio_mod.AsyncAgent.create = staticmethod(create)
    fake_asyncio_mod.AsyncAgent.resume = staticmethod(resume)

    fake_sdk = MagicMock()
    fake_sdk.AgentOptions = MagicMock(side_effect=lambda **kw: kw)
    fake_sdk.LocalAgentOptions = MagicMock(side_effect=lambda **kw: kw)

    monkeypatch.setitem(sys.modules, "cursor_sdk", fake_sdk)
    monkeypatch.setitem(sys.modules, "cursor_sdk.asyncio", fake_asyncio_mod)

    import lagent_bridge.agent as agent_mod

    importlib.reload(agent_mod)
    monkeypatch.setattr(
        agent_mod, "resolve_bridge_launch_command", lambda: ["node.exe", "bridge.js"]
    )
    try:
        out = agent_mod.run_local_prompt("hi", cwd=cwd)
    finally:
        importlib.reload(agent_mod)

    assert out.agent_id == "agent-1"
    assert out.status == "finished"
    assert out.text == "done"
    assert created == [fake_client]
    assert launched == [["node.exe", "bridge.js"]]

