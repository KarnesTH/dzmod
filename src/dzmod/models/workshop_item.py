from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkshopItem:
    mod_id: str
    title: str
    time_updated: int
    time_created: int = 0
    subscriptions: int = 0
    file_size: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_detail(cls, detail: dict) -> "WorkshopItem":
        """Builds a WorkshopItem from a Steam `publishedfiledetails` entry. Missing numbers become 0. Raises KeyError
        if `publishedfileid` is missing."""

        return cls(
            mod_id=str(detail["publishedfileid"]),
            title=detail.get("title", ""),
            time_updated=int(detail.get("time_updated", 0)),
            time_created=int(detail.get("time_created", 0)),
            subscriptions=int(detail.get("subscriptions", 0)),
            file_size=int(detail.get("file_size", 0) or 0),
            tags=tuple(tag.get("tag", "") for tag in detail.get("tags", []) if tag.get("tag")),
        )
