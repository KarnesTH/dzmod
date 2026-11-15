from dataclasses import dataclass, field


@dataclass
class RemoveResult:
    mod_id: str
    title: str
    keys_removed: list[str] = field(default_factory=list)
    keys_kept: dict[str, list[str]] = field(default_factory=dict)
    ce_folder: str | None = None
