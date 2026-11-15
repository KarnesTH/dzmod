import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def server(tmp_path: Path) -> Path:
    """Creates a minimal DayZ server directory with a vanilla-like Chernarus mission."""

    server_dir = tmp_path / "server"
    mission = server_dir / "mpmissions" / "dayzOffline.chernarusplus"
    mission.mkdir(parents=True)
    (server_dir / "DayZServer").touch()
    (server_dir / "keys").mkdir()
    (server_dir / "serverDZ.cfg").write_text(
        'hostname = "Test.Server";\nclass Missions\n{\n\tclass DayZ\n\t{\n'
        '\t\ttemplate = "dayzOffline.chernarusplus";\n\t};\n};\n',
        encoding="utf-8",
    )
    (mission / "cfgeconomycore.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<economycore>\n\t<classes>\n'
        '\t\t<rootclass name="DefaultWeapon" />\n\t</classes>\n</economycore>',
        encoding="utf-8",
    )
    (mission / "cfgeventspawns.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<eventposdef>\n'
        '\t<event name="VehicleSedan">\n\t\t<pos x="1" z="2" a="3" />\n\t</event>\n</eventposdef>\n',
        encoding="utf-8",
    )
    return server_dir


@pytest.fixture
def parse() -> Callable[[Path], ET.Element]:
    """Returns a function that parses an XML file and returns its root."""

    return lambda path: ET.parse(path).getroot()
