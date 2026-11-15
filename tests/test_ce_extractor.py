from pathlib import Path

from dzmod.core.ce_extractor import CEExtractor


def no_choice(kind: str, options: list[str]) -> None:
    return None


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_merges_files_by_content_and_ignores_info_texts(tmp_path: Path) -> None:
    write(tmp_path / "files/types/a.xml",
          '<?xml version="1.0"?>\n<!--c-->\n<types><type name="A"><nominal>1</nominal></type></types>')
    write(tmp_path / "files/types/b.xml", '<types><type name="B"><lifetime>5</lifetime></type></types>')
    write(tmp_path / "files/spawn.xml",
          '<spawnabletypes><damage min="0.1" max="0.2"/><type name="A"><hoarder/></type></spawnabletypes>')
    write(tmp_path / "files/NOTE.xml", "YOU NEED ALL OF THE FILES")
    write(tmp_path / "files/snippet.xml", '<type name="C"><cargo><item name="X"/></cargo></type>')
    write(tmp_path / "Info/cfgeconomycore.xml", '<economycore><ce folder="x"/></economycore>')

    data = CEExtractor(tmp_path, "chernarusplus", no_choice).extract()

    assert list(data.entries["types"]) == ["A", "B"]
    assert sorted(data.entries["spawnabletypes"]) == ["A", "C"]
    assert data.defaults["spawnabletypes"].get("min") == "0.1"
    assert data.invalid == []


def test_duplicates_identical_silent_different_reported(tmp_path: Path) -> None:
    write(tmp_path / "t.xml",
          '<types><type name="A"><nominal>1</nominal></type><type name="A"><nominal>1</nominal></type>'
          '<type name="B"><nominal>1</nominal></type><type name="B"><nominal>2</nominal></type></types>')

    data = CEExtractor(tmp_path, None, no_choice).extract()

    assert data.conflicts == {"types": ["B"]}
    assert data.entries["types"]["B"].find("nominal").text == "2"


def test_map_variants_follow_terrain(tmp_path: Path) -> None:
    for variant in ("Chernarus", "Namalsk"):
        write(tmp_path / f"Types/{variant}/t.xml",
              f'<types><type name="A"><nominal>1</nominal><value name="{variant}"/></type></types>')

    data = CEExtractor(tmp_path, "chernarusplus", no_choice).extract()

    assert data.chosen_variants == {"types": "Types/Chernarus"}
    assert data.entries["types"]["A"].find("value").get("name") == "Chernarus"


def test_unmatched_variants_are_skipped_without_choice(tmp_path: Path) -> None:
    for variant in ("Chernarus", "Namalsk"):
        write(tmp_path / f"Types/{variant}/t.xml", '<types><type name="A"><nominal>1</nominal></type></types>')

    data = CEExtractor(tmp_path, "sakhal", no_choice).extract()

    assert data.skipped_variants == {"types": ["Types/Chernarus", "Types/Namalsk"]}
    assert not data.entries["types"]


def test_broken_xml_reported_and_write_creates_files(tmp_path: Path, parse) -> None:
    mod = tmp_path / "mod"
    write(mod / "broken.xml", "<types><type name=")
    write(mod / "t.xml", '<types><type name="A"><nominal>1</nominal></type></types>')
    extractor = CEExtractor(mod, None, no_choice)
    data = extractor.extract()
    target = tmp_path / "ce"
    target.mkdir()

    written = extractor.write(data, target)

    assert data.invalid == [Path("broken.xml")]
    assert written == [("types.xml", "types", 1)]
    header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    assert (target / "types.xml").read_text(encoding="utf-8").startswith(header)
    assert parse(target / "types.xml")[0].get("name") == "A"
