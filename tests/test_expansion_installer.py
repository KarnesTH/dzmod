from pathlib import Path

import pytest

from dzmod.core import expansion_installer
from dzmod.core.expansion_installer import ExpansionInstaller


@pytest.fixture
def template_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    template = tmp_path / "repo" / "Template" / "Chernarus"
    (template / "expansion_ce").mkdir(parents=True)
    (template / "expansion_ce" / "expansion_types.xml").write_text("<types/>", encoding="utf-8")
    (template / "cfgeconomycore.xml").write_text(
        '<economycore>\n\t<ce folder="expansion_ce">\n\t\t<file name="expansion_types.xml" type="types" />\n'
        '\t</ce>\n</economycore>', encoding="utf-8")
    (template / "cfgeventspawns.xml").write_text(
        '<eventposdef>\n\t<event name="VehicleUAZ">\n\t\t<pos x="1" z="2" a="3" />\n\t</event>\n</eventposdef>',
        encoding="utf-8")
    monkeypatch.setattr(expansion_installer.GitHubArchive, "get", lambda self: tmp_path / "repo")
    return template


def test_install_and_remove_restore_the_mission(server: Path, template_repo: Path, parse) -> None:
    mission = server / "mpmissions" / "dayzOffline.chernarusplus"
    original_spawns = (mission / "cfgeventspawns.xml").read_text(encoding="utf-8")
    expansion = ExpansionInstaller(mission)

    result = expansion.install("Chernarus")
    expansion.install("Chernarus")

    assert result.files == ["expansion_types.xml"]
    assert result.event_spawns == 1
    assert (mission / "expansion_ce" / "expansion_types.xml").is_file()
    assert [e.get("name") for e in parse(mission / "cfgeventspawns.xml")] == ["VehicleSedan", "VehicleUAZ"]
    assert len(parse(mission / "cfgeconomycore.xml").findall("ce")) == 1

    assert expansion.remove() is True
    assert not (mission / "expansion_ce").exists()
    assert (mission / "cfgeventspawns.xml").read_text(encoding="utf-8") == original_spawns
