import re
import xml.etree.ElementTree as ET
from pathlib import Path


class EconomyCore:
    """Adds or replaces `<ce>` blocks in a mission's cfgeconomycore.xml as plain text, leaving the rest untouched."""

    FILE_NAME = "cfgeconomycore.xml"

    def __init__(self, mission_dir: Path) -> None:
        self.path = mission_dir / self.FILE_NAME

    @property
    def exists(self) -> bool:
        """True if the file exists."""

        return self.path.is_file()

    def upsert(self, folder: str, files: list[tuple[str, str]]) -> None:
        """Checks that the file is valid XML, then replaces an existing `<ce folder="...">` block or inserts a new
        one right before `</economycore>`. `files` holds (file name, CE type) pairs. Raises ValueError if the file
        is no valid XML or has no `</economycore>`."""

        text = self.path.read_text(encoding="utf-8")
        try:
            ET.fromstring(text.encode("utf-8"))
        except ET.ParseError as err:
            raise ValueError(err) from err

        lines = [f'\t<ce folder="{folder}">']
        lines += [f'\t\t<file name="{name}" type="{ce_type}" />' for name, ce_type in files]
        lines.append("\t</ce>\n")
        block = "\n".join(lines)

        pattern = re.compile(rf'[ \t]*<ce\s+folder="{re.escape(folder)}"\s*>.*?</ce>[ \t]*\n?', re.DOTALL)
        if pattern.search(text):
            text = pattern.sub(lambda _: block, text, count=1)
        else:
            end = text.rfind("</economycore>")
            if end < 0:
                raise ValueError("</economycore> not found")
            prefix = text[:end] if text[:end].endswith("\n") else text[:end] + "\n"
            text = prefix + block + text[end:]

        self.path.write_text(text, encoding="utf-8")
