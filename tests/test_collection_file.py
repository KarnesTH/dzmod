from pathlib import Path

from dzmod.core.collection_file import CollectionFile
from dzmod.models.workshop_item import WorkshopItem


def test_create_read_and_append_keep_comments(tmp_path: Path) -> None:
    collection = CollectionFile(tmp_path)
    collection.create("Test", "Desc", ["CF", "Community-Online-Tools"])
    with collection.path.open("a", encoding="utf-8") as file:
        file.write("# own note\nmy mod\n")

    added = collection.append(["cf", "New Mod", "New Mod"])

    assert added == ["New Mod"]
    assert collection.info["name"] == "Test"
    assert collection.mods == ["CF", "Community-Online-Tools", "my mod", "New Mod"]
    assert "# own note" in collection.path.read_text(encoding="utf-8")


def test_resolve_reports_missing_and_ambiguous(tmp_path: Path) -> None:
    collection = CollectionFile(tmp_path)
    collection.create("Test", "", ["cf", "Dup", "Unknown"])
    items = [
        WorkshopItem(mod_id="1", title="CF", time_updated=0),
        WorkshopItem(mod_id="2", title="Dup", time_updated=0),
        WorkshopItem(mod_id="3", title="Dup", time_updated=0),
    ]

    resolved, missing, ambiguous = collection.resolve(items)

    assert [item.mod_id for item in resolved] == ["1"]
    assert missing == ["Unknown"]
    assert ambiguous == {"Dup": ["2", "3"]}
