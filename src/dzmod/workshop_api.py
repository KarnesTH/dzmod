import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dzmod.workshop_item import WorkshopItem


class WorkshopAPI:
    """Queries `ISteamRemoteStorage/GetPublishedFileDetails`."""

    URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
    BATCH_SIZE = 100

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def fetch(self, mod_ids: list[str]) -> dict[str, WorkshopItem]:
        """Posts the IDs in the batches and returns all items with `result == 1`, keyed by mod ID."""

        items: dict[str, WorkshopItem] = {}

        for start in range(0, len(mod_ids), self.BATCH_SIZE):
            batch = mod_ids[start:start + self.BATCH_SIZE]
            payload = {"itemcount": len(batch)}
            payload.update({f"publishedfields[{i}]": mod_id for i, mod_id in enumerate(batch)})

            req = Request(self.URL, data=urlencode(payload).encode(), method="POST")
            with urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp)

            for detail in body.get("response", {}).get("publishedfiledetails", []):
                if detail.get("result") != 1:
                    continue
                mod_id = str(detail["publishedfileid"])
                items[mod_id] = WorkshopItem(
                    mod_id=mod_id,
                    title=detail.get("title", ""),
                    time_updated=int(detail.get("time_updated", 0)),
                )

        return items
