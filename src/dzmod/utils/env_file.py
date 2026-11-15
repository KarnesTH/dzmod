import os
from pathlib import Path


class EnvFile:
    """Reads `KEY=VALUE` lines from `$XDG_CONFIG_HOME/dzmod/.env` (default `~/.config/dzmod/.env`).
    Variables already set in the environment take precedence over the file."""

    KEYS = ("DZMOD_STEAM_LOGIN", "DZMOD_STEAM_API_KEY")

    def __init__(self) -> None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        self.path = config_home / "dzmod" / ".env"
        self.values = self._parse(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {}

    @property
    def exists(self) -> bool:
        """True if the file exists."""

        return self.path.is_file()

    def get(self, key: str) -> str | None:
        """Returns the environment variable if set and not empty, otherwise the value from the file."""

        return os.environ.get(key) or self.values.get(key) or None

    def create(self, values: dict[str, str]) -> None:
        """Writes the given values to the file with permissions 600 and its directory with 700."""

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
