import json
from importlib.resources import files


def test_languages_have_the_same_keys() -> None:
    texts = {lang: json.loads(files("dzmod").joinpath("language", f"{lang}.json").read_text(encoding="utf-8"))
             for lang in ("en", "de")}

    assert set(texts["en"]) == set(texts["de"])
