import argparse
import sys
import termios
import tty
from importlib.metadata import version
from pathlib import Path

from dzmod.core.collection_file import CollectionFile
from dzmod.utils.errors import DzmodError
from dzmod.utils.console import Console
from dzmod.utils.env_file import EnvFile
from dzmod.utils.messages import Messages
from dzmod.core.expansion_installer import ExpansionInstaller
from dzmod.core.map_catalog import MapCatalog
from dzmod.core.map_installer import MapInstaller
from dzmod.core.mod_installer import ModInstaller
from dzmod.core.mod_list import ModList
from dzmod.core.mod_picker import ModPicker
from dzmod.core.mod_remover import ModRemover
from dzmod.core.mod_table import ModTable
from dzmod.models.expansion_result import ExpansionResult
from dzmod.models.install_result import InstallResult
from dzmod.models.map_result import MapResult
from dzmod.models.mod_state import ModState
from dzmod.core.mod_updater import ModUpdater
from dzmod.core.server_config import ServerConfig
from dzmod.core.steam_cmd import SteamCmd
from dzmod.core.steam_cmd_installer import SteamCmdInstaller
from dzmod.core.workshop_api import WorkshopAPI
from dzmod.models.workshop_item import WorkshopItem


class CLI:
    """Parses the arguments and runs the subcommands. `setup` and `mods` only configure the CLI and work in any
    directory; `check`, `update`, `install` and `remove` need a DayZ server directory."""

    SERVER_BINARY = "DayZServer"
    EXPANSION_PREFIX = "dayz-expansion"
    STEAM_ID_PREFIX = "7656119"

    def __init__(self, messages: Messages) -> None:
        self.messages = messages
        self.args = self._parser().parse_args()
        self.env = EnvFile()
        self.console = Console()
        self.catalog = MapCatalog()
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
        elif self.args.command == "remove":
            self._remove()
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
        mods already in the server and resolves the mission source of a selected map before downloading the rest in
        one SteamCMD run. The map is set up first (mission and template), then the CE of already installed mods moves
        to the new mission, then the other mods are installed and the Expansion CE is added when an Expansion mod is
        present. Raises DzmodError if the login is missing, the map mission cannot be resolved or a download failed."""

        if self.args.mod_id:
            mods = self._mods_from_ids()
        elif self.args.collection:
            mods = self._mods_from_collection()
        else:
            mods = self._mods_from_list()

        if not mods:
            print(self.messages.get("nothing_to_install"))
            return

        installed = self.updater.mod_ids()
        for item in mods:
            if item.mod_id in installed:
                print(self.messages.get("already_installed", mod_id=item.mod_id, title=item.title))
        pending = self._limit_maps([item for item in mods if item.mod_id not in installed], installed)
        map_item = next((item for item in pending if self.catalog.is_map(item.mod_id)), None)
        prepared = self._map_installer().prepare(map_item.mod_id) if map_item else None

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
            results: list[InstallResult] = []
            map_result, refreshed = None, []

            for state in done:
                if self.catalog.is_map(state.mod_id):
                    results.append(self._installer().install(state.mod_id, state.title, with_ce=False))
                    map_result = self._map_installer().install(prepared)
                    refreshed = self._refresh_ce(installed)

            installer = self._installer()
            if done and not installer.has_mission:
                print(self.messages.get("mission_missing", path=installer.mission_dir or ServerConfig.FILE_NAME),
                      file=sys.stderr)
            results += [installer.install(state.mod_id, state.title)
                        for state in done if not self.catalog.is_map(state.mod_id)]

            expansion_result = self._sync_expansion(force=map_result is not None)

            self._report_installs("section_install", results, failed)
            self._report_map(map_result, refreshed)
            self._report_expansion(expansion_result)
            self._report_summary("summary_install", results, failed)

        self._report_launch_parameter()

        if failed:
            raise DzmodError("installs_failed", count=len(failed))

    def _limit_maps(self, pending: list[WorkshopItem], installed: list[str]) -> list[WorkshopItem]:
        """Allows one map mod per server: with several selected maps the user picks one (the others are dropped);
        a selected map while another map mod is installed raises DzmodError."""

        maps = [item for item in pending if self.catalog.is_map(item.mod_id)]
        if not maps:
            return pending

        if len(maps) > 1:
            names = [self.catalog.maps[item.mod_id]["name"] for item in maps]
            choice = self._choose_option(self.messages.get("map_choose"), names)
            if choice is None:
                raise DzmodError("map_several", names=", ".join(names))
            keep = maps[names.index(choice)]
            pending = [item for item in pending if item not in maps or item is keep]
            maps = [keep]

        for mod_id in installed:
            if self.catalog.is_map(mod_id) and mod_id != maps[0].mod_id:
                raise DzmodError("map_installed", name=self.catalog.maps[mod_id]["name"])
        return pending

    def _installer(self) -> ModInstaller:
        """Creates a ModInstaller for the mission currently set in serverDZ.cfg."""

        return ModInstaller(self.updater, ServerConfig(self.updater.server_dir), self._choose_variant)

    def _map_installer(self) -> MapInstaller:
        """Creates a MapInstaller with the interactive variant and path prompts."""

        return MapInstaller(
            self.updater.server_dir, self.catalog,
            lambda name, options: self._choose_option(self.messages.get("map_variant", name=name), options),
            self._ask_mission_path,
        )

    def _refresh_ce(self, mod_ids: list[str]) -> list[InstallResult]:
        """Extracts the CE entries of the given installed non-map mods again into the current mission."""

        mod_ids = [mod_id for mod_id in mod_ids if not self.catalog.is_map(mod_id)]
        if not mod_ids:
            return []
        items = self.updater.api.fetch(mod_ids)
        installer = self._installer()
        titles = {mod_id: items[mod_id].title if mod_id in items else "" for mod_id in mod_ids}
        return [installer.extract_ce(InstallResult(mod_id=mod_id, title=titles[mod_id])) for mod_id in mod_ids]

    def _sync_expansion(self, force: bool, titles: dict[str, str] | None = None) -> ExpansionResult | None:
        """Adds the Expansion CE to the current mission if an Expansion mod is installed and it is missing or `force`
        is set; removes it if no Expansion mod is left. `titles` maps the installed IDs to titles and is fetched if
        not given. Returns None if nothing changed."""

        config = ServerConfig(self.updater.server_dir)
        if not config.template or not (self.updater.server_dir / "mpmissions" / config.template).is_dir():
            return None

        if titles is None:
            items = self.updater.api.fetch(self.updater.mod_ids())
            titles = {mod_id: item.title for mod_id, item in items.items()}

        expansion = ExpansionInstaller(self.updater.server_dir / "mpmissions" / config.template)
        present = any(title.casefold().startswith(self.EXPANSION_PREFIX) for title in titles.values())

        if present and (force or not expansion.installed):
            template = self.catalog.expansion_template(config.template)
            return expansion.install(template) if template else ExpansionResult()
        if not present and expansion.installed:
            expansion.remove()
            return ExpansionResult(removed=True)
        return None

    def _report_installs(self, section: str, results: list[InstallResult], failed: list[ModState]) -> None:
        """Prints the section with one block per installed mod (keys, map variant, CE files, warnings) and one block
        per failed download."""

        get = self.messages.get
        self.console.section(get(section))

        for index, result in enumerate(results):
            if index:
                self.console.blank()
            self.console.mod(result.title, result.mod_id, ok=True)
            if result.keys:
                self.console.detail(get("label_keys"), ", ".join(result.keys))
            if result.ce_folder:
                self.console.detail(get("label_ce"), result.ce_folder)
                for name, _, count in result.ce_files:
                    self.console.detail("", get("ce_entries", name=name, count=count))
            for kind, folder in result.chosen_variants.items():
                self.console.detail(get("label_map"), f"{folder} ({kind})")
            for kind, names in result.conflicts.items():
                self.console.warning(get("ce_conflict", kind=kind, names=", ".join(names)))
            for kind, options in result.skipped_variants.items():
                self.console.warning(get("ce_variant_skipped", kind=kind, options=", ".join(options)))
            for path in result.invalid:
                self.console.warning(get("ce_invalid", path=path))
            if result.economy_error:
                self.console.warning(get("economy_core_invalid", error=result.economy_error))

        for index, state in enumerate(failed):
            if index or results:
                self.console.blank()
            self.console.mod(state.title, state.mod_id, ok=False)
            self.console.detail("", get("download_failed"))

    def _report_map(self, result: MapResult | None, refreshed: list[InstallResult]) -> None:
        """Prints the map section: mission, source, template and how many mods moved their CE to the new mission."""

        if result is None:
            return
        get = self.messages.get
        self.console.section(get("section_map"))
        self.console.mod(result.name, result.mod_id, ok=True)
        mission = result.mission + (f"  {get('mission_reused')}" if result.reused else "")
        self.console.detail(get("label_mission"), mission)
        self.console.detail(get("label_source"), result.source)
        self.console.detail(get("label_template"), get("template_set", mission=result.mission))
        if refreshed:
            self.console.detail(get("label_ce"), get("ce_refreshed", count=sum(1 for r in refreshed if r.ce_folder)))
        for key in result.warnings:
            self.console.warning(get(key))

    def _report_expansion(self, result: ExpansionResult | None) -> None:
        """Prints the Expansion section: template, CE files and event spawns, or that the Expansion CE was removed."""

        if result is None:
            return
        get = self.messages.get
        self.console.section("Expansion")
        if result.removed:
            self.console.detail(get("label_ce"), get("expansion_removed"))
        elif result.template is None:
            self.console.warning(get("expansion_no_template"))
        else:
            self.console.detail(get("label_template"), result.template)
            self.console.detail(get("label_ce"), f"expansion_ce ({', '.join(result.files)})")
            self.console.detail(get("label_spawns"), get("event_spawns", count=result.event_spawns))
            if result.incomplete:
                self.console.warning(get("expansion_incomplete"))

    def _report_summary(self, summary: str, results: list[InstallResult], failed: list[ModState]) -> None:
        """Prints the summary section with counts of installed, failed, copied keys and CE folders."""

        self.console.section(self.messages.get("section_summary"))
        self.console.highlight(self.messages.get(summary, done=len(results), failed=len(failed),
                                                 keys=sum(len(result.keys) for result in results),
                                                 ce=sum(1 for result in results if result.ce_folder)))

    def _report_launch_parameter(self) -> None:
        """Prints the start parameter section for all mods in the server directory."""

        installer = ModInstaller(self.updater, ServerConfig(self.updater.server_dir), self._choose_variant)
        self.console.section(self.messages.get("section_launch"))
        if self.updater.mod_ids():
            self.console.highlight(installer.launch_parameter(self._launch_order()))
        else:
            self.console.highlight(self.messages.get("no_mods_left"))

    def _remove(self) -> None:
        """Lets the user pick installed mods (or takes `--mod-id`), asks for confirmation and removes them: a map mod
        first (mission deleted, template back to vanilla, CE of the remaining mods moved there), then the other mods.
        The Expansion CE is removed when no Expansion mod is left. Prints the report and the new start parameter."""

        installed = self.updater.mod_ids()
        if not installed:
            print(self.messages.get("no_mods", path=self.updater.server_dir))
            return

        items = self.updater.api.fetch(installed)
        mods = [items.get(mod_id) or WorkshopItem(mod_id=mod_id, title="", time_updated=0) for mod_id in installed]
        titles = {item.mod_id: item.title or item.mod_id for item in mods}

        if self.args.mod_id:
            for mod_id in self.args.mod_id:
                if mod_id not in installed:
                    print(self.messages.get("not_installed", mod_id=mod_id), file=sys.stderr)
            selected = [item for item in mods if item.mod_id in self.args.mod_id]
        else:
            selected = ModPicker(mods, self.messages, self.args.verbose).run()

        if not selected:
            print(self.messages.get("selection_cancelled"))
            return

        selected.sort(key=lambda item: not self.catalog.is_map(item.mod_id))
        for item in selected:
            print(f"  {item.mod_id:<12} {item.title}")
        template = ServerConfig(self.updater.server_dir).template
        if any(self.catalog.is_map(item.mod_id) for item in selected):
            print(self.messages.get("remove_map_warning", mission=template))
        answer = input(self.messages.get("remove_confirm", count=len(selected))).strip().lower()
        if answer not in self.messages.get("yes_answers").split(","):
            print(self.messages.get("remove_cancelled"))
            return

        selected_ids = {item.mod_id for item in selected}
        remaining = [mod_id for mod_id in installed if mod_id not in selected_ids]
        results, removed_mission, refreshed = [], None, []

        for item in selected:
            remover = ModRemover(self.updater.server_dir, ServerConfig(self.updater.server_dir))
            results.append(remover.remove(item.mod_id, item.title, remaining))
            if self.catalog.is_map(item.mod_id):
                removed_mission = self._map_installer().remove(item.mod_id) or removed_mission
                if removed_mission:
                    refreshed = self._refresh_ce(remaining)

        expansion_result = self._sync_expansion(force=removed_mission is not None,
                                                titles={mod_id: titles[mod_id] for mod_id in remaining})

        get = self.messages.get
        self.console.section(get("section_remove"))
        for index, result in enumerate(results):
            if index:
                self.console.blank()
            self.console.mod(result.title, result.mod_id, ok=True)
            for key in result.keys_removed:
                self.console.detail(get("label_keys"), get("key_removed", name=key))
            for key, users in result.keys_kept.items():
                names = ", ".join(titles.get(user, user) for user in users)
                self.console.detail(get("label_keys"), get("key_kept", name=key, users=names))
            if result.ce_folder:
                self.console.detail(get("label_ce"), get("ce_removed", folder=result.ce_folder))
            if self.catalog.is_map(result.mod_id) and removed_mission:
                self.console.detail(get("label_mission"), get("mission_removed", mission=removed_mission))
                self.console.detail(get("label_template"), get("template_set", mission=MapCatalog.VANILLA_MISSION))
                if refreshed:
                    self.console.detail(get("label_ce"),
                                        get("ce_refreshed", count=sum(1 for r in refreshed if r.ce_folder)))

        self._report_expansion(expansion_result)
        self.console.section(get("section_summary"))
        self.console.highlight(get("summary_remove", done=len(results),
                                   keys=sum(len(result.keys_removed) for result in results),
                                   ce=sum(1 for result in results if result.ce_folder)))
        self._report_launch_parameter()

    def _choose_variant(self, title: str, kind: str, options: list[str]) -> str | None:
        """Asks which map variant folder of a mod's CE files should be used."""

        return self._choose_option(self.messages.get("variant_question", title=title, kind=kind), options)

    def _choose_option(self, question: str, options: list[str]) -> str | None:
        """Prints the question with numbered options and returns the option picked by number, or None on empty input
        or without a terminal."""

        if not sys.stdin.isatty():
            return None

        print(question)
        for number, option in enumerate(options, start=1):
            print(f"  {number}) {option}")

        while True:
            answer = input(self.messages.get("variant_prompt")).strip()
            if not answer:
                return None
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return options[int(answer) - 1]

    def _ask_mission_path(self, name: str, link: str) -> Path | None:
        """Explains where the mission files of a map come from and asks for the path of the downloaded mission
        folder. Returns None on empty input or without a terminal."""

        if not sys.stdin.isatty():
            return None
        print(self.messages.get("map_manual_question", name=name, link=link))
        answer = input(self.messages.get("map_manual_prompt")).strip()
        return Path(answer) if answer else None

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
        re-extracts their CE entries (map mods are only copied). Raises DzmodError if the login is missing or at least
        one download failed."""

        login = self.args.login or self.env.get("DZMOD_STEAM_LOGIN")
        if not login:
            raise DzmodError("login_missing", path=self.env.path)

        steam_cmd = self._steam_cmd(login)
        print(self.messages.get("downloading", count=len(outdated)))
        code = steam_cmd.download([state.mod_id for state in outdated])
        if code != 0:
            print(self.messages.get("steamcmd_failed", code=code), file=sys.stderr)

        done, failed = self.updater.downloaded(outdated)
        installer = self._installer()

        results = [installer.install(state.mod_id, state.title, with_ce=not self.catalog.is_map(state.mod_id))
                   for state in done]
        self._report_installs("section_update", results, failed)
        self._report_summary("summary_update", results, failed)
        self._report_launch_parameter()

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
        """Builds the parser with the global path options and the `setup` / `mods` / `check` / `update` / `install` /
        `remove` subcommands."""

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

        remove = subparsers.add_parser("remove", help="remove installed mods from the server")
        remove.add_argument("-v", "--verbose", action="store_true", help="show more columns in the mod list")
        remove.add_argument("--mod-id", nargs="+", metavar="ID", help="one or more installed mod IDs")

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
