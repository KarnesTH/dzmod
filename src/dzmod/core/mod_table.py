import os
import sys
from datetime import datetime

from dzmod.models.workshop_item import WorkshopItem
from dzmod.utils.messages import Messages


class ModTable:
    """Prints mods as a plain text table with ID, title, size and last update, sorted by title, followed by the
    count and total size."""

    UNITS = (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024))

    def __init__(self, items: list[WorkshopItem], messages: Messages) -> None:
        self.items = sorted(items, key=lambda item: item.title.casefold())
        self.messages = messages

    def print(self) -> None:
        """Prints header, rows and summary. The title column is as wide as the longest title; on a terminal it is
        shortened with `…` if the line would exceed the terminal width."""

        get = self.messages.get
        sizes = [self.size(item.file_size) for item in self.items]
        dates = [self.date(item.time_updated) for item in self.items]

        size_width = max(len(get("col_size")), *map(len, sizes))
        date_width = max(len(get("col_updated")), *map(len, dates))
        title_width = max(len(get("col_title")), *(len(item.title) for item in self.items))

        if sys.stdout.isatty():
            available = os.get_terminal_size().columns - 12 - size_width - date_width - 6
            title_width = max(min(title_width, available), 10)

        print(f"{get('col_id'):<12}  {get('col_title'):<{title_width}}  {get('col_size'):>{size_width}}  "
              f"{get('col_updated')}")
        for item, size, updated in zip(self.items, sizes, dates):
            title = item.title if len(item.title) <= title_width else item.title[:title_width - 1] + "…"
            print(f"{item.mod_id:<12}  {title:<{title_width}}  {size:>{size_width}}  {updated}")

        total = self.size(sum(item.file_size for item in self.items))
        print()
        print(get("mod_table_summary", count=len(self.items), size=total))

    def size(self, size: int) -> str:
        """Formats bytes with one decimal in GB, MB or KB, using the localized decimal separator."""

        for unit, factor in self.UNITS:
            if size >= factor:
                break
        return f"{size / factor:.1f}".replace(".", self.messages.get("decimal_separator")) + f" {unit}"

    def date(self, timestamp: int) -> str:
        """Formats a Unix timestamp with the localized date format, or returns `-` for 0."""

        return datetime.fromtimestamp(timestamp).strftime(self.messages.get("date_format")) if timestamp else "-"
