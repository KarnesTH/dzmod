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
from dzmod.core.mod_installer import ModInstaller
from dzmod.core.mod_list import ModList
from dzmod.core.mod_picker import ModPicker
from dzmod.core.mod_table import ModTable
from dzmod.models.install_result import InstallResult
from dzmod.models.mod_state import ModState
from dzmod.core.mod_updater import ModUpdater
from dzmod.core.server_config import ServerConfig
from dzmod.core.steam_cmd import SteamCmd
from dzmod.core.steam_cmd_installer import SteamCmdInstaller
from dzmod.core.workshop_api import WorkshopAPI
from dzmod.models.workshop_item import WorkshopItem


class CLI:
    """Parses the arguments and runs the subcommands. `setup` and `mods` only configure the CLI and work in any
    directory; `check`, `update` and `install` need a DayZ server directory."""

    SERVER_BINARY = "DayZServer"
    STEAM_ID_PREFIX = "7656119"

    def __init__(self, messages: Messages) -> None:
        self.messages = messages
        self.args = self._parser().parse_args()
        self.env = EnvFile()
        self.updater = self._create_updater(SteamCmd.locate(getattr(self.args, "steamcmd", None)))

    def _create_updater(self, executable: str | None) -> ModUpdater:
        """Creates the ModUpdater with `--steam-dir` if given, otherwise with the data directory of `executable`."""

        steam_dir = Path(self.args.steam_dir).expanduser() if self.args.steam_dir else SteamCmd.steam_dir(executable)
        return ModUpdater(server_dir=Path(self.args.server_dir).resolve(), steam_dir=steam_dir.resolve(),
                          api=WorkshopAPI())

    def run(self) -> None:
        """Runs the first-start setup if needed and dispatches to the subcommand; without a subcommand `check` runs.
        Raises DzmodError on any failure."""

        if self.args.command == "setup":
            self._setup()
            return

        if not self.env.exists:
            self._setup()

        if self.args.command == "mods":
            self._show_mods()
            return

        if not (self.updater.server_dir / self.SERVER_BINARY).is_file():
            raise DzmodError("not_a_server", path=self.updater.server_dir, binary=self.SERVER_BINARY)

        if self.args.command == "install":
            self._install()
        else:
            self._check()

    def _check(self) -> None:
        """Prints the update state of all mods in the server directory and runs the update for `update`."""

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
        """Asks for the Steam login (required), the SteamID64 (optional, 17 digits starting with STEAM_ID_PREFIX) and
        the API key (optional, masked with `*`); an empty input keeps the value already stored in the env file. Writes
        the values, then looks for SteamCMD and offers to install it. Raises DzmodError if stdin is not a terminal."""

        if not sys.stdin.isatty():
            raise DzmodError("setup_needs_terminal" if self.env.exists else "config_missing", path=self.env.path)

        current = dict(self.env.values)
        print(self.messages.get("setup_intro", path=self.env.path))
        if current:
            print(self.messages.get("setup_keep"))

        login = ""
        while not login:
            login = input(self._prompt("setup_login", current.get("DZMOD_STEAM_LOGIN"))).strip()
            login = login or current.get("DZMOD_STEAM_LOGIN", "")

        while True:
            steam_id = input(self._prompt("setup_steam_id", current.get("DZMOD_STEAM_ID"))).strip()
            if not steam_id:
                steam_id = current.get("DZMOD_STEAM_ID", "")
                break
            if steam_id.isdigit() and len(steam_id) == 17 and steam_id.startswith(self.STEAM_ID_PREFIX):
                break
            print(self.messages.get("steam_id_invalid"))

        stored_key = current.get("DZMOD_STEAM_API_KEY", "")
        api_key = self._masked_input(self._prompt("setup_api_key", "*" * 8 if stored_key else None)).strip()
        api_key = api_key or stored_key

        self.env.create({"DZMOD_STEAM_LOGIN": login, "DZMOD_STEAM_ID": steam_id, "DZMOD_STEAM_API_KEY": api_key})
        print(self.messages.get("setup_done", path=self.env.path))

        executable = SteamCmd.locate()
        if executable:
            print(self.messages.get("steamcmd_found", path=executable))
        else:
            self._install_steam_cmd()

    def _prompt(self, key: str, current: str | None) -> str:
        """Returns the prompt text for `key`, with the current value in brackets before the colon if there is one."""

        text = self.messages.get(key)
        return f"{text.rstrip().rstrip(':')} [{current}]: " if current else text

    def _steam_cmd(self, login: str) -> SteamCmd:
        """Locates SteamCMD (`--steamcmd`, PATH, `~/Steam/steamcmd.sh`) and offers to install it if missing. After
        an installation the ModUpdater is recreated with the new data directory. Raises DzmodError if SteamCMD is
        neither found nor installed."""

        executable = SteamCmd.locate(self.args.steamcmd)
        if executable is None and not self.args.steamcmd:
            executable = self._install_steam_cmd()
            if executable:
                self.updater = self._create_updater(executable)
        if executable is None:
            raise DzmodError("steamcmd_missing")
        return SteamCmd(executable, login)

    def _install_steam_cmd(self) -> str | None:
        """Asks whether SteamCMD should be installed into `~/Steam`, installs it and runs it once. Prints the
        command for the 32-bit libraries if that first run fails. Returns the script path, or None if declined or no
        terminal is attached."""

        installer = SteamCmdInstaller()
        if not sys.stdin.isatty():
            return None

        answer = input(self.messages.get("steamcmd_ask_install", path=installer.directory)).strip().lower()
        if answer not in self.messages.get("yes_answers").split(","):
            return None

        print(self.messages.get("steamcmd_installing", path=installer.directory))
        executable = installer.install()
        print(self.messages.get("steamcmd_first_run"))
        if installer.first_run() != 0:
            raise DzmodError("steamcmd_libs_missing", command=installer.lib_command())

        print(self.messages.get("steamcmd_installed", path=executable))
        return executable

    def _install(self) -> None:
        """Collects the mods from `--mod-id`, `--collection` or, by default, the selection from the mod list, skips
        mods already in the server, downloads the rest in one SteamCMD run, installs them with keys and CE files and
        prints the `-mod=` parameter. Raises DzmodError if the login is missing or a download failed."""

        if self.args.mod_id:
            mods = self._mods_from_ids()
        elif self.args.collection:
            mods = self._mods_from_collection()
        else:
            mods = self._mods_from_list()

        if not mods:
            print(self.messages.get("nothing_to_install"))
            return

        installed = set(self.updater.mod_ids())
        for item in mods:
            if item.mod_id in installed:
                print(self.messages.get("already_installed", mod_id=item.mod_id, title=item.title))
        pending = [item for item in mods if item.mod_id not in installed]

        failed: list[ModState] = []
        if pending:
            login = self.args.login or self.env.get("DZMOD_STEAM_LOGIN")
            if not login:
                raise DzmodError("login_missing", path=self.env.path)

            steam_cmd = self._steam_cmd(login)
            states = [ModState(mod_id=item.mod_id, title=item.title, local_updated=0,
                               remote_updated=item.time_updated) for item in pending]

            print(self.messages.get("downloading", count=len(states)))
            code = steam_cmd.download([state.mod_id for state in states])
            if code != 0:
                print(self.messages.get("steamcmd_failed", code=code), file=sys.stderr)

            done, failed = self.updater.downloaded(states)
            installer = ModInstaller(self.updater, ServerConfig(self.updater.server_dir), self._choose_variant)
            if done and not installer.has_mission:
                print(self.messages.get("mission_missing", path=installer.mission_dir or ServerConfig.FILE_NAME),
                      file=sys.stderr)

            for state in done:
                self._print_install(installer.install(state.mod_id, state.title))
            for state in failed:
                print(self.messages.get("download_failed", mod_id=state.mod_id, title=state.title), file=sys.stderr)

        installer = ModInstaller(self.updater, ServerConfig(self.updater.server_dir), self._choose_variant)
        if self.updater.mod_ids():
            print(self.messages.get("launch_parameter", parameter=installer.launch_parameter(self._launch_order())))

        if failed:
            raise DzmodError("installs_failed", count=len(failed))

    def _print_install(self, result: InstallResult, header: str = "mod_installed") -> None:
        """Prints the mod with its copied keys, the written CE files and all CE notes."""

        print(self.messages.get(header, mod_id=result.mod_id, title=result.title))
        for key in result.keys:
            print(self.messages.get("key_copied", name=key))
        for kind, folder in result.chosen_variants.items():
            print(self.messages.get("ce_variant", kind=kind, folder=folder))
        if result.ce_folder:
            print(self.messages.get("ce_added", folder=result.ce_folder))
            for name, _, count in result.ce_files:
                print(self.messages.get("ce_file", name=name, count=count))
        for kind, names in result.conflicts.items():
            print(self.messages.get("ce_conflict", kind=kind, names=", ".join(names)), file=sys.stderr)
        for kind, options in result.skipped_variants.items():
            print(self.messages.get("ce_variant_skipped", kind=kind, options=", ".join(options)), file=sys.stderr)
        for path in result.invalid:
            print(self.messages.get("ce_invalid", path=path), file=sys.stderr)
        if result.economy_error:
            print(self.messages.get("economy_core_invalid", error=result.economy_error), file=sys.stderr)

    def _choose_variant(self, title: str, kind: str, options: list[str]) -> str | None:
        """Lists the map variant folders of a mod and returns the one picked by number, or None on empty input or
        without a terminal."""

        if not sys.stdin.isatty():
            return None

        print(self.messages.get("variant_question", title=title, kind=kind))
        for number, option in enumerate(options, start=1):
            print(f"  {number}) {option}")

        while True:
            answer = input(self.messages.get("variant_prompt")).strip()
            if not answer:
                return None
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return options[int(answer) - 1]

    def _launch_order(self) -> list[str]:
        """Returns the mod IDs in the order of the collection file, resolved via the stored mod list. Returns an
        empty list if the collection or the mod list does not exist or cannot be read."""

        collection = CollectionFile(self.updater.server_dir)
        mod_list = self._mod_list()
        if not collection.exists or not mod_list.exists:
            return []
        try:
            collection.read()
            resolved, _, _ = collection.resolve(mod_list.load())
        except DzmodError:
            return []
        return [item.mod_id for item in resolved]

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
        """Loads the mod list, lets the user pick mods and, if more than one was picked, offers to add them to the
        collection file."""

        items = self._load_mod_list()
        selected = ModPicker(items, self.messages, self.args.verbose).run()
        if not selected:
            print(self.messages.get("selection_cancelled"))
            return []

        if len(selected) > 1:
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

    def _show_mods(self) -> None:
        """Prints the subscribed mods as a table; with `--refresh` they are fetched from Steam first. Raises
        DzmodError if the list is empty."""

        items = self._refresh_mod_list() if self.args.refresh else self._load_mod_list()
        if not items:
            raise DzmodError("mod_list_empty")
        ModTable(items, self.messages).print()

    def _load_mod_list(self) -> list[WorkshopItem]:
        """Reads the mod list, creating it from Steam first if it does not exist yet. Raises DzmodError if the list
        is empty."""

        mod_list = self._mod_list()
        items = mod_list.load() if mod_list.exists else self._refresh_mod_list()

        if not items:
            raise DzmodError("mod_list_empty")
        return items

    def _refresh_mod_list(self) -> list[WorkshopItem]:
        """Fetches the subscribed mods from Steam with a progress line and saves them. Raises DzmodError if the API
        key or SteamID is missing."""

        mod_list = self._mod_list()
        if not mod_list.api_key:
            raise DzmodError("api_key_missing")
        if not mod_list.steam_id:
            raise DzmodError("steam_id_missing")

        print(self.messages.get("mod_list_loading"))
        try:
            items = mod_list.refresh(self._print_progress)
        finally:
            print()

        print(self.messages.get("mod_list_saved", count=len(items), path=mod_list.path))
        return items

    def _mod_list(self) -> ModList:
        """Creates the ModList with the API key and SteamID from the env file."""

        return ModList(self.updater.api, self.env.get("DZMOD_STEAM_API_KEY"), self.env.get("DZMOD_STEAM_ID"))

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
        """Downloads the outdated mods, verifies them via the ACF and installs the current ones again, which also
        re-extracts their CE entries. Raises DzmodError if the login is missing or at least one download failed."""

        login = self.args.login or self.env.get("DZMOD_STEAM_LOGIN")
        if not login:
            raise DzmodError("login_missing", path=self.env.path)

        steam_cmd = self._steam_cmd(login)
        print(self.messages.get("downloading", count=len(outdated)))
        code = steam_cmd.download([state.mod_id for state in outdated])
        if code != 0:
            print(self.messages.get("steamcmd_failed", code=code), file=sys.stderr)

        done, failed = self.updater.downloaded(outdated)
        installer = ModInstaller(self.updater, ServerConfig(self.updater.server_dir), self._choose_variant)

        for state in done:
            self._print_install(installer.install(state.mod_id, state.title), header="installed")

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
        """Builds the parser with the global path options and the `setup` / `mods` / `check` / `update` / `install`
        subcommands."""

        parser = argparse.ArgumentParser(prog="dzmod")
        parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {version('dzmod')}")
        parser.add_argument("--server-dir", default=".", help="DayZ server directory")
        parser.add_argument("--steam-dir", help="SteamCMD data directory (default: directory of steamcmd.sh, "
                                                "otherwise ~/.steam/steam)")

        subparsers = parser.add_subparsers(dest="command", required=False)
        subparsers.add_parser("setup", help="set the Steam login, SteamID64 and Steam Web API key")
        mods = subparsers.add_parser("mods", help="show your subscribed DayZ Workshop mods")
        mods.add_argument("-r", "--refresh", action="store_true", help="fetch the subscribed mods from Steam first")
        subparsers.add_parser("check", help="list mods and their update state")

        update = subparsers.add_parser("update", help="download outdated mods and copy them into the server directory")
        update.add_argument("--login", help="Steam account that owns DayZ")
        update.add_argument("--steamcmd",
                            help="SteamCMD executable (default: steamcmd in PATH, then ~/Steam/steamcmd.sh)")

        install = subparsers.add_parser("install",
                                        help="pick from your subscribed mods, or install by ID or collection")
        install.add_argument("--login", help="Steam account that owns DayZ")
        install.add_argument("--steamcmd",
                             help="SteamCMD executable (default: steamcmd in PATH, then ~/Steam/steamcmd.sh)")
        install.add_argument("-v", "--verbose", action="store_true", help="show more columns in the mod list")
        source = install.add_mutually_exclusive_group()
        source.add_argument("--mod-id", nargs="+", metavar="ID", help="one or more mod IDs")
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
