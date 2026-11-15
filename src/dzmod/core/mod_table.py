import os
import sys

from dzmod.models.workshop_item import WorkshopItem
from dzmod.utils.console import Console
from dzmod.utils.formatter import Formatter
from dzmod.utils.messages import Messages


class ModTable:
    """Prints mods as a table section with ID, title, size and last update, sorted by title, followed by the count and
    total size."""

    def __init__(self, items: list[WorkshopItem], messages: Messages, console: Console) -> None:
        self.items = sorted(items, key=lambda item: item.title.casefold())
        self.messages = messages
        self.console = console
        self.format = Formatter(messages)

    def print(self) -> None:
        """Prints the section header with the mod count, a muted column header, the rows (ID and date muted) and the
        summary. The title column is as wide as the longest title; on a terminal it is shortened with `…` if the
        line would exceed the terminal width."""

        get = self.messages.get
        muted = self.console.muted
        sizes = [self.format.size(item.file_size) for item in self.items]
        dates = [self.format.date(item.time_updated) for item in self.items]

        size_width = max(len(get("col_size")), *map(len, sizes))
        title_width = max(len(get("col_title")), *(len(item.title) for item in self.items))
        if sys.stdout.isatty():
            available = os.get_terminal_size().columns - 2 - 12 - size_width - 10 - 6
            title_width = max(min(title_width, available), 10)

        self.console.section(get("section_subscribed"), get("count_mods", count=len(self.items)))
        print(muted(f"  {get('col_id'):<12}  {get('col_title'):<{title_width}}  {get('col_size'):>{size_width}}  "
                    f"{get('col_updated')}"))
        for item, size, updated in zip(self.items, sizes, dates, strict=True):
            title = item.title if len(item.title) <= title_width else item.title[:title_width - 1] + "…"
            print(f"  {muted(f'{item.mod_id:<12}')}  {title:<{title_width}}  {size:>{size_width}}  {muted(updated)}")

        total = self.format.size(sum(item.file_size for item in self.items))
        self.console.blank()
        self.console.highlight(get("mod_table_summary", count=len(self.items), size=total))
