import shutil
from pathlib import Path

from dzmod.core.economy_core import EconomyCore
from dzmod.core.mod_installer import ModInstaller
from dzmod.core.server_config import ServerConfig
from dzmod.models.remove_result import RemoveResult


class ModRemover:
    """Removes installed mods from the server: mod folder, keys no other remaining mod ships, the `ce_<mod_name>`
    folder and its block in cfgeconomycore.xml."""

    def __init__(self, server_dir: Path, config: ServerConfig) -> None:
        self.server_dir = server_dir
        self.keys_dir = server_dir / "keys"
        self.mission_dir = server_dir / "mpmissions" / config.template if config.template else None

    def remove(self, mod_id: str, title: str, remaining: list[str]) -> RemoveResult:
        """Removes the mod. A key is deleted from the server's `keys` folder only if none of the `remaining` mod
        folders ships a key with the same file name; otherwise it is reported as kept with the IDs using it."""

        mod_dir = self.server_dir / mod_id
        result = RemoveResult(mod_id=mod_id, title=title)

        users: dict[str, list[str]] = {}
        for other in remaining:
            for key in self.keys_of(self.server_dir / other):
                users.setdefault(key, []).append(other)

        for key in self.keys_of(mod_dir):
            if key in users:
                result.keys_kept[key] = users[key]
            elif (self.keys_dir / key).is_file():
                (self.keys_dir / key).unlink()
                result.keys_removed.append(key)

        if mod_dir.exists():
            shutil.rmtree(mod_dir)

        if self.mission_dir:
            folder = f"ce_{ModInstaller.folder_name(mod_id, title)}"
            ce_dir = self.mission_dir / folder
            economy = EconomyCore(self.mission_dir)
            removed_block = economy.exists and economy.remove(folder)
            had_folder = ce_dir.exists()
            if had_folder:
                shutil.rmtree(ce_dir)
            if removed_block or had_folder:
                result.ce_folder = folder

        return result

    @staticmethod
    def keys_of(mod_dir: Path) -> set[str]:
        """Returns the file names of all `.bikey` files inside folders named `keys` (any case) of the mod."""

        if not mod_dir.is_dir():
            return set()
        return {
            key.name for key in mod_dir.rglob("*")
            if key.is_file() and key.suffix.lower() == ".bikey" and key.parent.name.lower() == "keys"
        }
