from pathlib import Path

from dzmod.core.mod_remover import ModRemover
from dzmod.core.server_config import ServerConfig


def add_mod(server: Path, mod_id: str, key: str) -> None:
    keys = server / mod_id / "Keys"
    keys.mkdir(parents=True)
    (keys / key).touch()
    (server / "keys" / key).touch()


def test_shared_key_is_kept_until_last_user_is_removed(server: Path) -> None:
    add_mod(server, "1", "shared.bikey")
    add_mod(server, "2", "shared.bikey")
    remover = ModRemover(server, ServerConfig(server))

    first = remover.remove("1", "CF", remaining=["2"])
    assert first.keys_kept == {"shared.bikey": ["2"]}
    assert (server / "keys" / "shared.bikey").exists()
    assert not (server / "1").exists()

    second = remover.remove("2", "COT", remaining=[])
    assert second.keys_removed == ["shared.bikey"]
    assert not (server / "keys" / "shared.bikey").exists()
