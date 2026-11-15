import os
import sys
from typing import ClassVar


class Console:
    """Prints all terminal output of dzmod in one layout: section headers, mod lines with status symbol, labelled
    detail lines, warnings, numbered options and prompts. Colors are 24-bit ANSI codes in the Karnes palette and are
    only used when the target stream is a terminal and NO_COLOR is not set."""

    WIDTH: ClassVar[int] = 64
    LABEL_WIDTH: ClassVar[int] = 10
    ACCENT: ClassVar[str] = "\033[38;2;178;16;242m"
    LIGHT: ClassVar[str] = "\033[38;2;236;232;244m"
    MUTED: ClassVar[str] = "\033[38;2;138;132;150m"
    RED: ClassVar[str] = "\033[38;2;242;68;90m"
    YELLOW: ClassVar[str] = "\033[38;2;242;193;78m"
    BOLD: ClassVar[str] = "\033[1m"
    RESET: ClassVar[str] = "\033[0m"
    STATES: ClassVar[dict[str, tuple[str, str]]] = {"ok": ("✔", ACCENT), "outdated": ("↻", YELLOW),
                                                    "missing": ("✘", RED)}

    def __init__(self) -> None:
        no_color = bool(os.environ.get("NO_COLOR"))
        self.tty = sys.stdout.isatty()
        self.colors = self.tty and not no_color
        self.error_colors = sys.stderr.isatty() and not no_color
        self.open_line = False
        self.progress_line = False

    def section(self, title: str, info: str = "") -> None:
        """Prints an empty line, the header `━━ title ━━…` in bold ACCENT filled to WIDTH with `info` muted behind it,
        and another empty line."""

        line = f"━━ {title} " + "━" * max(self.WIDTH - len(title) - 4, 3)
        tail = f"  {self.muted(info)}" if info else ""
        self.close_line()
        print()
        print(self._color(line, self.BOLD + self.ACCENT) + tail)
        print()

    def mod(self, title: str, mod_id: str, ok: bool) -> None:
        """Prints `✔ title  (id)` with an ACCENT symbol or `✘ title  (id)` with a red one; without a title the ID is
        shown instead."""

        self.state(title, mod_id, "ok" if ok else "missing")

    def state(self, title: str, mod_id: str, state: str, label: str = "") -> None:
        """Prints a mod line with the symbol of `state` (ok, outdated, missing), the title with muted ID and an
        optional muted label."""

        self.close_line()
        symbol, color = self.STATES[state]
        suffix = f"  {self.muted(label)}" if label else ""
        print(f"{self._color(symbol, color)} {self._name(title, mod_id)}{suffix}")

    def item(self, title: str, mod_id: str) -> None:
        """Prints `• title  (id)` with an ACCENT bullet, indented by two."""

        print(f"  {self._color('•', self.ACCENT)} {self._name(title, mod_id)}")

    def detail(self, label: str, value: str) -> None:
        """Prints an indented line with the muted label padded to LABEL_WIDTH."""

        print(f"    {self.muted(f'{label:<{self.LABEL_WIDTH}}')}{value}")

    def warning(self, text: str) -> None:
        """Prints an indented line with a yellow `⚠` in the label column."""

        print(f"    {self._color(f'{"⚠":<{self.LABEL_WIDTH}}', self.YELLOW)}{text}")

    def success(self, text: str) -> None:
        """Prints `✔ text` with an ACCENT symbol."""

        self.close_line()
        print(f"{self._color('✔', self.ACCENT)} {text}")

    def text(self, text: str) -> None:
        """Prints every line of `text` indented by two; lines that start without whitespace are bold, indented lines
        are muted."""

        for line in text.splitlines():
            if not line.strip():
                print()
            elif line[0].isspace():
                print(f"  {self.muted(line)}")
            else:
                print(f"  {self._color(line, self.BOLD)}")

    def note(self, text: str) -> None:
        """Prints `text` muted and indented by two."""

        self.close_line()
        print(f"  {self.muted(text)}")

    def option(self, number: int, text: str) -> None:
        """Prints a numbered option `  1  text` with the number in bold ACCENT."""

        print(f"  {self._color(f'{number:>2}', self.BOLD + self.ACCENT)}  {text}")

    def prompt(self, text: str) -> str:
        """Returns the prompt `  › text` with an ACCENT arrow, for use with input()."""

        return f"  {self._color('›', self.BOLD + self.ACCENT)} {text}"

    def highlight(self, text: str) -> None:
        """Prints an indented bold line."""

        print(f"  {self._color(text, self.BOLD)}")

    def blank(self) -> None:
        """Prints an empty line."""

        print()

    def raw(self, line: str) -> None:
        """Prints a line of an external program muted and indented by two."""

        self.close_line()
        print(f"  {self.muted(line)}")

    def partial(self, text: str) -> None:
        """Prints text of an external program without line break (e.g. a password prompt) and remembers the open
        line so the next regular output starts on a new one."""

        print(self.muted(text), end="", flush=True)
        self.open_line = True

    def close_line(self) -> None:
        """Ends a line left open by `partial`; a progress line is erased instead, so the next output replaces it."""

        if self.progress_line:
            print("\r\033[K", end="", flush=True)
            self.progress_line = False
        elif self.open_line:
            print()
        self.open_line = False

    def progress(self, text: str) -> None:
        """Overwrites the current line with `text` muted and indented by two; the line is erased by the next output.
        Does nothing if stdout is not a terminal."""

        if not self.tty:
            return
        self.close_line()
        print(f"  {self.muted(text)}", end="", flush=True)
        self.progress_line = True

    def error(self, text: str) -> None:
        """Prints an empty line and `✘ text` on stderr, the symbol red if stderr is a terminal."""

        self.close_line()
        print(file=sys.stderr)
        symbol = f"{self.RED}✘{self.RESET}" if self.error_colors else "✘"
        print(f"{symbol} {text}", file=sys.stderr)

    def muted(self, text: str) -> str:
        """Returns `text` in MUTED if colors are enabled."""

        return self._color(text, self.MUTED)

    def accent(self, text: str) -> str:
        """Returns `text` in bold ACCENT if colors are enabled."""

        return self._color(text, self.BOLD + self.ACCENT)

    def _name(self, title: str, mod_id: str) -> str:
        """Returns `title  (id)` with the ID muted, or only the ID if there is no title."""

        return f"{title}  {self.muted(f'({mod_id})')}" if title else mod_id

    def _color(self, text: str, code: str) -> str:
        """Wraps `text` in the ANSI `code` if colors are enabled."""

        return f"{code}{text}{self.RESET}" if self.colors else text
