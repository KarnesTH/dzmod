import argparse
import termios
import tty
import sys
from pathlib import Path
from importlib.metadata import version

from dzmod.errors import DzmodError
from dzmod.env_file import EnvFile
from dzmod.messages import Messages
from dzmod.mod_state import ModState
from dzmod.mod_updater import ModUpdater
from dzmod.steam_cmd import SteamCmd
from dzmod.workshop_api import WorkshopAPI


class CLI:
    """Parses the arguments and runs the `check`, `update` and `install` subcommands."""

    SERVER_BINARY = "DayZServer"

    def __init__(self, messages: Messages) -> None:
        self.messages = messages
        self.args = self._parser().parse_args()
        self.env = EnvFile()
        self.updater = ModUpdater(
            server_dir=Path(self.args.server_dir).resolve(),
            steam_dir=Path(self.args.steam_dir).expanduser().resolve(),
            api=WorkshopAPI(),
        )

    def run(self) -> None:
        """Runs the first-start setup if needed, verifies the server directory and dispatches to the subcommand.
        Raises DzmodError on any failure."""

        if not self.env.exists:
            self._setup()

        if not (self.updater.server_dir / self.SERVER_BINARY).is_file():
            raise DzmodError("not_a_server", path=self.updater.server_dir, binary=self.SERVER_BINARY)

        if not self.updater.mod_ids():
            print(self.messages.get("no_mods", path=self.updater.server_dir))
            return

        states = self.updater.check()
        self._print_states(states)
        outdated = [state for state in states if state.outdated]

        if not outdated:
            print(self.messages.get("all_current"))
            return

        print(self.messages.get("updates_found", count=len(outdated)))

        if self.args.command == "update":
            self._update(outdated)

    def _setup(self) -> None:
        """Asks for the Steam login (required) and the API key (optional, hidden input) and writes them to the
        env file. Raises DzmodError if stdin is not a terminal."""

        if not sys.stdin.isatty():
            raise DzmodError("config_missing", path=self.env.path)

        print(self.messages.get("setup_intro", path=self.env.path))

        login = ""
        while not login:
            login = input(self.messages.get("setup_login")).strip()
        api_key = self._masked_input(self.messages.get("setup_api_key")).strip()

        self.env.create({"DZMOD_STEAM_LOGIN": login, "DZMOD_STEAM_API_KEY": api_key})
        print(self.messages.get("setup_done", path=self.env.path))

    @staticmethod
    def _masked_input(prompt: str) -> str:
        """Reads a line in raw terminal mode and echoes `*` per printable character. Backspace removes the last
        character, Enter finishes, Ctrl+C raises KeyboardInterrupt and Ctrl+D on an empty line raises EOFError.
        Escape sequences (arrow keys etc.) are ignored. The terminal settings are restored afterwards."""

        fd = sys.stdin.fileno()
        settings = termios.tcgetattr(fd)
        chars: list[str] = []
        sys.stdout.write(prompt)
        sys.stdout.flush()

        try:
            tty.setraw(fd)
            while True:
                char = sys.stdin.read(1)
                if char in ("\r", "\n"):
                    break
                if char == "\x03":
                    raise KeyboardInterrupt
                if char == "\x04" and not chars:
                    raise EOFError
                if char in ("\x7f", "\x08"):
                    if chars:
                        chars.pop()
                        sys.stdout.write("\b \b")
                elif char == "\x1b":
                    if sys.stdin.read(1) == "[":
                        while not sys.stdin.read(1).isalpha():
                            pass
                elif char.isprintable():
                    chars.append(char)
                    sys.stdout.write("*")
                sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, settings)
            sys.stdout.write("\n")
            sys.stdout.flush()

        return "".join(chars)

    def _update(self, outdated: list[ModState]) -> None:
        """Downloads the outdated mods, verifies them via the ACF and copies the current ones into the server
        directory. Raises DzmodError if the login is missing or at least one download failed."""

        login = self.args.login or self.env.get("DZMOD_STEAM_LOGIN")
        if not login:
            raise DzmodError("login_missing", path=self.env.path)

        steam_cmd = SteamCmd(self.args.steamcmd, login)
        print(self.messages.get("downloading", count=len(outdated)))
        code = steam_cmd.download([state.mod_id for state in outdated])
        if code != 0:
            print(self.messages.get("steamcmd_failed", code=code), file=sys.stderr)

        done, failed = self.updater.downloaded(outdated)

        for state in done:
            self.updater.install(state.mod_id)
            print(self.messages.get("installed", mod_id=state.mod_id, title=state.title))

        for state in failed:
            print(self.messages.get("download_failed", mod_id=state.mod_id, title=state.title), file=sys.stderr)

        if failed:
            raise DzmodError("downloads_failed", count=len(failed))

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
        parser.add_argument("--server-dir", default=".", help="DayZ server directory")
        parser.add_argument("--steam-dir", default="~/.steam/steam", help="Steam/SteamCMD root")
        parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {version('dzmod')}")

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
    """Runs the CLI and turns DzmodError, file errors, Ctrl+C and Ctrl+D into a message on stderr and a non-zero
    exit."""

    messages = Messages()
    try:
        CLI(messages).run()
    except DzmodError as err:
        print(messages.get(err.key, **err.values), file=sys.stderr)
        sys.exit(1)
    except OSError as err:
        print(messages.get("file_error", path=err.filename or "", error=err.strerror or err), file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print(file=sys.stderr)
        sys.exit(130)
