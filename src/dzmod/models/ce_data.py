import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CEData:
    entries: dict[str, dict[str, ET.Element]] = field(default_factory=dict)
    defaults: dict[str, ET.Element] = field(default_factory=dict)
    invalid: list[Path] = field(default_factory=list)
    conflicts: dict[str, list[str]] = field(default_factory=dict)
    chosen_variants: dict[str, str] = field(default_factory=dict)
    skipped_variants: dict[str, list[str]] = field(default_factory=dict)
