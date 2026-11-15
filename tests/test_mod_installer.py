from pathlib import Path

from dzmod.core.mod_installer import ModInstaller
from dzmod.core.mod_updater import ModUpdater
from dzmod.core.server_config import ServerConfig
from dzmod.core.workshop_api import WorkshopAPI


def installer_for(server: Path, steam: Path) -> ModInstaller:
    updater = ModUpdater(server_dir=server, steam_dir=steam, api=WorkshopAPI())
    return ModInstaller(updater, ServerConfig(server), lambda title, kind, options: None)


def test_install_copies_mod_keys_and_ce(server: Path, tmp_path: Path) -> None:
    content = tmp_path / "steam" / "steamapps" / "workshop" / "content" / "221100" / "42"
    (content / "keys").mkdir(parents=True)
    (content / "keys" / "mod.bikey").touch()
    (content / "files").mkdir()
    (content / "files" / "types.xml").write_text('<types><type name="A"><nominal>1</nominal></type></types>',
                                                 encoding="utf-8")

    result = installer_for(server, tmp_path / "steam").install("42", "My Mod!")

    mission = server / "mpmissions" / "dayzOffline.chernarusplus"
    assert result.keys == ["mod.bikey"]
    assert result.ce_folder == "ce_my_mod"
    assert (mission / "ce_my_mod" / "types.xml").is_file()
    assert 'folder="ce_my_mod"' in (mission / "cfgeconomycore.xml").read_text(encoding="utf-8")


def test_launch_parameter_order(server: Path, tmp_path: Path) -> None:
    for mod_id in ("9", "1559212036", "5", "2545327648"):
        (server / mod_id).mkdir()

    parameter = installer_for(server, tmp_path).launch_parameter(order=["9"])

    assert parameter == '"-mod=1559212036;2545327648;9;5"'
