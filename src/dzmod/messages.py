import locale
import os

TEXTS = {
    "en": {
        "no_mods": "No mod folders found in {path}.",
        "up_to_date": "up to date",
        "outdated": "outdated",
        "unavailable": "not available on the Workshop",
        "all_current": "All mods are up to date.",
        "updates_found": "{count} mod(s) need an update.",
        "downloading": "Downloading {count} mod(s) via SteamCMD ...",
        "steamcmd_failed": "SteamCMD exited with code {code}.",
        "installed": "Updated {mod_id} {title}",
        "download_failed": "Download failed for {mod_id} {title}",
        "api_error": "Steam API request failed: {error}",
        "login_missing": "No Steam login given. Use --login or set DZMOD_STEAM_LOGIN.",
    },
    "de": {
        "no_mods": "Keine Mod-Ordner in {path} gefunden.",
        "up_to_date": "aktuell",
        "outdated": "veraltet",
        "unavailable": "nicht im Workshop verfügbar",
        "all_current": "Alle Mods sind aktuell.",
        "updates_found": "{count} Mod(s) brauchen ein Update.",
        "downloading": "Lade {count} Mod(s) über SteamCMD ...",
        "steamcmd_failed": "SteamCMD wurde mit Code {code} beendet.",
        "installed": "Aktualisiert {mod_id} {title}",
        "download_failed": "Download fehlgeschlagen für {mod_id} {title}",
        "api_error": "Steam-API-Anfrage fehlgeschlagen: {error}",
        "login_missing": "Kein Steam-Login angegeben. --login nutzen oder DZMOD_STEAM_LOGIN setzen.",
    },
}


class Messages:
    """Selects German texts if LANG/LC_ALL/LC_MESSAGES or the system locale starts with 'de' otherwise english."""

    def __init__(self) -> None:
        candidates = [os.environ.get(name, "") for name in ("LANG", "LC_ALL", "LC_MESSAGES")]
        candidates.append(locale.getlocale()[0] or "")
        language = next((value for value in candidates if value), "")
        self.texts = TEXTS["de"] if language.lower().startswith("de") else TEXTS["en"]

    def get(self, key: str, **values) -> str:
        """Returns the text for `key` formatted with `values`."""

        return self.texts[key].format(**values)
