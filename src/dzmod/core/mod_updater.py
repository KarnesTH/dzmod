import shutil
from pathlib import Path

from dzmod.core.acf_file import ACFFile
from dzmod.models.mod_state import ModState
from dzmod.core.steam_cmd import SteamCmd
from dzmod.core.workshop_api import WorkshopAPI


class ModUpdater:
    """Compares the server's mod folders against the ACF and the Workshop, and replaces outdated ones."""

    def __init__(self, server_dir: Path, steam_dir: Path, api: WorkshopAPI) -> None:
        self.server_dir = server_dir
        self.acf_path = steam_dir / "steamapps" / "workshop" / f"appworkshop_{SteamCmd.APP_ID}.acf"
        self.content_dir = steam_dir / "steamapps" / "workshop" / "content" / SteamCmd.APP_ID
        self.api = api

    def mod_ids(self) -> list[str]:
        """Returns the names of all directories in the server dir that consist of ASCII digits only."""

        return sorted(
            entry.name
            for entry in self.server_dir.iterdir()
            if entry.is_dir() and entry.name.isascii() and entry.name.isdigit()
        )

    def check(self) -> list[ModState]:
        """Reads local timestamps from the ACF and remote ones from the API."""

        mod_ids = self.mod_ids()
        if not mod_ids:
            return []

        local = ACFFile(self.acf_path).installed_timestamps()
        remote = self.api.fetch(mod_ids)

        return [
            ModState(
                mod_id=mod_id,
                title=remote[mod_id].title if mod_id in remote else "",
                local_updated=local.get(mod_id, 0),
                remote_updated=remote[mod_id].time_updated if mod_id in remote else 0,
            )
            for mod_id in mod_ids
        ]

    def downloaded(self, states: list[ModState]) -> tuple[list[ModState], list[ModState]]:
        """Re-reads the ACF and splits the states into (now current, still outdated) ones."""

        local = ACFFile(self.acf_path).installed_timestamps()
        done, failed = [], []

        for state in states:
            current = local.get(state.mod_id, 0) >= state.remote_updated
            (done if current and (self.content_dir / state.mod_id).is_dir() else failed).append(state)

        return done, failed

    def install(self, mod_id: str) -> None:
        """Deletes the mod folder in the server directory and copies it fresh from the workshop content directory."""

        source = self.content_dir / mod_id
        target = self.server_dir / mod_id

        if target.exists():
            shutil.rmtree(target)

        shutil.copytree(source, target)
