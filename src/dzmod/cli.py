import argparse
import os
import sys
from pathlib import Path
from urllib.error import URLError

from dzmod.messages import Messages
from dzmod.mod_state import ModState
from dzmod.mod_updater import ModUpdater
from dzmod.steam_cmd import SteamCmd
from dzmod.workshop_api import WorkshopAPI


class CLI:
    """Parses the arguments and runs the `check`, `update` and `install` subcommands."""

    def __init__(self) -> None:
        self.messages = Messages()
        self.args = self._parser().parse_args()
        self.updater = ModUpdater(
            server_dir=Path(self.args.server_dir).resolve(),
            steam_dir=Path(self.args.steam_dir).expanduser().resolve(),
            api=WorkshopAPI(),
        )

    def run(self) -> int:
        """Collects the mod states and dispatches to the selected subcommand."""

        if not self.updater.mod_ids():
            print(self.messages.get("no_mods", path=self.updater.server_dir))
            return 0

        try:
            states = self.updater.check()
        except (URLError, OSError, ValueError) as err:
            print(self.messages.get("api_error", error=err), file=sys.stderr)
            return 2

        self._print_states(states)
        outdated = [state for state in states if state.outdated]

        if not outdated:
            print(self.messages.get("all_current"))
            return 0

        print(self.messages.get("updates_found", count=len(outdated)))

        if self.args.command == "update":
            return self._update(outdated)
        return 0

    def _update(self, outdated: list[ModState]) -> int:
        """Downloads the outdated mods, verifies them via the ACF and copies the current ones into the server
        directory."""

        login = self.args.login or os.environ.get("DZMOD_STEAM_LOGIN")
        if not login:
            print(self.messages.get("login_missing"))
            return 2

        print(self.messages.get("downloading", count=len(outdated)))
        code = SteamCmd(self.args.steamcmd, login).download([state.mod_id for state in outdated])
        if code != 0:
            print(self.messages.get("steamcmd_failed", code=code), file=sys.stderr)

        done, failed = self.updater.downloaded(outdated)

        for state in done:
            self.updater.install(state.mod_id)
            print(self.messages.get("installed", mod_id=state.mod_id, title=state.title))

        for state in failed:
            print(self.messages.get("download_failed", mod_id=state.mod_id, title=state.title), file=sys.stderr)

        return 1 if failed else 0

    def _print_states(self, states: list[ModState]) -> None:
        """Prints one line per mod: ID, status and title."""

        for state in states:
            if not state.available:
                status = self.messages.get("unavailable")
            elif state.outdated:
                status = self.messages.get("outdated")
            else:
                status = self.messages.get("up_to_date")
            print(f"{state.mod_id:<12} {status:<30} {state.title}")

    @staticmethod
    def _parser() -> argparse.ArgumentParser:
        """Builds the parser with the global path options and the `check` / `update` / `install` subcommands."""

        parser = argparse.ArgumentParser(prog="dzmod")
        parser.add_argument("--server_dir", default=".", help="DayZ server directory")
        parser.add_argument("--steam-dir", default="~/.steam/steam", help="Steam/SteamCMD root")

        subparsers = parser.add_subparsers(dest="command", required=False)
        subparsers.add_parser("check", help="list mods and their update state")

        update = subparsers.add_parser("update", help="download outdated mods and copy them into the server directory")
        update.add_argument("--login", help="Steam account that owns DayZ")
        update.add_argument("--steamcmd", default="steamcmd", help="SteamCMD binary")

        install = subparsers.add_parser("install", help="install mods from a list of mods")
        install.add_argument("--login", help="Steam account that owns DayZ")
        install.add_argument("--steamcmd", default="steamcmd", help="SteamCMD binary")
        install.add_argument("--mod-list", help="list of mods to install")
        install.add_argument("--mod-id", help="mod id to install")

        return parser


def main() -> None:
    sys.exit(CLI().run())
