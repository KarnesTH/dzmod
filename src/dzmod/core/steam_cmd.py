import codecs
import os
import pty
import select
import shutil
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

from dzmod.core.steam_output import SteamOutput


class SteamCmd:
    """Runs SteamCMD workshop downloads for DayZ."""

    APP_ID: ClassVar[str] = "221100"
    DEFAULT_SCRIPT: ClassVar[Path] = Path.home() / "Steam" / "steamcmd.sh"
    IDLE_SECONDS: ClassVar[float] = 0.3

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

    def download(self, mod_ids: list[str], output: SteamOutput) -> int:
        """Downloads all IDs in a single SteamCMD session and returns its exit code. The output is read and passed to
        `output`; on a terminal SteamCMD writes into a pseudo terminal so it flushes prompts immediately, while its
        input stays connected to the real terminal (password, Steam Guard code)."""

        args = [self.executable, "+login", self.login]
        for mod_id in mod_ids:
            args += ["+workshop_download_item", self.APP_ID, mod_id]
        args.append("+quit")

        if sys.stdout.isatty():
            reader, writer = pty.openpty()
            process = subprocess.Popen(args, stdout=writer, stderr=writer)
            os.close(writer)
        else:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            reader = process.stdout.fileno()

        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            while True:
                ready, _, _ = select.select([reader], [], [], self.IDLE_SECONDS)
                if not ready:
                    output.idle()
                    continue
                try:
                    data = os.read(reader, 4096)
                except OSError:
                    break
                if not data:
                    break
                output.feed(decoder.decode(data))
        finally:
            output.feed(decoder.decode(b"", final=True))
            output.finish()
            if process.stdout is None:
                os.close(reader)

        return process.wait()
