import json
import time
from collections.abc import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dzmod.utils.errors import DzmodError
from dzmod.models.workshop_item import WorkshopItem


class WorkshopAPI:
    """Queries `ISteamRemoteStorage/GetPublishedFileDetails` and `IPublishedFileService/QueryFiles`."""

    DETAILS_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
    QUERY_URL = "https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/"
    APP_ID = 221100
    BATCH_SIZE = 100
    QUERY_RANKED_BY_SUBSCRIPTIONS = 12
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
                item = self._item(detail)
                items[item.mod_id] = item

        return items

    def query_files(self, api_key: str) -> Iterator[tuple[list[WorkshopItem], int]]:
        """Pages through all DayZ Workshop items ranked by subscriptions via `cursor` and yields each page with the
        total item count. Stops when a page is empty or the cursor does not change."""

        cursor = "*"
        while True:
            params = {
                "key": api_key,
                "query_type": self.QUERY_RANKED_BY_SUBSCRIPTIONS,
                "cursor": cursor,
                "numperpage": self.BATCH_SIZE,
                "appid": self.APP_ID,
                "creator_appid": self.APP_ID,
                "filetype": 0,
                "return_details": "true",
                "return_tags": "true",
            }
            body = self._request(Request(f"{self.QUERY_URL}?{urlencode(params)}"))
            response = body.get("response", {})
            details = response.get("publishedfiledetails", [])

            if not details:
                return

            yield [self._item(detail) for detail in details if detail.get("title")], int(response.get("total", 0))

            next_cursor = response.get("next_cursor")
            if not next_cursor or next_cursor == cursor:
                return
            cursor = next_cursor

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

    @staticmethod
    def _item(detail: dict) -> WorkshopItem:
        """Builds a WorkshopItem from a `publishedfiledetails` entry. Missing numbers become 0."""

        return WorkshopItem(
            mod_id=str(detail["publishedfileid"]),
            title=detail.get("title", ""),
            time_updated=int(detail.get("time_updated", 0)),
            time_created=int(detail.get("time_created", 0)),
            subscriptions=int(detail.get("subscriptions", 0)),
            file_size=int(detail.get("file_size", 0) or 0),
            tags=tuple(tag.get("tag", "") for tag in detail.get("tags", []) if tag.get("tag")),
        )
