from datetime import datetime
from typing import ClassVar

from dzmod.utils.messages import Messages


class Formatter:
    """Formats sizes and dates with the localized decimal separator and date format."""

    UNITS: ClassVar[tuple[tuple[str, int], ...]] = (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024))

    def __init__(self, messages: Messages) -> None:
        self.messages = messages

    def size(self, size: int) -> str:
        """Formats bytes with one decimal in GB, MB or KB (below 1 KB as KB too)."""

        unit, factor = next(((unit, factor) for unit, factor in self.UNITS if size >= factor), self.UNITS[-1])
        return f"{size / factor:.1f}".replace(".", self.messages.get("decimal_separator")) + f" {unit}"

    def date(self, timestamp: int) -> str:
        """Formats a Unix timestamp with the localized date format, or returns `-` for 0."""

        return datetime.fromtimestamp(timestamp).strftime(self.messages.get("date_format")) if timestamp else "-"
