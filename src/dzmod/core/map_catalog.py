import json
from importlib.resources import files


class MapCatalog:
    """Reads `dzmod/data/maps.json`: the known map mods by Workshop ID with their mission source, mission folder name
    and Expansion template."""

    VANILLA_EXPANSION = {"chernarusplus": "Chernarus", "enoch": "Enoch"}
    VANILLA_MISSION = "dayzOffline.chernarusplus"

    def __init__(self) -> None:
        self.maps: dict[str, dict] = json.loads(
            files("dzmod").joinpath("data", "maps.json").read_text(encoding="utf-8")
        )

    def is_map(self, mod_id: str) -> bool:
        """True if the Workshop ID belongs to a known map mod."""

        return mod_id in self.maps

    def missions(self, mod_id: str) -> list[str]:
        """Returns all mission folder names a map mod can use (several for maps with variants)."""

        mission = self.maps[mod_id].get("mission")
        if isinstance(mission, dict):
            return list(mission.values())
        return [mission] if mission else []

    def owns_mission(self, mod_id: str, template: str | None) -> bool:
        """True if `template` is one of the map's mission folders (case-insensitive). For maps without a known mission
        name (manual source) the map name has to be part of the template's terrain."""

        if not template:
            return False
        missions = self.missions(mod_id)
        if missions:
            return template.lower() in (mission.lower() for mission in missions)
        return self.maps[mod_id]["name"].lower() in template.rsplit(".", 1)[-1].lower()

    def map_for_mission(self, template: str | None) -> str | None:
        """Returns the Workshop ID of the map mod that owns the mission `template`."""

        return next((mod_id for mod_id in self.maps if self.owns_mission(mod_id, template)), None)

    def expansion_template(self, template: str | None) -> str | None:
        """Returns the Expansion template path (below `Template/`) for the mission `template`: from the map mod using
        that mission (with `{variant}` replaced by the mission's variant) or, for vanilla missions, by terrain."""

        if not template:
            return None

        mod_id = self.map_for_mission(template)
        if mod_id:
            expansion = self.maps[mod_id].get("expansion")
            mission = self.maps[mod_id].get("mission")
            if expansion and isinstance(mission, dict):
                variant = next(name for name, folder in mission.items() if folder.lower() == template.lower())
                return expansion.format(variant=variant)
            return expansion

        return self.VANILLA_EXPANSION.get(template.rsplit(".", 1)[-1].lower())
