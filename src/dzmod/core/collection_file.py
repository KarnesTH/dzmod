import re
from datetime import date
from pathlib import Path

from dzmod.models.workshop_item import WorkshopItem

SECTION_PATTERN = re.compile(r"^\[(\w+)\]$")
UPDATED_PATTERN = re.compile(r"^(\s*updated\s*=\s*).*$", re.MULTILINE)


class CollectionFile:
    """Reads and writes a TOML-like collection file with a `[collection]` section (`key = value`) and a `[mods]`
    section holding one mod title per line. Lines starting with `#` are comments."""

    FILE_NAME = "dzmod.col"

    def __init__(self, server_dir: Path) -> None:
        self.path = server_dir / self.FILE_NAME
        self.info: dict[str, str] = {}
        self.mods: list[str] = []

    @property
    def exists(self) -> bool:
        """True if the file exists."""

        return self.path.is_file()

    def read(self) -> None:
        """Parses the file into `info` and `mods`. Unknown sections and duplicate titles (case-insensitive) are
        ignored."""

        self.info, self.mods = {}, []
        section = None

        for raw in self.path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            match = SECTION_PATTERN.match(line)
            if match:
                section = match.group(1).lower()
            elif section == "collection" and "=" in line:
                key, value = line.split("=", 1)
                self.info[key.strip().lower()] = value.strip().strip('"')
            elif section == "mods" and line.casefold() not in {mod.casefold() for mod in self.mods}:
                self.mods.append(line)

    def create(self, name: str, description: str, titles: list[str]) -> None:
        """Writes a new file with name, description, today's date as `created` and `updated`, and the titles."""

        today = date.today().isoformat()
        lines = [
            "[collection]",
            f'name = "{name.replace(chr(34), "")}"',
            f'description = "{description.replace(chr(34), "")}"',
            f"created = {today}",
            f"updated = {today}",
            "",
            "[mods]",
            *titles,
        ]
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.read()

    def append(self, titles: list[str]) -> list[str]:
        """Inserts the titles that are not listed yet (case-insensitive) at the end of the `[mods]` section, keeping the rest of the
        file as it is, sets `updated` to today and returns the added titles. Adds a `[mods]` section if missing."""

        self.read()
        known = {mod.casefold() for mod in self.mods}
        new = []
        for title in titles:
            if title.casefold() not in known:
                known.add(title.casefold())
                new.append(title)
        if not new:
            return []

        lines = self.path.read_text(encoding="utf-8").splitlines()
        header = next((i for i, line in enumerate(lines) if line.strip().lower() == "[mods]"), None)

        if header is None:
            lines += ["", "[mods]", *new]
        else:
            end = next((i for i in range(header + 1, len(lines)) if SECTION_PATTERN.match(lines[i].strip())),
                       len(lines))
            while end - 1 > header and not lines[end - 1].strip():
                end -= 1
            lines[end:end] = new

        text = UPDATED_PATTERN.sub(lambda match: match.group(1) + date.today().isoformat(), "\n".join(lines), count=1)
        self.path.write_text(text + "\n", encoding="utf-8")
        self.read()
        return new

    def resolve(self, items: list[WorkshopItem]) -> tuple[list[WorkshopItem], list[str], dict[str, list[str]]]:
        """Matches every mod title case-insensitively against `items` and returns (resolved items in file order,
        titles without match, titles with several matches and their IDs)."""

        by_title: dict[str, list[WorkshopItem]] = {}
        for item in items:
            by_title.setdefault(item.title.casefold(), []).append(item)

        resolved, missing, ambiguous = [], [], {}
        for title in self.mods:
            matches = by_title.get(title.casefold(), [])
            if len(matches) == 1:
                resolved.append(matches[0])
            elif not matches:
                missing.append(title)
            else:
                ambiguous[title] = [item.mod_id for item in matches]

        return resolved, missing, ambiguous
