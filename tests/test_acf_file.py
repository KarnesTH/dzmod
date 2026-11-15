from pathlib import Path

from dzmod.core.acf_file import ACFFile


def test_reads_installed_timestamps(tmp_path: Path) -> None:
    acf = tmp_path / "appworkshop_221100.acf"
    acf.write_text(
        '"AppWorkshop"\n{\n\t"WorkshopItemsInstalled"\n\t{\n'
        '\t\t"1559212036"\n\t\t{\n\t\t\t"timeupdated"\t\t"1791897978"\n\t\t}\n'
        '\t\t"1564026768"\n\t\t{\n\t\t\t"timeupdated"\t\t"broken"\n\t\t}\n\t}\n}\n',
        encoding="utf-8",
    )

    assert ACFFile(acf).installed_timestamps() == {"1559212036": 1791897978}


def test_missing_file_is_empty(tmp_path: Path) -> None:
    assert ACFFile(tmp_path / "missing.acf").installed_timestamps() == {}
