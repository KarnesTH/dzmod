import json
from pathlib import Path
from typing import ClassVar


class ServerState:
    """Keeps the Workshop timestamp of every mod copy in the server directory in `.dzmod-state.json`, so the server
    copy can be compared with Steam independently of the shared workshop folder."""

    FILE_NAME: ClassVar[str] = ".dzmod-state.json"

    def __init__(self, server_dir: Path) -> None:
        self.path = server_dir / self.FILE_NAME
        self.timestamps = self._read()

    def get(self, mod_id: str) -> int | None:
        """Returns the stored timestamp of the mod, or None if the mod was not copied by dzmod."""

        return self.timestamps.get(mod_id)

    def set(self, mod_id: str, timestamp: int) -> None:
        """Stores the timestamp of the mod and writes the file."""

        self.timestamps[mod_id] = timestamp
        self._write()

    def remove(self, mod_id: str) -> None:
        """Removes the mod from the file if it is listed."""

        if self.timestamps.pop(mod_id, None) is not None:
            self._write()

    def _read(self) -> dict[str, int]:
        """Reads the file; a missing or damaged file and entries that are not integers count as empty."""

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): value for key, value in data.items() if isinstance(value, int)}

    def _write(self) -> None:
        """Writes the timestamps sorted by mod ID atomically via a temporary file."""

        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(sorted(self.timestamps.items())), indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)
