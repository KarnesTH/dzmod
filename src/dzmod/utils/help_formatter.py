import argparse
import dataclasses
import re
from typing import ClassVar


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Keeps descriptions unwrapped and replaces the argparse color theme with the Karnes palette: headings in
    ACCENT, program, commands and options in LIGHT, placeholders in MUTED. Overrides the internal `_set_color` of
    Python 3.14 argparse."""

    ACCENT = "\033[38;2;178;16;242m"
    LIGHT = "\033[38;2;236;232;244m"
    MUTED = "\033[38;2;138;132;150m"
    BOLD = "\033[1m"
    ANSI: ClassVar[re.Pattern[str]] = re.compile(r"\033\[[0-9;]*m")

    def _set_color(self, color: bool) -> None:
        """Lets argparse pick the colored or plain theme; for the colored one swaps in the palette and replaces
        `_decolor` with a regex that also strips 24-bit codes, so column widths are measured without them."""

        super()._set_color(color)
        if not self._theme.reset:
            return

        accent, light = self.BOLD + self.ACCENT, self.BOLD + self.LIGHT
        self._theme = dataclasses.replace(
            self._theme, usage=accent, heading=accent, prog=light, prog_extra=self.LIGHT,
            summary_long_option=self.LIGHT, summary_short_option=self.LIGHT, summary_action=self.LIGHT,
            summary_label=self.MUTED, long_option=light, short_option=light, action=light, label=self.MUTED,
        )
        self._decolor = lambda text: self.ANSI.sub("", text)
