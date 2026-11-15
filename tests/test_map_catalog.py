import pytest

from dzmod.core.map_catalog import MapCatalog


@pytest.mark.parametrize(("template", "map_id", "expansion"), [
    ("dayzOffline.chernarusplus", None, "Chernarus"),
    ("dayzOffline.enoch", None, "Enoch"),
    ("dayzOffline.sakhal", None, None),
    ("dayzOffline.banovfrost", "3375557599", "0_INCOMPLETE/Banov"),
    ("hardcore.namalsk", "2289461232", "Namalsk/Hardcore"),
    ("empty.valning", "1880753439", "0_INCOMPLETE/Valning"),
])
def test_mission_lookup(template: str, map_id: str | None, expansion: str | None) -> None:
    catalog = MapCatalog()

    assert catalog.map_for_mission(template) == map_id
    assert catalog.expansion_template(template) == expansion


def test_every_map_has_a_valid_source() -> None:
    for record in MapCatalog().maps.values():
        assert record["source"]["type"] in ("github", "mod", "manual")
