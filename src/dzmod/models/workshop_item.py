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
