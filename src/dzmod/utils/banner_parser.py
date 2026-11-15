import argparse
import os
import sys

from dzmod.utils.banner import Banner
from dzmod.utils.help_formatter import HelpFormatter


class BannerParser(argparse.ArgumentParser):
    """ArgumentParser that puts the banner above the help text and uses HelpFormatter. Subparsers inherit the class,
    so `-h` of every subcommand shows both too; error usage lines stay without banner."""

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("formatter_class", HelpFormatter)
        super().__init__(*args, **kwargs)

    def format_help(self) -> str:
        """Returns the banner, an empty line and the regular help text."""

        return f"{self.banner().render()}\n\n{super().format_help()}"

    @staticmethod
    def banner() -> Banner:
        """Creates the banner with colors if stdout is a terminal and NO_COLOR is not set."""

        return Banner(sys.stdout.isatty() and not os.environ.get("NO_COLOR"))
