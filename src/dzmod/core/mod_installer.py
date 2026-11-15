import re
import shutil
from collections.abc import Callable

from dzmod.core.ce_extractor import CEExtractor
from dzmod.core.economy_core import EconomyCore
from dzmod.core.mod_updater import ModUpdater
from dzmod.core.server_config import ServerConfig
from dzmod.models.install_result import InstallResult


class ModInstaller:
    """Copies downloaded mods into the server, adds missing keys, extracts the mod's CE entries into
    `ce_<mod_name>` of the mission and builds the `-mod=` parameter."""

    # CF, Community-Online-Tools, Dabs Framework
    PRIORITY_IDS = ("1559212036", "1564026768", "2545327648")

    def __init__(self, updater: ModUpdater, config: ServerConfig,
                 choose: Callable[[str, str, list[str]], str | None]) -> None:
        self.updater = updater
        self.keys_dir = updater.server_dir / "keys"
        self.terrain = config.terrain
        self.mission_dir = updater.server_dir / "mpmissions" / config.template if config.template else None
        self.economy = EconomyCore(self.mission_dir) if self.mission_dir else None
        self.choose = choose

    @property
    def has_mission(self) -> bool:
        """True if the mission from serverDZ.cfg has a cfgeconomycore.xml."""

        return self.economy is not None and self.economy.exists

    def install(self, mod_id: str, title: str, with_ce: bool = True) -> InstallResult:
        """Copies the mod into the server directory and copies `.bikey` files from its `keys` folder (any case) that
        are missing in the server's `keys` folder. With `with_ce` the CE entries are extracted as in `extract_ce`."""

        self.updater.install(mod_id)
        mod_dir = self.updater.server_dir / mod_id
        result = InstallResult(mod_id=mod_id, title=title)

        self.keys_dir.mkdir(exist_ok=True)
        for key in sorted(mod_dir.rglob("*")):
            if (key.is_file() and not key.is_symlink() and key.suffix.lower() == ".bikey"
                    and key.parent.name.lower() == "keys"):
                target = self.keys_dir / key.name
                if not target.exists():
                    shutil.copy2(key, target)
                    result.keys.append(key.name)

        if with_ce:
            self.extract_ce(result)
        return result

    def extract_ce(self, result: InstallResult) -> InstallResult:
        """If the mission exists, writes the CE entries extracted from the installed mod folder into a freshly
        created `ce_<mod_name>` folder and registers its files in cfgeconomycore.xml. `choose` is called with the
        title, the kind and the variant folders when map variants cannot be matched to the terrain."""

        if not self.has_mission:
            return result

        mod_dir = self.updater.server_dir / result.mod_id
        title = result.title
        extractor = CEExtractor(mod_dir, self.terrain, lambda kind, options: self.choose(title, kind, options))
        data = extractor.extract()
        result.invalid = data.invalid
        result.conflicts = data.conflicts
        result.chosen_variants = data.chosen_variants
        result.skipped_variants = data.skipped_variants

        if not any(data.entries.values()):
            return result

        folder = f"ce_{self.folder_name(result.mod_id, title)}"
        ce_dir = self.mission_dir / folder
        if ce_dir.exists():
            shutil.rmtree(ce_dir)
        ce_dir.mkdir()
        written = extractor.write(data, ce_dir)

        try:
            self.economy.upsert(folder, [(name, kind) for name, kind, _ in written])
        except ValueError as err:
            result.economy_error = str(err)
            return result

        result.ce_folder = folder
        result.ce_files = written
        return result

    def launch_parameter(self, order: list[str]) -> str:
        """Builds `-mod=` from all mod folders in the server directory: PRIORITY_IDS first, then the IDs in `order`,
        then the remaining IDs sorted."""

        mod_ids = self.updater.mod_ids()
        ordered = [mod_id for mod_id in dict.fromkeys([*self.PRIORITY_IDS, *order]) if mod_id in mod_ids]
        ordered += [mod_id for mod_id in mod_ids if mod_id not in ordered]
        return f'"-mod={";".join(ordered)}"'

    @staticmethod
    def folder_name(mod_id: str, title: str) -> str:
        """Lowercases the title and replaces every run of non-alphanumeric characters with `_`. Falls back to the
        mod ID if nothing is left."""

        return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or mod_id
