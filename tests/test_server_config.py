from pathlib import Path

import pytest

from dzmod.core.server_config import ServerConfig
from dzmod.utils.errors import DzmodError


def test_reads_and_sets_only_the_template_line(server: Path) -> None:
    config = ServerConfig(server)
    assert config.template == "dayzOffline.chernarusplus"
    assert config.terrain == "chernarusplus"

    config.set_template("dayzOffline.banov")

    text = (server / "serverDZ.cfg").read_text(encoding="utf-8")
    assert 'template = "dayzOffline.banov";' in text
    assert 'hostname = "Test.Server";' in text
    assert ServerConfig(server).template == "dayzOffline.banov"


def test_set_template_without_file_raises(tmp_path: Path) -> None:
    with pytest.raises(DzmodError) as err:
        ServerConfig(tmp_path).set_template("x.y")
    assert err.value.key == "server_config_missing"
