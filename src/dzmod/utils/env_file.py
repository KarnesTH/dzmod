import os
from pathlib import Path
from typing import ClassVar


class EnvFile:
    """Reads `KEY=VALUE` lines from `$XDG_CONFIG_HOME/dzmod/.env` (default `~/.config/dzmod/.env`). Variables already
    set in the environment take precedence over the file. Only KEYS are kept; a Steam Web API key found in the file
    is removed from it when the file is read."""

    KEYS: ClassVar[tuple[str, ...]] = ("DZMOD_STEAM_LOGIN", "DZMOD_STEAM_ID")
    API_KEY: ClassVar[str] = "DZMOD_STEAM_API_KEY"

    def __init__(self) -> None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        self.path = config_home / "dzmod" / ".env"
        self.values = self._parse(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {}
        self.removed_api_key = bool(self.values.pop(self.API_KEY, ""))
        if self.removed_api_key:
            self.create(self.values)

    @property
    def exists(self) -> bool:
        """True if the file exists."""

        return self.path.is_file()

    def get(self, key: str) -> str | None:
        """Returns the environment variable if set and not empty, otherwise the value from the file."""

        return os.environ.get(key) or self.values.get(key) or None

    @classmethod
    def api_key(cls) -> str | None:
        """Returns the Steam Web API key from the environment variable API_KEY, never from the file."""

        return os.environ.get(cls.API_KEY) or None

    def create(self, values: dict[str, str]) -> None:
        """Writes the KEYS from `values` to the file with permissions 600 and its directory with 700."""

        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        content = "".join(f"{key}={values.get(key, '')}\n" for key in self.KEYS)

        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
        os.chmod(self.path, 0o600)
        self.values = self._parse(content)

    @staticmethod
    def _parse(text: str) -> dict[str, str]:
        """Splits each non-comment line at the first `=` and strips surrounding whitespace and quotes."""

        values = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
        return values
