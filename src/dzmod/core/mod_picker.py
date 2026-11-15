import curses
import locale
from datetime import datetime

from dzmod.utils.messages import Messages
from dzmod.models.workshop_item import WorkshopItem


class ModPicker:
    """Shows the mods in a curses list. Arrow keys/j/k move, PgUp/PgDn page, Home/End jump, Space toggles a mod,
    Enter confirms and q/Esc cancels."""

    KEYS_UP = (curses.KEY_UP, ord("k"))
    KEYS_DOWN = (curses.KEY_DOWN, ord("j"))
    KEYS_CONFIRM = (curses.KEY_ENTER, 10, 13)
    KEYS_CANCEL = (ord("q"), 27)

    def __init__(self, items: list[WorkshopItem], messages: Messages, verbose: bool) -> None:
        self.items = items
        self.messages = messages
        self.verbose = verbose
        self.selected: set[int] = set()
        self.cursor = 0
        self.top = 0

    def run(self) -> list[WorkshopItem]:
        """Applies the system locale if available, runs the picker and returns the selected mods in list order, or an
        empty list if canceled."""

        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass
        confirmed = curses.wrapper(self._loop)
        return [self.items[i] for i in sorted(self.selected)] if confirmed else []

    def _loop(self, screen: curses.window) -> bool:
        """Draws the list and handles keys until Enter (True) or q/Esc (False)."""

        curses.curs_set(0)
        screen.keypad(True)
        curses.set_escdelay(25)

        while True:
            height, width = screen.getmaxyx()
            rows = max(height - 3, 1)
            self._scroll(rows)
            self._draw(screen, rows, width)

            key = screen.getch()
            if key in self.KEYS_UP:
                self.cursor -= 1
            elif key in self.KEYS_DOWN:
                self.cursor += 1
            elif key == curses.KEY_PPAGE:
                self.cursor -= rows
            elif key == curses.KEY_NPAGE:
                self.cursor += rows
            elif key == curses.KEY_HOME:
                self.cursor = 0
            elif key == curses.KEY_END:
                self.cursor = len(self.items) - 1
            elif key == ord(" "):
                self.selected ^= {self.cursor}
                self.cursor += 1
            elif key in self.KEYS_CONFIRM:
                return True
            elif key in self.KEYS_CANCEL:
                return False

            self.cursor = min(max(self.cursor, 0), len(self.items) - 1)

    def _scroll(self, rows: int) -> None:
        """Moves the visible window so the cursor stays on screen."""

        self.cursor = min(max(self.cursor, 0), len(self.items) - 1)
        if self.cursor < self.top:
            self.top = self.cursor
        elif self.cursor >= self.top + rows:
            self.top = self.cursor - rows + 1

    def _draw(self, screen: curses.window, rows: int, width: int) -> None:
        """Draws header, visible rows, status line and key help, each cut to the terminal width."""

        screen.erase()
        get = self.messages.get
        header = self._row(" ", get("col_id"), get("col_title"), get("col_updated"),
                           get("col_subscriptions"), get("col_size"), get("col_created"), get("col_tags"), width)
        self._put(screen, 0, header, width, curses.A_BOLD)

        for line, index in enumerate(range(self.top, min(self.top + rows, len(self.items))), start=1):
            item = self.items[index]
            row = self._row(
                "x" if index in self.selected else " ",
                item.mod_id,
                item.title,
                self._date(item.time_updated),
                f"{item.subscriptions:,}".replace(",", "."),
                f"{item.file_size / 1_048_576:.1f} MB",
                self._date(item.time_created),
                ", ".join(item.tags),
                width,
            )
            self._put(screen, line, row, width, curses.A_REVERSE if index == self.cursor else curses.A_NORMAL)

        status = get("picker_status", selected=len(self.selected), position=self.cursor + 1, total=len(self.items))
        self._put(screen, rows + 1, status, width, curses.A_BOLD)
        self._put(screen, rows + 2, get("picker_help"), width, curses.A_DIM)
        screen.refresh()

    def _row(self, mark: str, mod_id: str, title: str, updated: str, subscriptions: str, size: str, created: str,
             tags: str, width: int) -> str:
        """Builds one line with fixed-width columns; the title takes the remaining width. The last four columns are
        only included in verbose mode."""

        fixed = f"[{mark}] {mod_id:<12} "
        tail = f" {updated:<12}"
        if self.verbose:
            tail += f" {subscriptions:>11} {size:>10} {created:<12} "

        title_width = max(width - len(fixed) - len(tail) - (20 if self.verbose else 1), 10)
        title = title[:title_width - 1] + "…" if len(title) > title_width else title
        return f"{fixed}{title:<{title_width}}{tail}{tags if self.verbose else ''}"

    def _date(self, timestamp: int) -> str:
        """Formats a Unix timestamp with the localized date format, or returns `-` for 0."""

        return datetime.fromtimestamp(timestamp).strftime(self.messages.get("date_format")) if timestamp else "-"

    @staticmethod
    def _put(screen: curses.window, y: int, text: str, width: int, attr: int) -> None:
        """Writes `text` cut to `width - 1` characters at row `y`; ignores writes outside the window."""

        try:
            screen.addstr(y, 0, text[:width - 1], attr)
        except curses.error:
            pass
