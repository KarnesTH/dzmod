import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from dzmod.utils.errors import DzmodError


class GitHubArchive:
    """Downloads a GitHub repository as ZIP of its default branch and keeps it extracted in
    `$XDG_CACHE_HOME/dzmod/repos/<owner>_<repo>` (default `~/.cache/dzmod/repos/...`)."""

    URL = "https://github.com/{repo}/archive/HEAD.zip"

    def __init__(self, repo: str, timeout: int = 120) -> None:
        cache_home = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        self.repo = repo
        self.path = cache_home / "dzmod" / "repos" / repo.replace("/", "_")
        self.timeout = timeout

    def get(self) -> Path:
        """Returns the extracted repository, downloading it first if it is not cached. The ZIP's single top-level
        folder is stripped; entries pointing outside the target folder are skipped. Raises DzmodError if the download
        or the archive fails."""

        if self.path.is_dir():
            return self.path

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.path.parent) as tmp:
            archive = Path(tmp) / "repo.zip"
            try:
                with urlopen(self.URL.format(repo=self.repo), timeout=self.timeout) as resp, archive.open("wb") as file:
                    shutil.copyfileobj(resp, file)
            except (URLError, TimeoutError) as err:
                raise DzmodError("repo_download_failed", repo=self.repo, error=getattr(err, "reason", err)) from err

            target = Path(tmp) / "extracted"
            try:
                with zipfile.ZipFile(archive) as zip_file:
                    for member in zip_file.infolist():
                        parts = Path(member.filename).parts[1:]
                        if not parts or ".." in parts or Path(member.filename).is_absolute():
                            continue
                        destination = target.joinpath(*parts)
                        if member.is_dir():
                            destination.mkdir(parents=True, exist_ok=True)
                        else:
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            with zip_file.open(member) as source, destination.open("wb") as file:
                                shutil.copyfileobj(source, file)
            except zipfile.BadZipFile as err:
                raise DzmodError("repo_download_failed", repo=self.repo, error=err) from err

            target.rename(self.path)

        return self.path
