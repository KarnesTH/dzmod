import json
import locale
import os
from importlib.resources import files


class Messages:
    """Loads the texts from `dzmod/language/<lang>.json`. German is used if LANG/LC_ALL/LC_MESSAGES or the system
    locale starts with 'de', otherwise English. Keys missing in the selected language fall back to English."""

    FALLBACK = "en"

    def __init__(self) -> None:
        candidates = [os.environ.get(name, "") for name in ("LANG", "LC_ALL", "LC_MESSAGES")]
        candidates.append(locale.getlocale()[0] or "")
        language = next((value for value in candidates if value), "")

        self.fallback = self._load(self.FALLBACK)
        self.texts = self._load("de") if language.lower().startswith("de") else self.fallback

    def get(self, key: str, **values) -> str:
        """Returns the text for `key` formatted with `values`."""

        return self.texts.get(key, self.fallback[key]).format(**values)

    @staticmethod
    def _load(language: str) -> dict[str, str]:
        """Reads `language/<language>.json` from the package."""

        return json.loads(files("dzmod").joinpath("language", f"{language}.json").read_text(encoding="utf-8"))
