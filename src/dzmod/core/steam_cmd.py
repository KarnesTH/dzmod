import shutil
import subprocess

from dzmod.utils.errors import DzmodError


class SteamCmd:
    """Runs SteamCMD workshop downloads for DayZ."""

    APP_ID = "221100"

    def __init__(self, binary: str, login: str) -> None:
        """Resolves `binary` via PATH or as a path. Raises DzmodError if it cannot be found."""

        executable = shutil.which(binary)
        if executable is None:
            raise DzmodError("steamcmd_missing", binary=binary)

        self.binary = executable
        self.login = login

    def download(self, mod_ids: list[str]) -> int:
        """Downloads all IDs in a single SteamCMD session and returns its exit code."""

        args = [self.binary, "+login", self.login]
        for mod_id in mod_ids:
            args += ["+workshop_download_item", self.APP_ID, mod_id]
        args.append("+quit")

        return subprocess.run(args).returncode
