import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

from dzmod.models.ce_data import CEData

XML_DECLARATION = re.compile(rb"^\s*<\?xml[^>]*\?>", re.IGNORECASE)


class CEExtractor:
    """Reads the Central Economy entries (`types`, `spawnabletypes`, `events`) from all XML files of a mod,
    regardless of file names and folder layout, and merges them into one set per kind."""

    KINDS = {"types": "type", "spawnabletypes": "type", "events": "event"}
    FILE_NAMES = {"types": "types.xml", "spawnabletypes": "cfgspawnabletypes.xml", "events": "events.xml"}
    SPAWNABLE_TAGS = {"attachments", "cargo", "hoarder", "damage", "tag"}
    TYPES_TAGS = {"nominal", "lifetime", "restock", "min", "quantmin", "quantmax", "cost", "flags", "category",
                  "usage", "value"}
    XML_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    MAP_ALIASES = {"enoch": "livonia", "livonia": "enoch", "chernarusplus": "chernarus"}

    def __init__(self, mod_dir: Path, terrain: str | None,
                 choose: Callable[[str, list[str]], str | None]) -> None:
        self.mod_dir = mod_dir
        self.terrain = terrain
        self.choose = choose

    def extract(self) -> CEData:
        """Parses every XML file that starts with `<`, sorts its entries into the kinds, resolves map variants and
        merges duplicate names. Files that are no XML at all (info texts with `.xml` extension) are ignored;
        broken XML is reported in `data.invalid`."""

        data = CEData()
        found: dict[str, list[tuple[Path, ET.Element]]] = {kind: [] for kind in self.KINDS}

        for path in sorted(self.mod_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() != ".xml":
                continue

            raw = path.read_bytes().lstrip(b"\xef\xbb\xbf").lstrip()
            if not raw.startswith(b"<"):
                continue

            root = self._parse(raw)
            if root is None:
                data.invalid.append(path.relative_to(self.mod_dir))
                continue

            for kind, element in self._classify(root):
                if element.tag == "damage" and kind == "spawnabletypes":
                    data.defaults.setdefault(kind, element)
                elif element.get("name"):
                    found[kind].append((path, element))

        for kind, entries in found.items():
            entries = self._resolve_variants(kind, entries, data)
            self._merge(kind, entries, data)

        return data

    def write(self, data: CEData, target_dir: Path) -> list[tuple[str, str, int]]:
        """Writes one file per kind with entries into `target_dir` (indented, with XML_HEADER) and returns
        (file name, kind, entry count) for each written file."""

        written = []
        for kind, entries in data.entries.items():
            if not entries:
                continue
            root = ET.Element(kind)
            if kind in data.defaults:
                root.append(data.defaults[kind])
            root.extend(entries.values())
            ET.indent(root, space="    ")

            name = self.FILE_NAMES[kind]
            body = ET.tostring(root, encoding="unicode")
            (target_dir / name).write_text(f"{self.XML_HEADER}\n{body}\n", encoding="utf-8")
            written.append((name, kind, len(entries)))
        return written

    @staticmethod
    def _parse(raw: bytes) -> ET.Element | None:
        """Parses the bytes as XML; if that fails, wraps the content (without XML declaration) in a dummy root so
        snippets without a root element can be read. Returns None if both fail."""

        try:
            return ET.fromstring(raw)
        except ET.ParseError:
            pass
        try:
            return ET.fromstring(b"<dzmod>" + XML_DECLARATION.sub(b"", raw) + b"</dzmod>")
        except ET.ParseError:
            return None

    def _classify(self, root: ET.Element) -> list[tuple[str, ET.Element]]:
        """Returns (kind, element) pairs. A known root element decides the kind for all children; under any other
        root `event` children are events and `type` children are spawnabletypes if they contain spawnable tags,
        otherwise types."""

        if root.tag in self.KINDS:
            return [(root.tag, child) for child in root if child.tag in (self.KINDS[root.tag], "damage")]

        pairs = []
        for child in root:
            if child.tag == "event":
                pairs.append(("events", child))
            elif child.tag == "type":
                tags = {sub.tag for sub in child}
                is_spawnable = tags & self.SPAWNABLE_TAGS and not tags & self.TYPES_TAGS
                pairs.append(("spawnabletypes" if is_spawnable else "types", child))
        return pairs

    def _resolve_variants(self, kind: str, entries: list[tuple[Path, ET.Element]],
                          data: CEData) -> list[tuple[Path, ET.Element]]:
        """Treats directories that define the same names as map variants. Keeps the directory matching the terrain;
        if none or several match, `choose` decides. Without a choice the variant entries of this kind are dropped
        and reported in `data.skipped_variants`."""

        dirs_by_name: dict[str, set[Path]] = {}
        for path, element in entries:
            dirs_by_name.setdefault(element.get("name"), set()).add(path.parent)

        variant_dirs = sorted({d for dirs in dirs_by_name.values() if len(dirs) > 1 for d in dirs})
        if not variant_dirs:
            return entries

        matching = [d for d in variant_dirs if self._matches_terrain(d.name)]
        options = [str(d.relative_to(self.mod_dir)) for d in variant_dirs]

        if len(matching) == 1:
            chosen = matching[0]
        else:
            answer = self.choose(kind, options)
            chosen = variant_dirs[options.index(answer)] if answer in options else None

        if chosen is None:
            data.skipped_variants[kind] = options
            return [(p, e) for p, e in entries if p.parent not in variant_dirs]

        data.chosen_variants[kind] = str(chosen.relative_to(self.mod_dir))
        return [(p, e) for p, e in entries if p.parent not in variant_dirs or p.parent == chosen]

    def _matches_terrain(self, directory: str) -> bool:
        """True if the normalized directory name has at least four characters and it and the terrain (or its alias)
        contain each other."""

        if not self.terrain:
            return False
        name = re.sub(r"[^a-z0-9]", "", directory.lower())
        terrains = {self.terrain, self.MAP_ALIASES.get(self.terrain, self.terrain)}
        return len(name) >= 4 and any(name in terrain or terrain in name for terrain in terrains)

    @staticmethod
    def _merge(kind: str, entries: list[tuple[Path, ET.Element]], data: CEData) -> None:
        """Adds the entries by name in file order. Identical duplicates are dropped; for differing duplicates the
        last definition wins and the name is reported in `data.conflicts`."""

        merged = data.entries.setdefault(kind, {})
        for _, element in entries:
            name = element.get("name")
            if name in merged:
                if ET.tostring(merged[name]).split() != ET.tostring(element).split():
                    data.conflicts.setdefault(kind, []).append(name)
                    merged[name] = element
            else:
                merged[name] = element
