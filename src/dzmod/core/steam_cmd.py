import shutil
import subprocess
from pathlib import Path


class SteamCmd:
    """Runs SteamCMD workshop downloads for DayZ."""

    APP_ID = "221100"
    DEFAULT_SCRIPT = Path.home() / "Steam" / "steamcmd.sh"

    def __init__(self, executable: str, login: str) -> None:
        self.executable = executable
        self.login = login

    @classmethod
    def locate(cls, binary: str | None = None) -> str | None:
        """Returns the SteamCMD executable: `binary` if given (resolved via PATH or as a path), otherwise `steamcmd`
        from PATH, otherwise `~/Steam/steamcmd.sh`. Returns None if nothing is found."""

        if binary:
            return shutil.which(binary)
        return shutil.which("steamcmd") or shutil.which(str(cls.DEFAULT_SCRIPT))

    @staticmethod
    def steam_dir(executable: str | None) -> Path:
        """Returns the directory SteamCMD stores its data in: the directory of a manually installed `steamcmd.sh`,
        otherwise `~/.steam/steam` (package manager installation or no SteamCMD found)."""

        if executable and Path(executable).name == "steamcmd.sh":
            return Path(executable).parent.resolve()
        return Path.home() / ".steam" / "steam"

    def download(self, mod_ids: list[str]) -> int:
        """Downloads all IDs in a single SteamCMD session and returns its exit code."""

        args = [self.executable, "+login", self.login]
        for mod_id in mod_ids:
            args += ["+workshop_download_item", self.APP_ID, mod_id]
        args.append("+quit")

        return subprocess.run(args).returncode
