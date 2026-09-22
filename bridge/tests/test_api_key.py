from __future__ import annotations

from pathlib import Path

import pytest

from lagent_bridge.agent import PromptError, require_api_key


def test_env_wins_over_local_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.local.toml").write_text(
        'CURSOR_API_KEY = "from-file"\n', encoding="utf-8"
    )
    monkeypatch.setenv("CURSOR_API_KEY", "from-env")
    assert require_api_key() == "from-env"


def test_toml_and_dotenv_when_env_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.local.toml").write_text(
        'CURSOR_API_KEY = "from-file"\n', encoding="utf-8"
    )
    assert require_api_key() == "from-file"

    (tmp_path / "config.local.toml").unlink()
    (tmp_path / ".env").write_text('export CURSOR_API_KEY="from-dotenv"\n', encoding="utf-8")
    assert require_api_key() == "from-dotenv"


def test_bridge_subdir_toml_before_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    bridge = tmp_path / "bridge"
    bridge.mkdir()
    (bridge / "config.local.toml").write_text(
        'CURSOR_API_KEY = "from-bridge"\n', encoding="utf-8"
    )
    (tmp_path / ".env").write_text("CURSOR_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert require_api_key() == "from-bridge"


def test_missing_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PromptError, match="CURSOR_API_KEY not set"):
        require_api_key()


def test_bad_toml_does_not_echo_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.local.toml").write_text(
        'CURSOR_API_KEY = "super-secret-value\n', encoding="utf-8"
    )
    with pytest.raises(PromptError, match="Could not parse") as exc:
        require_api_key()
    assert "super-secret-value" not in str(exc.value)


def test_example_config_and_gitignore() -> None:
    repo = Path(__file__).resolve().parents[2]
    example = (repo / "bridge" / "config.example.toml").read_text(encoding="utf-8")
    assert 'CURSOR_API_KEY = ""' in example
    assert "crsr_" not in example
    ignored = {
        line.strip()
        for line in (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
    }
    assert ".env" in ignored
    assert "config.local.toml" in ignored
    assert "config.example.toml" not in ignored
