import re
from pathlib import Path

from dzmod.utils.errors import DzmodError

TEMPLATE_PATTERN = re.compile(r'^(\s*template\s*=\s*")([^"]+)("\s*;)', re.MULTILINE)


class ServerConfig:
    """Reads and changes the mission template (`<MissionName>.<TerrainName>`) in the server config `serverDZ.cfg`."""

    FILE_NAME = "serverDZ.cfg"

    def __init__(self, server_dir: Path) -> None:
        self.path = server_dir / self.FILE_NAME
        text = self.path.read_text(encoding="utf-8", errors="replace") if self.path.is_file() else ""
        match = TEMPLATE_PATTERN.search(text)
        self.template = match.group(2) if match else None

    @property
    def terrain(self) -> str | None:
        """Returns the lowercased part after the last dot of the template, e.g. `chernarusplus`."""

        return self.template.rsplit(".", 1)[-1].lower() if self.template else None

    def set_template(self, template: str) -> None:
        """Replaces the value of the first `template = "...";` line and keeps the rest of the file unchanged. Raises
        DzmodError if the file or the line does not exist."""

        if not self.path.is_file():
            raise DzmodError("server_config_missing", path=self.path)

        text = self.path.read_text(encoding="utf-8", errors="replace")
        new_text, count = TEMPLATE_PATTERN.subn(lambda m: m.group(1) + template + m.group(3), text, count=1)
        if not count:
            raise DzmodError("template_missing", path=self.path)

        self.path.write_text(new_text, encoding="utf-8")
        self.template = template
