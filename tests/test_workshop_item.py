from dzmod.models.workshop_item import WorkshopItem


def test_from_detail_with_missing_fields() -> None:
    item = WorkshopItem.from_detail({"publishedfileid": 123, "title": "CF", "file_size": "1024",
                                     "tags": [{"tag": "Mod"}, {"display_name": "x"}]})

    assert item.mod_id == "123"
    assert item.file_size == 1024
    assert item.time_updated == 0
    assert item.tags == ("Mod",)
