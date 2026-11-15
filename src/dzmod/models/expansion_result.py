from dataclasses import dataclass, field


@dataclass
class ExpansionResult:
    template: str | None = None
    files: list[str] = field(default_factory=list)
    event_spawns: int = 0
    incomplete: bool = False
    removed: bool = False
