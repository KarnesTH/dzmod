import argparse
import sys
import termios
import tty
from importlib.metadata import version
from pathlib import Path

from dzmod.core.collection_file import CollectionFile
from dzmod.utils.errors import DzmodError
from dzmod.utils.env_file import EnvFile
from dzmod.utils.messages import Messages
from dzmod.core.mod_list import ModList
from dzmod.core.mod_picker import ModPicker
from dzmod.models.mod_state import ModState
from dzmod.core.mod_updater import ModUpdater
from dzmod.core.steam_cmd import SteamCmd
from dzmod.core.workshop_api import WorkshopAPI
from dzmod.models.workshop_item import WorkshopItem


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

        if self.args.command == "install":
            self._install()
            return

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
        """Asks for the Steam login (required) and the API key (optional, masked with `*`) and writes them to the
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

    def _install(self) -> None:
        """Collects the mods from `--mod-id`, `--mod-list` or `--collection` and prints them."""

        if self.args.mod_list:
            mods = self._mods_from_list()
        elif self.args.collection:
            mods = self._mods_from_collection()
        else:
            mods = self._mods_from_ids()

        if not mods:
            print(self.messages.get("nothing_to_install"))
            return

        print(self.messages.get("install_list", count=len(mods)))
        for item in mods:
            print(f"  {item.mod_id:<12} {item.title}")

    def _mods_from_ids(self) -> list[WorkshopItem]:
        """Validates the IDs, looks them up via the Steam API and warns about IDs the Workshop does not return."""

        mod_ids = list(dict.fromkeys(self.args.mod_id))
        for mod_id in mod_ids:
            if not (mod_id.isascii() and mod_id.isdigit()):
                raise DzmodError("invalid_id", mod_id=mod_id)

        items = self.updater.api.fetch(mod_ids)
        for mod_id in mod_ids:
            if mod_id not in items:
                print(self.messages.get("unavailable_id", mod_id=mod_id), file=sys.stderr)
        return [items[mod_id] for mod_id in mod_ids if mod_id in items]

    def _mods_from_list(self) -> list[WorkshopItem]:
        """Loads the mod list, lets the user pick mods and optionally adds them to the collection file."""

        items = self._load_mod_list()
        selected = ModPicker(items, self.messages, self.args.verbose).run()
        if not selected:
            print(self.messages.get("selection_cancelled"))
            return []

        answer = input(self.messages.get("ask_collection")).strip().lower()
        if answer in self.messages.get("yes_answers").split(","):
            self._save_collection(selected, items)
        return selected

    def _save_collection(self, selected: list[WorkshopItem], items: list[WorkshopItem]) -> None:
        """Appends the titles to the collection file, creating it with a name and description if it does not exist.
        Warns about titles that occur more than once in the mod list."""

        collection = CollectionFile(self.updater.server_dir)
        titles = [item.title for item in selected]

        if collection.exists:
            added = collection.append(titles)
            print(self.messages.get("collection_extended", path=collection.path, count=len(added)))
        else:
            name = ""
            while not name:
                name = input(self.messages.get("ask_collection_name")).strip()
            description = input(self.messages.get("ask_collection_description")).strip()
            collection.create(name, description, titles)
            print(self.messages.get("collection_created", path=collection.path, count=len(titles)))

        counts: dict[str, int] = {}
        for item in items:
            counts[item.title.casefold()] = counts.get(item.title.casefold(), 0) + 1
        for title in titles:
            if counts.get(title.casefold(), 0) > 1:
                print(self.messages.get("title_not_unique", title=title), file=sys.stderr)

    def _mods_from_collection(self) -> list[WorkshopItem]:
        """Reads the collection file of the server and resolves its titles via the mod list. Titles without or with
        several matches are reported and skipped."""

        collection = CollectionFile(self.updater.server_dir)
        if not collection.exists:
            raise DzmodError("collection_missing", path=collection.path)

        collection.read()
        if not collection.mods:
            raise DzmodError("collection_empty", path=collection.path)

        print(self.messages.get("collection_header", name=collection.info.get("name", collection.path.name),
                                count=len(collection.mods)))

        resolved, missing, ambiguous = collection.resolve(self._load_mod_list())
        for title in missing:
            print(self.messages.get("mod_not_found", title=title), file=sys.stderr)
        for title, mod_ids in ambiguous.items():
            print(self.messages.get("mod_ambiguous", title=title, ids=", ".join(mod_ids)), file=sys.stderr)
        return resolved

    def _load_mod_list(self) -> list[WorkshopItem]:
        """Loads the cached mod list and shows the progress while it is refreshed from Steam."""

        mod_list = ModList(self.updater.api, self.env.get("DZMOD_STEAM_API_KEY"))
        refreshing = mod_list.outdated and mod_list.api_key

        if refreshing:
            print(self.messages.get("mod_list_loading"))

        try:
            items = mod_list.load(self._print_progress if refreshing else None)
        except DzmodError as err:
            if err.key == "api_key_missing":
                raise DzmodError("api_key_missing", path=self.env.path) from err
            raise
        finally:
            if refreshing:
                print()

        if not items:
            raise DzmodError("mod_list_empty")
        return items

    def _print_progress(self, loaded: int, total: int) -> None:
        """Overwrites the current terminal line with the loading progress."""

        print("\r" + self.messages.get("mod_list_progress", loaded=loaded, total=total), end="", flush=True)

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
                    next_char = sys.stdin.read(1)
                    if next_char == "[":
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
        parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {version('dzmod')}")
        parser.add_argument("--server-dir", default=".", help="DayZ server directory")
        parser.add_argument("--steam-dir", default="~/.steam/steam", help="Steam/SteamCMD root")

        subparsers = parser.add_subparsers(dest="command", required=False)
        subparsers.add_parser("check", help="list mods and their update state")

        update = subparsers.add_parser("update", help="download outdated mods and copy them into the server directory")
        update.add_argument("--login", help="Steam account that owns DayZ")
        update.add_argument("--steamcmd", default="steamcmd", help="SteamCMD binary")

        install = subparsers.add_parser("install", help="install mods by ID, from the Workshop list or the collection")
        install.add_argument("--login", help="Steam account that owns DayZ")
        install.add_argument("--steamcmd", default="steamcmd", help="SteamCMD binary")
        install.add_argument("-v", "--verbose", action="store_true", help="show more columns in the mod list")
        source = install.add_mutually_exclusive_group(required=True)
        source.add_argument("--mod-id", nargs="+", metavar="ID", help="one or more mod IDs")
        source.add_argument("--mod-list", action="store_true", help="pick mods from the Workshop list")
        source.add_argument("--collection", action="store_true",
                            help=f"use {CollectionFile.FILE_NAME} in the server directory")

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
