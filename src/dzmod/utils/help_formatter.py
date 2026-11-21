import argparse
import dataclasses
import re
from typing import ClassVar


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Keeps descriptions unwrapped and replaces the argparse color theme with the Karnes palette: headings in
    ACCENT, program, commands and options in LIGHT, placeholders in MUTED. Overrides the internal `_theme` and
    `_decolor` of argparse, which are properties since Python 3.15 and plain attributes before."""

    ACCENT = "\033[38;2;178;16;242m"
    LIGHT = "\033[38;2;236;232;244m"
    MUTED = "\033[38;2;138;132;150m"
    BOLD = "\033[1m"
    ANSI: ClassVar[re.Pattern[str]] = re.compile(r"\033\[[0-9;]*m")

    @property
    def _theme(self):
        """Returns the theme argparse picked; for the colored one a copy with the palette swapped in."""
        theme = self._inherited("_theme")
        if not theme.reset:
            return theme

        accent, light = self.BOLD + self.ACCENT, self.BOLD + self.LIGHT
        return dataclasses.replace(
            theme, usage=accent, heading=accent, prog=light, prog_extra=self.LIGHT,
            summary_long_option=self.LIGHT, summary_short_option=self.LIGHT, summary_action=self.LIGHT,
            summary_label=self.MUTED, long_option=light, short_option=light, action=light, label=self.MUTED,
        )

    @_theme.setter
    def _theme(self, value) -> None:
        self.__dict__["_inherited_theme"] = value

    @property
    def _decolor(self):
        """Returns the decolor function argparse picked; for the colored theme a regex that also strips 24-bit
        codes, so column widths are measured without them."""
        if not self._theme.reset:
            return self._inherited("_decolor")
        return lambda text: self.ANSI.sub("", text)

    @_decolor.setter
    def _decolor(self, value) -> None:
        self.__dict__["_inherited_decolor"] = value

    def _inherited(self, name: str):
        """Reads the property of the argparse base class (Python 3.15+) or, if it has none, the value argparse
        assigned through the setter (Python 3.14)."""
        try:
            return getattr(super(), name)
        except AttributeError:
            return self.__dict__[f"_inherited{name}"]
