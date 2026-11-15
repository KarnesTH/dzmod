import shutil
from pathlib import Path

from dzmod.core.acf_file import ACFFile
from dzmod.core.server_state import ServerState
from dzmod.core.steam_cmd import SteamCmd
from dzmod.core.workshop_api import WorkshopAPI
from dzmod.models.mod_state import ModState


class ModUpdater:
    """Compares the server's mod copies against the Workshop, finds mods that are already current in the workshop
    folder and copies mods from there into the server directory."""

    def __init__(self, server_dir: Path, steam_dir: Path, api: WorkshopAPI) -> None:
        self.server_dir = server_dir
        self.acf_path = steam_dir / "steamapps" / "workshop" / f"appworkshop_{SteamCmd.APP_ID}.acf"
        self.content_dir = steam_dir / "steamapps" / "workshop" / "content" / SteamCmd.APP_ID
        self.api = api
        self.state = ServerState(server_dir)

    def mod_ids(self) -> list[str]:
        """Returns the names of all directories in the server dir that consist of ASCII digits only."""

        return sorted(
            entry.name
            for entry in self.server_dir.iterdir()
            if entry.is_dir() and entry.name.isascii() and entry.name.isdigit()
        )

    def check(self) -> list[ModState]:
        """Compares the timestamp of each server copy with the Workshop. The local timestamp comes from the server
        state; copies made before dzmod kept a state fall back to the ACF timestamp. Mods the API does not return get
        None as remote timestamp."""

        mod_ids = self.mod_ids()
        if not mod_ids:
            return []

        workshop = ACFFile(self.acf_path).installed_timestamps()
        remote = self.api.fetch(mod_ids)

        return [
            ModState(
                mod_id=mod_id,
                title=remote[mod_id].title if mod_id in remote else "",
                local_updated=self._local(mod_id, workshop),
                remote_updated=remote[mod_id].time_updated if mod_id in remote else None,
            )
            for mod_id in mod_ids
        ]

    def in_workshop(self, states: list[ModState]) -> tuple[list[ModState], list[ModState]]:
        """Re-reads the ACF and splits the states into (current in the workshop folder, missing or outdated there).
        A mod counts as current if its content folder exists and its ACF timestamp is at least the remote one."""

        workshop = ACFFile(self.acf_path).installed_timestamps()
        current, missing = [], []

        for state in states:
            ready = workshop.get(state.mod_id, 0) >= (state.remote_updated or 0)
            (current if ready and (self.content_dir / state.mod_id).is_dir() else missing).append(state)

        return current, missing

    def install(self, mod_id: str) -> None:
        """Deletes the mod folder in the server directory, copies it fresh from the workshop content directory
        (symbolic links are skipped) and stores the ACF timestamp of the copied content in the server state."""

        source = self.content_dir / mod_id
        target = self.server_dir / mod_id

        if target.exists():
            shutil.rmtree(target)

        shutil.copytree(source, target, ignore=self._symlinks)
        self.state.set(mod_id, ACFFile(self.acf_path).installed_timestamps().get(mod_id, 0))

    def _local(self, mod_id: str, workshop: dict[str, int]) -> int:
        """Returns the server state timestamp of the mod, or its ACF timestamp if the state has no entry."""

        stored = self.state.get(mod_id)
        return stored if stored is not None else workshop.get(mod_id, 0)

    @staticmethod
    def _symlinks(directory: str, names: list[str]) -> list[str]:
        """Returns the names in `directory` that are symbolic links, for `shutil.copytree(ignore=…)`."""

        return [name for name in names if (Path(directory) / name).is_symlink()]
