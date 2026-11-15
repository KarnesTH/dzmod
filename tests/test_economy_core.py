from pathlib import Path

from dzmod.core.economy_core import EconomyCore


def test_upsert_inserts_replaces_and_removes(server: Path, parse) -> None:
    mission = server / "mpmissions" / "dayzOffline.chernarusplus"
    economy = EconomyCore(mission)

    economy.upsert("ce_test", [("types.xml", "types")])
    economy.upsert("ce_test", [("types.xml", "types"), ("events.xml", "events")])

    blocks = parse(mission / "cfgeconomycore.xml").findall("ce")
    assert len(blocks) == 1
    assert [file.get("name") for file in blocks[0]] == ["types.xml", "events.xml"]
    assert "<rootclass" in (mission / "cfgeconomycore.xml").read_text(encoding="utf-8")

    assert economy.remove("ce_test") is True
    assert economy.remove("ce_test") is False
    assert parse(mission / "cfgeconomycore.xml").findall("ce") == []
