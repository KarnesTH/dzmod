import argparse
import os
import sys

from dzmod.utils.banner import Banner


class BannerParser(argparse.ArgumentParser):
    """ArgumentParser that puts the banner above the help text. Subparsers inherit the class, so `-h` of every
    subcommand shows it too; error usage lines stay without banner."""

    def format_help(self) -> str:
        """Returns the banner, an empty line and the regular help text."""

        return f"{self.banner()}\n\n{super().format_help()}"

    @staticmethod
    def banner() -> str:
        """Renders the banner with colors if stdout is a terminal and NO_COLOR is not set."""

        return Banner(sys.stdout.isatty() and not os.environ.get("NO_COLOR")).render()
