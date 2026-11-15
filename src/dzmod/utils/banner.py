from importlib.resources import files
from typing import ClassVar


class Banner:
    """Renders `dzmod/data/banner.txt`: block characters with `{g}` (gear) and `{t}` (text) markers that switch the
    color of the following characters until the next marker or the end of the line."""

    COLORS: ClassVar[dict[str, str]] = {"g": "\033[38;2;178;16;242m", "t": "\033[38;2;236;232;244m"}
    RESET = "\033[0m"

    def __init__(self, colors: bool) -> None:
        self.colors = colors
        self.lines = files("dzmod").joinpath("data", "banner.txt").read_text(encoding="utf-8").splitlines()

    def render(self) -> str:
        """Replaces the markers with the ANSI color codes and appends a reset to every colored line; without colors
        the markers are removed."""

        rendered = []
        for line in self.lines:
            for marker, code in self.COLORS.items():
                line = line.replace(f"{{{marker}}}", code if self.colors else "")
            rendered.append(f"{line}{self.RESET}" if self.colors and "\033" in line else line)
        return "\n".join(rendered)
