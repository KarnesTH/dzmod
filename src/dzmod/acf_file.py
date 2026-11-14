import re
from pathlib import Path

TOKEN_PATTERN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])')


class ACFFile:
    """Reads a steam ACF/VDF file into nested dictionaries with lowercased keys."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = self._parse(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def installed_timestamps(self) -> dict[str, int]:
        """Returns `timeupdated` per mod ID from the `WorkshopItemsInstalled` section."""

        items = self.data.get("appworkshop", {}).get("workshopitemsinstalled", {})
        return {
            mod_id: int(entry.get("timeupdated", 0))
            for mod_id, entry in items.items()
            if isinstance(entry, dict)
        }

    @staticmethod
    def _parse(text: str) -> dict:
        """Tokenizes quoted strings and curly braces. A string followed by `{` opens a nested dictionary,
        otherwise the next string is its value."""

        root: dict = {}
        stack = [root]
        key = None

        for match in TOKEN_PATTERN.finditer(text):
            string, brace = match.groups()

            if brace == "{":
                child: dict = {}
                stack[-1][key] = child
                stack.append(child)
                key = None
            elif brace == "}":
                if len(stack) > 1:
                    stack.pop()
                key = None
            elif key is None:
                key = string.lower()
            else:
                stack[-1][key] = string
                key = None

        return root
