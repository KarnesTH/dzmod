from pathlib import Path

from dzmod.core.mod_updater import ModUpdater
from dzmod.core.server_state import ServerState
from dzmod.models.mod_state import ModState
from dzmod.models.workshop_item import WorkshopItem


class StubAPI:
    """Returns fixed Workshop items instead of querying Steam."""

    def __init__(self, items: dict[str, int]) -> None:
        self.items = items

    def fetch(self, mod_ids: list[str]) -> dict[str, WorkshopItem]:
        return {mod_id: WorkshopItem(mod_id=mod_id, title=f"Mod {mod_id}", time_updated=self.items[mod_id])
                for mod_id in mod_ids if mod_id in self.items}


def workshop(steam_dir: Path, timestamps: dict[str, int]) -> None:
    """Creates content folders and an ACF with the given timestamps."""

    entries = ""
    for mod_id, timestamp in timestamps.items():
        content = steam_dir / "steamapps" / "workshop" / "content" / "221100" / mod_id
        content.mkdir(parents=True)
        (content / "meta.cpp").write_text("name = \"x\";", encoding="utf-8")
        entries += f'"{mod_id}" {{ "timeupdated" "{timestamp}" }}\n'
    acf = steam_dir / "steamapps" / "workshop" / "appworkshop_221100.acf"
    acf.write_text(f'"AppWorkshop" {{ "WorkshopItemsInstalled" {{ {entries} }} }}', encoding="utf-8")


def test_check_uses_server_copy_not_shared_workshop(server: Path, tmp_path: Path) -> None:
    steam_dir = tmp_path / "steam"
    workshop(steam_dir, {"100": 200})
    (server / "100").mkdir()
    ServerState(server).set("100", 150)

    states = ModUpdater(server, steam_dir, StubAPI({"100": 200})).check()

    assert states[0].local_updated == 150
    assert states[0].outdated


def test_check_falls_back_to_acf_without_state(server: Path, tmp_path: Path) -> None:
    steam_dir = tmp_path / "steam"
    workshop(steam_dir, {"100": 200})
    (server / "100").mkdir()

    states = ModUpdater(server, steam_dir, StubAPI({"100": 200})).check()

    assert states[0].local_updated == 200
    assert not states[0].outdated


def test_check_marks_mods_missing_in_workshop(server: Path, tmp_path: Path) -> None:
    (server / "100").mkdir()

    states = ModUpdater(server, tmp_path / "steam", StubAPI({})).check()

    assert not states[0].available


def test_in_workshop_splits_current_and_missing(server: Path, tmp_path: Path) -> None:
    steam_dir = tmp_path / "steam"
    workshop(steam_dir, {"100": 200, "101": 100})
    states = [ModState("100", "a", 0, 200), ModState("101", "b", 0, 200), ModState("102", "c", 0, 200)]

    current, missing = ModUpdater(server, steam_dir, StubAPI({})).in_workshop(states)

    assert [state.mod_id for state in current] == ["100"]
    assert [state.mod_id for state in missing] == ["101", "102"]


def test_install_records_state_and_skips_symlinks(server: Path, tmp_path: Path) -> None:
    steam_dir = tmp_path / "steam"
    workshop(steam_dir, {"100": 200})
    secret = tmp_path / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    (steam_dir / "steamapps" / "workshop" / "content" / "221100" / "100" / "link.txt").symlink_to(secret)

    ModUpdater(server, steam_dir, StubAPI({})).install("100")

    assert (server / "100" / "meta.cpp").is_file()
    assert not (server / "100" / "link.txt").exists()
    assert ServerState(server).get("100") == 200
