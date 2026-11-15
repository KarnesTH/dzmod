from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MapResult:
    mod_id: str
    name: str
    mission: str | None = None
    source: str | None = None
    mission_path: Path | None = None
    reused: bool = False
    warnings: list[str] = field(default_factory=list)
