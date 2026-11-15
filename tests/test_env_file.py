import os
from pathlib import Path

import pytest

from dzmod.utils.env_file import EnvFile


def test_create_sets_permissions_and_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("DZMOD_STEAM_LOGIN", raising=False)
    env = EnvFile()

    env.create({"DZMOD_STEAM_LOGIN": "user", "DZMOD_STEAM_ID": "76561190000000000"})

    assert oct(os.stat(env.path).st_mode & 0o777) == "0o600"
    assert EnvFile().get("DZMOD_STEAM_LOGIN") == "user"
    monkeypatch.setenv("DZMOD_STEAM_LOGIN", "other")
    assert EnvFile().get("DZMOD_STEAM_LOGIN") == "other"


def test_api_key_is_never_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    env = EnvFile()

    env.create({"DZMOD_STEAM_LOGIN": "user", "DZMOD_STEAM_API_KEY": "secret"})

    assert "secret" not in env.path.read_text(encoding="utf-8")


def test_stored_api_key_is_removed_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("DZMOD_STEAM_API_KEY", raising=False)
    path = tmp_path / "dzmod" / ".env"
    path.parent.mkdir()
    path.write_text("DZMOD_STEAM_LOGIN=user\nDZMOD_STEAM_API_KEY=secret\n", encoding="utf-8")

    env = EnvFile()

    assert env.removed_api_key
    assert "secret" not in path.read_text(encoding="utf-8")
    assert env.get("DZMOD_STEAM_LOGIN") == "user"
    assert EnvFile.api_key() is None
    assert not EnvFile().removed_api_key


def test_api_key_comes_only_from_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("DZMOD_STEAM_API_KEY", "from-env")

    assert EnvFile.api_key() == "from-env"
