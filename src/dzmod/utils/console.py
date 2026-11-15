import os
import sys


class Console:
    """Prints structured reports: section headers, mod lines with status symbol, labelled detail lines and warnings.
    Colors are ANSI codes and are only used when stdout is a terminal and NO_COLOR is not set."""

    WIDTH = 64
    LABEL_WIDTH = 10
    GREEN, RED, YELLOW, BOLD, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[0m"

    def __init__(self) -> None:
        self.colors = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

    def section(self, title: str) -> None:
        """Prints an empty line and a bold header line `━━ title ━━…` filled to WIDTH."""

        line = f"━━ {title} " + "━" * max(self.WIDTH - len(title) - 4, 3)
        print()
        print(self._color(line, self.BOLD))
        print()

    def mod(self, title: str, mod_id: str, ok: bool) -> None:
        """Prints `✔ title  (id)` with a green symbol or `✘ title  (id)` with a red one; without a title the ID is
        shown instead."""

        symbol = self._color("✔", self.GREEN) if ok else self._color("✘", self.RED)
        print(f"{symbol} {title or mod_id}  ({mod_id})")

    def detail(self, label: str, value: str) -> None:
        """Prints an indented line with the label padded to LABEL_WIDTH."""

        print(f"    {label:<{self.LABEL_WIDTH}}{value}")

    def warning(self, text: str) -> None:
        """Prints an indented line with a yellow `⚠` in the label column."""

        print(f"    {self._color('⚠', self.YELLOW):<{self._pad('⚠')}}{text}")

    def blank(self) -> None:
        """Prints an empty line."""

        print()

    def highlight(self, text: str) -> None:
        """Prints an indented bold line."""

        print(f"  {self._color(text, self.BOLD)}")

    def _pad(self, symbol: str) -> int:
        """Returns the padding width for `symbol` so colored and plain output align to LABEL_WIDTH."""

        return self.LABEL_WIDTH + (len(self._color(symbol, self.YELLOW)) - len(symbol))

    def _color(self, text: str, code: str) -> str:
        """Wraps `text` in the ANSI `code` if colors are enabled."""

        return f"{code}{text}{self.RESET}" if self.colors else text
