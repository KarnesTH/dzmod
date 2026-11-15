import json
import os
from collections.abc import Callable
from pathlib import Path

from dzmod.core.workshop_api import WorkshopAPI
from dzmod.models.workshop_item import WorkshopItem
from dzmod.utils.errors import DzmodError


class ModList:
    """Keeps the user's subscribed DayZ Workshop mods as the complete Steam responses in
    `$XDG_DATA_HOME/dzmod/mods.json` (default `~/.local/share/dzmod/mods.json`)."""

    def __init__(self, api: WorkshopAPI, steam_id: str | None) -> None:
        data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        self.path = data_home / "dzmod" / "mods.json"
        self.api = api
        self.steam_id = steam_id

    @property
    def exists(self) -> bool:
        """True if the file exists."""

        return self.path.is_file()

    def load(self) -> list[WorkshopItem]:
        """Reads the stored Steam responses and builds WorkshopItems from them. Raises DzmodError if the file is
        damaged or in an older format."""

        try:
            return [WorkshopItem.from_detail(detail) for detail in json.loads(self.path.read_text(encoding="utf-8"))]
        except (json.JSONDecodeError, TypeError, KeyError, AttributeError) as err:
            raise DzmodError("mod_list_corrupt", path=self.path) from err

    def refresh(self, api_key: str, progress: Callable[[int, int], None] | None = None) -> list[WorkshopItem]:
        """Fetches all subscribed mods page by page with `api_key` (only used for the requests, never stored),
        reports `(loaded, total)` after each page and writes the raw responses atomically via a temporary file.
        Raises DzmodError if the API key or SteamID is missing."""

        if not api_key:
            raise DzmodError("api_key_missing")
        if not self.steam_id:
            raise DzmodError("steam_id_missing")

        details: list[dict] = []
        seen: set[str] = set()

        for page, total in self.api.user_subscriptions(api_key, self.steam_id):
            for detail in page:
                mod_id = str(detail.get("publishedfileid", ""))
                if mod_id and mod_id not in seen and detail.get("result", 1) == 1:
                    seen.add(mod_id)
                    details.append(detail)
            if progress:
                progress(len(details), total)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(details, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
        return [WorkshopItem.from_detail(detail) for detail in details]
