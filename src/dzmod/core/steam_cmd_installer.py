import subprocess
import tarfile
from pathlib import Path
from typing import ClassVar
from urllib.error import URLError
from urllib.request import urlopen

from dzmod.core.steam_cmd import SteamCmd
from dzmod.utils.errors import DzmodError


class SteamCmdInstaller:
    """Installs SteamCMD into `~/Steam` as described by Valve: downloads the official archive, extracts it and runs
    `steamcmd.sh +quit` once so it updates itself."""

    URL: ClassVar[str] = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz"
    LIB_COMMANDS: ClassVar[dict[str, str]] = {
        "debian": "sudo apt-get install lib32gcc-s1",
        "fedora": "sudo dnf install glibc.i686 libstdc++.i686",
        "rhel": "sudo dnf install glibc.i686 libstdc++.i686",
        "arch": "sudo pacman -S lib32-gcc-libs  (multilib)",
    }

    def __init__(self, timeout: int = 60) -> None:
        self.script = SteamCmd.DEFAULT_SCRIPT
        self.directory = self.script.parent
        self.timeout = timeout

    def install(self) -> str:
        """Downloads the archive into the target directory, extracts it with the `data` filter (no absolute paths,
        no paths outside the directory, no device files) and deletes the archive. Returns the script path. Raises
        DzmodError if the download fails."""

        self.directory.mkdir(parents=True, exist_ok=True)
        archive = self.directory / "steamcmd_linux.tar.gz"

        try:
            with urlopen(self.URL, timeout=self.timeout) as resp, archive.open("wb") as file:
                while chunk := resp.read(65536):
                    file.write(chunk)
        except (URLError, TimeoutError) as err:
            archive.unlink(missing_ok=True)
            raise DzmodError("steamcmd_download_failed", error=getattr(err, "reason", err)) from err

        try:
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(self.directory, filter="data")
        except tarfile.TarError as err:
            raise DzmodError("steamcmd_download_failed", error=err) from err
        finally:
            archive.unlink(missing_ok=True)

        self.script.chmod(0o755)
        return str(self.script)

    def first_run(self) -> int:
        """Runs `steamcmd.sh +quit` once and returns its exit code."""

        return subprocess.run([str(self.script), "+quit"], check=False).returncode

    def lib_command(self) -> str:
        """Returns the command to install the 32-bit libraries for the distribution found in `/etc/os-release`
        (matched via `ID` and `ID_LIKE`), or all known commands if the distribution is unknown."""

        ids: list[str] = []
        os_release = Path("/etc/os-release")
        if os_release.is_file():
            for line in os_release.read_text(encoding="utf-8", errors="replace").splitlines():
                key, _, value = line.partition("=")
                if key in ("ID", "ID_LIKE"):
                    ids += value.strip().strip('"').lower().split()

        for distro_id in ids:
            if distro_id in self.LIB_COMMANDS:
                return self.LIB_COMMANDS[distro_id]
        return "\n  ".join(dict.fromkeys(self.LIB_COMMANDS.values()))
