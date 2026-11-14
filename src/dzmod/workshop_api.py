import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dzmod.errors import DzmodError
from dzmod.workshop_item import WorkshopItem


class WorkshopAPI:
    """Queries `ISteamRemoteStorage/GetPublishedFileDetails`."""

    URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
    BATCH_SIZE = 100

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def fetch(self, mod_ids: list[str]) -> dict[str, WorkshopItem]:
        """Posts the IDs in the batches and returns all items with `result == 1`, keyed by mod ID.
        Raises DzmodError if Steam is unreachable, answers with an HTTP error or returns invalid JSON."""

        items: dict[str, WorkshopItem] = {}

        for start in range(0, len(mod_ids), self.BATCH_SIZE):
            batch = mod_ids[start:start + self.BATCH_SIZE]
            payload = {"itemcount": len(batch)}
            payload.update({f"publishedfileids[{i}]": mod_id for i, mod_id in enumerate(batch)})

            req = Request(self.URL, data=urlencode(payload).encode(), method="POST")
            try:
                with urlopen(req, timeout=self.timeout) as resp:
                    body = json.load(resp)
            except HTTPError as err:
                raise DzmodError("api_http_error", code=err.code) from err
            except (URLError, TimeoutError) as err:
                raise DzmodError("api_unreachable", error=getattr(err, "reason", err)) from err
            except json.JSONDecodeError as err:
                raise DzmodError("api_invalid_response") from err

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
