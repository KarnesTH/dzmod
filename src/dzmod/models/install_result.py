from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class InstallResult:
    mod_id: str
    title: str
    keys: list[str] = field(default_factory=list)
    ce_folder: str | None = None
    ce_files: list[tuple[str, str, int]] = field(default_factory=list)
    invalid: list[Path] = field(default_factory=list)
    conflicts: dict[str, list[str]] = field(default_factory=dict)
    chosen_variants: dict[str, str] = field(default_factory=dict)
    skipped_variants: dict[str, list[str]] = field(default_factory=dict)
    economy_error: str | None = None
