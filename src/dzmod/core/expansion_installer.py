import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from dzmod.core.economy_core import EconomyCore
from dzmod.core.github_archive import GitHubArchive
from dzmod.models.expansion_result import ExpansionResult
from dzmod.utils.errors import DzmodError


class ExpansionInstaller:
    """Adds the Expansion CE to a mission from the official Expansion mission templates: the `expansion_ce` folder,
    its `<ce>` block in cfgeconomycore.xml and the event spawns in cfgeventspawns.xml between dzmod markers."""

    REPO = "ExpansionModTeam/DayZ-Expansion-Missions"
    FOLDER = "expansion_ce"
    MARK_START = "<!-- dzmod:expansion:start -->"
    MARK_END = "<!-- dzmod:expansion:end -->"
    MARKED_BLOCK = re.compile(rf"[ \t]*{re.escape(MARK_START)}.*?{re.escape(MARK_END)}[ \t]*\n?", re.DOTALL)

    def __init__(self, mission_dir: Path) -> None:
        self.mission_dir = mission_dir
        self.economy = EconomyCore(mission_dir)
        self.event_spawns = mission_dir / "cfgeventspawns.xml"

    @property
    def installed(self) -> bool:
        """True if the mission already has an `expansion_ce` folder."""

        return (self.mission_dir / self.FOLDER).is_dir()

    def install(self, template: str) -> ExpansionResult:
        """Copies `Template/<template>/expansion_ce` into the mission (replacing an existing one), registers the
        template's `<ce>` blocks and writes its event spawns into the marked block. Raises DzmodError if the template
        does not exist."""

        source = GitHubArchive(self.REPO).get() / "Template" / template
        if not (source / self.FOLDER).is_dir():
            raise DzmodError("expansion_template_missing", template=template)

        target = self.mission_dir / self.FOLDER
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source / self.FOLDER, target)

        result = ExpansionResult(template=template, incomplete=template.startswith("0_INCOMPLETE"))

        core = ET.parse(source / "cfgeconomycore.xml").getroot()
        for ce in core.iter("ce"):
            files = [(file.get("name"), file.get("type")) for file in ce.iter("file")]
            self.economy.upsert(ce.get("folder"), files)
            result.files += [name for name, _ in files]

        spawns_file = source / "cfgeventspawns.xml"
        if spawns_file.is_file() and self.event_spawns.is_file():
            events = ET.parse(spawns_file).getroot().findall("event")
            self._write_event_spawns(events)
            result.event_spawns = len(events)

        return result

    def remove(self) -> bool:
        """Deletes the `expansion_ce` folder, its `<ce>` block and the marked event spawn block. Returns True if
        anything was removed."""

        removed = False
        if self.installed:
            shutil.rmtree(self.mission_dir / self.FOLDER)
            removed = True
        if self.economy.exists and self.economy.remove(self.FOLDER):
            removed = True
        if self.event_spawns.is_file():
            text = self.event_spawns.read_text(encoding="utf-8")
            new_text, count = self.MARKED_BLOCK.subn("", text, count=1)
            if count:
                self.event_spawns.write_text(new_text, encoding="utf-8")
                removed = True
        return removed

    def _write_event_spawns(self, events: list[ET.Element]) -> None:
        """Replaces the marked block in cfgeventspawns.xml or inserts it before `</eventposdef>`. Raises
        DzmodError if the closing tag is missing."""

        lines = [f"\t{self.MARK_START}"]
        for event in events:
            ET.indent(event, space="\t", level=1)
            lines.append("\t" + ET.tostring(event, encoding="unicode").rstrip())
        lines.append(f"\t{self.MARK_END}\n")
        block = "\n".join(lines)

        text = self.event_spawns.read_text(encoding="utf-8")
        if self.MARKED_BLOCK.search(text):
            text = self.MARKED_BLOCK.sub(lambda _: block, text, count=1)
        else:
            end = text.rfind("</eventposdef>")
            if end < 0:
                raise DzmodError("event_spawns_invalid", path=self.event_spawns)
            prefix = text[:end] if text[:end].endswith("\n") else text[:end] + "\n"
            text = prefix + block + text[end:]

        self.event_spawns.write_text(text, encoding="utf-8")
