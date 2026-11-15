import re
from pathlib import Path

TEMPLATE_PATTERN = re.compile(r'^\s*template\s*=\s*"([^"]+)"\s*;', re.MULTILINE)


class ServerConfig:
    """Reads the mission template (`<MissionName>.<TerrainName>`) from the server config `serverDZ.cfg`."""

    FILE_NAME = "serverDZ.cfg"

    def __init__(self, server_dir: Path) -> None:
        self.path = server_dir / self.FILE_NAME
        text = self.path.read_text(encoding="utf-8", errors="replace") if self.path.is_file() else ""
        match = TEMPLATE_PATTERN.search(text)
        self.template = match.group(1) if match else None

    @property
    def terrain(self) -> str | None:
        """Returns the lowercased part after the last dot of the template, e.g. `chernarusplus`."""

        return self.template.rsplit(".", 1)[-1].lower() if self.template else None
