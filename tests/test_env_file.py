import os
from pathlib import Path

import pytest

from dzmod.utils.env_file import EnvFile


def test_create_sets_permissions_and_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("DZMOD_STEAM_LOGIN", raising=False)
    env = EnvFile()

    env.create({"DZMOD_STEAM_LOGIN": "user", "DZMOD_STEAM_API_KEY": "key"})

    assert oct(os.stat(env.path).st_mode & 0o777) == "0o600"
    assert EnvFile().get("DZMOD_STEAM_LOGIN") == "user"
    monkeypatch.setenv("DZMOD_STEAM_LOGIN", "other")
    assert EnvFile().get("DZMOD_STEAM_LOGIN") == "other"
