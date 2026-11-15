import json
import os
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from dzmod.utils.errors import DzmodError
from dzmod.core.workshop_api import WorkshopAPI
from dzmod.models.workshop_item import WorkshopItem


class ModList:
    """Keeps the list of all DayZ Workshop mods as JSON in `$XDG_CACHE_HOME/dzmod/mods.json`
    (default `~/.cache/dzmod/mods.json`) and refreshes it from Steam when it is missing or older than MAX_AGE."""

    MAX_AGE = 7 * 24 * 60 * 60

    def __init__(self, api: WorkshopAPI, api_key: str | None) -> None:
        cache_home = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        self.path = cache_home / "dzmod" / "mods.json"
        self.api = api
        self.api_key = api_key

    @property
    def outdated(self) -> bool:
        """True if the cache file is missing or older than MAX_AGE."""

        return not self.path.is_file() or time.time() - self.path.stat().st_mtime > self.MAX_AGE

    def load(self, progress: Callable[[int, int], None] | None = None) -> list[WorkshopItem]:
        """Returns the cached mods, refreshing them first if the cache is outdated. Without an API key an existing
        cache is used as it is. Raises DzmodError if there is neither a cache nor an API key."""

        if self.outdated and self.api_key:
            return self.refresh(progress)
        if not self.path.is_file():
            raise DzmodError("api_key_missing")

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [WorkshopItem(**{**entry, "tags": tuple(entry.get("tags", ()))}) for entry in data]
        except (json.JSONDecodeError, TypeError) as err:
            if self.api_key:
                return self.refresh(progress)
            raise DzmodError("mod_list_corrupt", path=self.path) from err

    def refresh(self, progress: Callable[[int, int], None] | None = None) -> list[WorkshopItem]:
        """Fetches all pages from Steam, reports `(loaded, total)` after each page and writes the cache atomically
        via a temporary file."""

        items: list[WorkshopItem] = []
        seen: set[str] = set()

        for page, total in self.api.query_files(self.api_key):
            for item in page:
                if item.mod_id not in seen:
                    seen.add(item.mod_id)
                    items.append(item)
            if progress:
                progress(len(items), total)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(item) for item in items], ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
        return items
