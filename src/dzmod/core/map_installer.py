import shutil
from collections.abc import Callable
from pathlib import Path

from dzmod.core.github_archive import GitHubArchive
from dzmod.core.map_catalog import MapCatalog
from dzmod.core.server_config import ServerConfig
from dzmod.models.map_result import MapResult
from dzmod.utils.errors import DzmodError


class MapInstaller:
    """Sets up the mission of a map mod in two steps: `prepare` resolves the mission folder (GitHub, inside the mod or
    a path given by the user) before the download, `install` copies it to `mpmissions/` and sets it as template in
    serverDZ.cfg. Removing reverts to the vanilla mission."""

    def __init__(self, server_dir: Path, catalog: MapCatalog,
                 choose_variant: Callable[[str, list[str]], str | None],
                 ask_path: Callable[[str, str], Path | None]) -> None:
        self.server_dir = server_dir
        self.catalog = catalog
        self.choose_variant = choose_variant
        self.ask_path = ask_path

    def prepare(self, mod_id: str) -> MapResult:
        """Resolves the mission source before anything is downloaded: GitHub missions are fetched now, for missions
        inside the mod the variant is chosen (the path is resolved after the download), manual maps ask for the path.
        Raises DzmodError if no source can be determined or a fetched/given folder has no cfgeconomycore.xml."""

        record = self.catalog.maps[mod_id]
        source = record["source"]
        result = MapResult(mod_id=mod_id, name=record["name"])

        if source["type"] == "github":
            result.mission_path = GitHubArchive(source["repo"]).get() / source["path"]
            result.mission = record["mission"]
            result.source = f"github.com/{source['repo']}"
            if source.get("outdated"):
                result.warnings.append("map_outdated")
        elif source["type"] == "mod":
            variants = list(source["variants"])
            variant = self.choose_variant(record["name"], variants)
            if variant not in variants:
                raise DzmodError("map_variant_missing", name=record["name"])
            result.mission_path = self.server_dir / mod_id / source["variants"][variant]
            result.mission = record["mission"][variant]
            result.source = f"Mod ({variant})"
            return result
        else:
            path = self.ask_path(record["name"], source["link"])
            if path is None:
                raise DzmodError("map_manual", name=record["name"], link=source["link"])
            result.mission_path = path.expanduser().resolve()
            result.mission = result.mission_path.name
            result.source = str(result.mission_path)

        self._validate(result.mission_path)
        return result

    def install(self, result: MapResult) -> MapResult:
        """Copies the prepared mission folder to `mpmissions/<mission>` unless that folder already exists (then it is
        reused) and sets the template. Raises DzmodError if the mission folder has no cfgeconomycore.xml."""

        self._validate(result.mission_path)
        target = self.server_dir / "mpmissions" / result.mission
        if target.exists():
            result.reused = True
        else:
            shutil.copytree(result.mission_path, target)

        ServerConfig(self.server_dir).set_template(result.mission)
        return result

    @staticmethod
    def _validate(mission_path: Path) -> None:
        """Raises DzmodError if `mission_path` has no cfgeconomycore.xml."""

        if not (mission_path / "cfgeconomycore.xml").is_file():
            raise DzmodError("map_mission_invalid", path=mission_path)

    def remove(self, mod_id: str) -> str | None:
        """If the current template is a mission of the map, deletes that mission folder, sets the template back to
        the vanilla mission and returns the removed mission name."""

        config = ServerConfig(self.server_dir)
        if not self.catalog.owns_mission(mod_id, config.template):
            return None

        mission_dir = self.server_dir / "mpmissions" / config.template
        if mission_dir.exists():
            shutil.rmtree(mission_dir)
        config.set_template(MapCatalog.VANILLA_MISSION)
        return mission_dir.name
