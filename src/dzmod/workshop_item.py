from dataclasses import dataclass


@dataclass(frozen=True)
class WorkshopItem:
    mod_id: str
    title: str
    time_updated: int
