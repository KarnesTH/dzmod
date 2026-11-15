import curses
import locale
from typing import ClassVar

from dzmod.models.workshop_item import WorkshopItem
from dzmod.utils.formatter import Formatter
from dzmod.utils.messages import Messages


class ModPicker:
    """Shows the mods in a curses list in the dzmod layout. Arrow keys/j/k move, PgUp/PgDn page, Home/End jump, Space
    toggles a mod, `a` toggles all visible mods, `/` filters by title or ID, Enter confirms and q cancels (Esc clears
    an active filter first). Mods in `installed` are shown with `✔` and cannot be selected."""

    KEYS_UP: ClassVar[tuple[int, ...]] = (curses.KEY_UP, ord("k"))
    KEYS_DOWN: ClassVar[tuple[int, ...]] = (curses.KEY_DOWN, ord("j"))
    KEYS_CONFIRM: ClassVar[tuple[int, ...]] = (curses.KEY_ENTER, 10, 13)
    KEYS_BACKSPACE: ClassVar[tuple[int, ...]] = (curses.KEY_BACKSPACE, 127, 8)
    KEY_ESC: ClassVar[int] = 27
    COLORS_256: ClassVar[dict[str, int]] = {"accent": 129, "light": 255, "muted": 245, "cursor": 236}
    CHROME_ROWS: ClassVar[int] = 7

    def __init__(self, items: list[WorkshopItem], messages: Messages, verbose: bool, title: str, info: str,
                 installed: set[str] | None = None) -> None:
        self.items = items
        self.messages = messages
        self.verbose = verbose
        self.title = title
        self.info = info
        self.installed = installed or set()
        self.format = Formatter(messages)
        self.selected: set[int] = set()
        self.visible = list(range(len(items)))
        self.query = ""
        self.searching = False
        self.cursor = 0
        self.top = 0
        self.pairs: dict[str, int] = {}
        self.title_width = max([len(messages.get("col_title")), *(len(item.title) for item in items)])

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
        """Sets up colors, draws the list and handles keys until Enter (True) or q (False)."""

        curses.curs_set(0)
        screen.keypad(True)
        curses.set_escdelay(25)
        self._init_colors()

        while True:
            height, width = screen.getmaxyx()
            rows = max(height - self.CHROME_ROWS, 1)
            self._scroll(rows)
            self._draw(screen, rows, width)

            key = screen.get_wch()
            code = ord(key) if isinstance(key, str) else key
            if self.searching:
                self._search_key(key, code)
                continue

            if code in self.KEYS_UP:
                self.cursor -= 1
            elif code in self.KEYS_DOWN:
                self.cursor += 1
            elif code == curses.KEY_PPAGE:
                self.cursor -= rows
            elif code == curses.KEY_NPAGE:
                self.cursor += rows
            elif code == curses.KEY_HOME:
                self.cursor = 0
            elif code == curses.KEY_END:
                self.cursor = len(self.visible) - 1
            elif key == " ":
                self._toggle()
                self.cursor += 1
            elif key == "a":
                self._toggle_all()
            elif key == "/":
                self.searching = True
            elif code in self.KEYS_CONFIRM:
                return True
            elif code == self.KEY_ESC and self.query:
                self._filter("")
            elif key == "q" or code == self.KEY_ESC:
                return False

    def _search_key(self, key: str | int, code: int) -> None:
        """Handles a key while the filter line is open: characters extend the query, Backspace shortens it, Enter
        keeps the filter and closes the line, Esc clears the filter and closes the line."""

        if code in self.KEYS_CONFIRM:
            self.searching = False
        elif code == self.KEY_ESC:
            self.searching = False
            self._filter("")
        elif code in self.KEYS_BACKSPACE:
            self._filter(self.query[:-1])
        elif isinstance(key, str) and key.isprintable():
            self._filter(self.query + key)

    def _filter(self, query: str) -> None:
        """Shows only the mods whose title or ID contains `query` (case-insensitive) and moves the cursor to the top."""

        self.query = query
        needle = query.casefold()
        self.visible = [i for i, item in enumerate(self.items)
                        if needle in item.title.casefold() or needle in item.mod_id]
        self.cursor = self.top = 0

    def _toggle(self) -> None:
        """Selects or deselects the mod under the cursor unless it is installed."""

        if self.visible and self.items[self.visible[self.cursor]].mod_id not in self.installed:
            self.selected ^= {self.visible[self.cursor]}

    def _toggle_all(self) -> None:
        """Selects all visible selectable mods, or deselects them if all are selected already."""

        selectable = {i for i in self.visible if self.items[i].mod_id not in self.installed}
        self.selected = self.selected - selectable if selectable <= self.selected else self.selected | selectable

    def _scroll(self, rows: int) -> None:
        """Keeps the cursor inside the visible list and moves the window so the cursor stays on screen."""

        self.cursor = min(max(self.cursor, 0), max(len(self.visible) - 1, 0))
        if self.cursor < self.top:
            self.top = self.cursor
        elif self.cursor >= self.top + rows:
            self.top = self.cursor - rows + 1

    def _init_colors(self) -> None:
        """Creates the color pairs: Karnes colors from the 256-color palette, the basic colors on 8-color terminals
        and no colors otherwise (the cursor row is then shown reversed). The terminal background is kept."""

        if not curses.has_colors():
            return
        curses.start_color()
        curses.use_default_colors()
        if curses.COLORS >= 256:
            colors = self.COLORS_256
        else:
            colors = {"accent": curses.COLOR_MAGENTA, "light": curses.COLOR_WHITE, "muted": -1, "cursor": -1}

        for number, (name, background) in enumerate(
                [(name, bg) for bg in ("", "cursor") for name in ("accent", "light", "muted")], start=1):
            curses.init_pair(number, colors[name], colors[background] if background else -1)
            self.pairs[f"{name}:{background}"] = number

    def _attr(self, name: str, cursor: bool = False, bold: bool = False) -> int:
        """Returns the curses attribute for color `name`, on the cursor background if `cursor` is set."""

        attr = curses.A_BOLD if bold else curses.A_NORMAL
        if not self.pairs:
            return attr | (curses.A_REVERSE if cursor else 0) | (curses.A_DIM if name == "muted" else 0)
        if cursor and curses.COLORS < 256:
            attr |= curses.A_REVERSE
        return attr | curses.color_pair(self.pairs[f"{name}:{'cursor' if cursor else ''}"])

    def _draw(self, screen: curses.window, rows: int, width: int) -> None:
        """Draws header line, column header, visible rows, status line and key help (or the filter line)."""

        get = self.messages.get
        screen.erase()

        info = get("picker_matches", shown=len(self.visible), total=len(self.items)) if self.query else self.info
        line = f"━━ {self.title} " + "━" * max(60 - len(self.title), 3)
        x = self._put(screen, 0, 0, line, width, self._attr("accent", bold=True))
        self._put(screen, 0, x, f"  {info}", width, self._attr("muted"))

        header = f"    {get('col_id'):<12}{get('col_title'):<{self.title_width + 2}}{get('col_size'):>9}  " \
                 f"{get('col_updated'):<12}"
        if self.verbose:
            header += f"{get('col_subscriptions'):>11}  {get('col_created'):<12}{get('col_tags')}"
        self._put(screen, 2, 0, header, width, self._attr("muted"))

        if not self.visible:
            self._put(screen, 3, 4, get("picker_empty"), width, self._attr("muted"))
        for line_number, position in enumerate(range(self.top, min(self.top + rows, len(self.visible))), start=3):
            self._draw_row(screen, line_number, position, width)

        status_y = rows + 4
        size = self.format.size(sum(self.items[i].file_size for i in self.selected))
        x = self._put(screen, status_y, 0, str(len(self.selected)), width, self._attr("accent", bold=True))
        x = self._put(screen, status_y, x, get("picker_selected"), width, self._attr("muted"))
        x = self._put(screen, status_y, x, size, width, self._attr("light", bold=True))
        position = get("picker_position", position=min(self.cursor + 1, len(self.visible)), total=len(self.visible))
        self._put(screen, status_y, x, f"   ·   {position}", width, self._attr("muted"))

        if self.searching:
            x = self._put(screen, status_y + 1, 0, "/ ", width, self._attr("accent", bold=True))
            x = self._put(screen, status_y + 1, x, self.query, width, self._attr("light"))
            x = self._put(screen, status_y + 1, x, "▏", width, self._attr("accent"))
            self._help(screen, status_y + 1, x + 6, get("picker_search_help"), width)
        else:
            self._help(screen, status_y + 1, 0, get("picker_help"), width)
        screen.refresh()

    def _draw_row(self, screen: curses.window, y: int, position: int, width: int) -> None:
        """Draws one mod row: cursor bar, mark (`●` selected, `○` open, `✔` installed), muted ID, title (bold when
        selected or under the cursor), size and date, plus the verbose columns."""

        index = self.visible[position]
        item = self.items[index]
        cursor = position == self.cursor
        installed = item.mod_id in self.installed
        chosen = index in self.selected

        if cursor and self.pairs:
            self._put(screen, y, 0, " " * (width - 1), width, self._attr("light", cursor))
        mark = "✔" if installed else "●" if chosen else "○"
        x = self._put(screen, y, 0, "▌" if cursor else " ", width, self._attr("accent", cursor))
        x = self._put(screen, y, x, f"{mark}  ", width, self._attr("accent" if installed or chosen else "muted",
                                                                   cursor, bold=chosen))
        x = self._put(screen, y, x, f"{item.mod_id:<12}", width, self._attr("muted", cursor))
        title_color = "muted" if installed else "light"
        x = self._put(screen, y, x, f"{item.title:<{self.title_width + 2}}", width,
                      self._attr(title_color, cursor, bold=(cursor or chosen) and not installed))
        tail = f"{self.format.size(item.file_size):>9}  {self.format.date(item.time_updated):<12}"
        if self.verbose:
            tail += f"{item.subscriptions:>11,}".replace(",", ".") + \
                    f"  {self.format.date(item.time_created):<12}{', '.join(item.tags)}"
        if installed:
            tail += f"  {self.messages.get('picker_installed')}"
        self._put(screen, y, x, tail, width, self._attr("muted", cursor))

    def _help(self, screen: curses.window, y: int, x: int, text: str, width: int) -> None:
        """Draws `key=label;key=label` pairs with bold keys and muted labels."""

        for pair in text.split(";"):
            key, _, label = pair.partition("=")
            x = self._put(screen, y, x, key, width, self._attr("light", bold=True))
            x = self._put(screen, y, x, f" {label}   ", width, self._attr("muted"))

    @staticmethod
    def _put(screen: curses.window, y: int, x: int, text: str, width: int, attr: int) -> int:
        """Writes `text` at (y, x) cut to the window width and returns the column after it; writes outside the window
        are ignored."""

        text = text[:max(width - 1 - x, 0)]
        if text:
            try:
                screen.addstr(y, x, text, attr)
            except curses.error:
                pass
        return x + len(text)
