import json
import time
from collections.abc import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dzmod.utils.errors import DzmodError
from dzmod.models.workshop_item import WorkshopItem


class WorkshopAPI:
    """Queries `ISteamRemoteStorage/GetPublishedFileDetails` and `IPublishedFileService/GetUserFiles`."""

    DETAILS_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
    USER_FILES_URL = "https://api.steampowered.com/IPublishedFileService/GetUserFiles/v1/"
    APP_ID = 221100
    BATCH_SIZE = 100
    RATE_LIMIT_WAIT = 30
    RATE_LIMIT_RETRIES = 3

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def fetch(self, mod_ids: list[str]) -> dict[str, WorkshopItem]:
        """Posts the IDs in the batches and returns all items with `result == 1`, keyed by mod ID."""

        items: dict[str, WorkshopItem] = {}

        for start in range(0, len(mod_ids), self.BATCH_SIZE):
            batch = mod_ids[start:start + self.BATCH_SIZE]
            payload = {"itemcount": len(batch)}
            payload.update({f"publishedfileids[{i}]": mod_id for i, mod_id in enumerate(batch)})

            body = self._request(Request(self.DETAILS_URL, data=urlencode(payload).encode(), method="POST"))

            for detail in body.get("response", {}).get("publishedfiledetails", []):
                if detail.get("result") != 1:
                    continue
                item = WorkshopItem.from_detail(detail)
                items[item.mod_id] = item

        return items

    def user_subscriptions(self, api_key: str, steam_id: str) -> Iterator[tuple[list[dict], int]]:
        """Pages through the DayZ Workshop items the user with `steam_id` has subscribed to via `GetUserFiles` with
        `type=mysubscriptions` and yields each page as raw `publishedfiledetails` entries together with the total
        count. Stops when all items are loaded or a page is empty."""

        page, loaded = 1, 0
        while True:
            params = {
                "key": api_key,
                "steamid": steam_id,
                "appid": self.APP_ID,
                "creator_appid": self.APP_ID,
                "type": "mysubscriptions",
                "page": page,
                "numperpage": self.BATCH_SIZE,
                "return_details": "true",
                "return_tags": "true",
                "return_kv_tags": "true",
                "return_children": "true",
                "return_previews": "true",
                "return_vote_data": "true",
                "return_metadata": "true",
            }
            response = self._request(Request(f"{self.USER_FILES_URL}?{urlencode(params)}")).get("response", {})
            details = response.get("publishedfiledetails", [])
            total = int(response.get("total", 0))

            if not details:
                return

            loaded += len(details)
            yield details, total

            if loaded >= total:
                return
            page += 1

    def _request(self, req: Request) -> dict:
        """Sends the request and returns the decoded JSON body. HTTP 429 is retried after RATE_LIMIT_WAIT seconds up
        to RATE_LIMIT_RETRIES times. Raises DzmodError for an invalid API key (401/403), other HTTP errors,
        connection problems and invalid JSON."""

        for attempt in range(self.RATE_LIMIT_RETRIES + 1):
            try:
                with urlopen(req, timeout=self.timeout) as resp:
                    return json.load(resp)
            except HTTPError as err:
                if err.code == 429 and attempt < self.RATE_LIMIT_RETRIES:
                    time.sleep(self.RATE_LIMIT_WAIT)
                    continue
                if err.code in (401, 403):
                    raise DzmodError("api_key_invalid") from err
                raise DzmodError("api_http_error", code=err.code) from err
            except (URLError, TimeoutError) as err:
                raise DzmodError("api_unreachable", error=getattr(err, "reason", err)) from err
            except json.JSONDecodeError as err:
                raise DzmodError("api_invalid_response") from err

        raise DzmodError("api_http_error", code=429)
