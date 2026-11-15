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
        "downloads_failed": "{count} mod(s) could not be updated.",
        "login_missing": "No Steam login given. Use --login or set DZMOD_STEAM_LOGIN in {path}.",
        "api_unreachable": "Steam API not reachable: {error}",
        "api_http_error": "Steam API answered with HTTP {code}.",
        "api_invalid_response": "Steam API returned an invalid response.",
        "steamcmd_missing": "SteamCMD not found ('{binary}'). Install SteamCMD or pass its path with --steamcmd.",
        "not_a_server": "{path} is not a DayZ server directory ({binary} not found).",
        "config_missing": "No configuration found. Run dzmod once in a terminal or create {path}.",
        "file_error": "File error at {path}: {error}",
        "setup_intro": (
            "Setting up dzmod.\n"
            "\n"
            "Steam login\n"
            "  Username of a Steam account that owns DayZ.\n"
            "  dzmod does not store a password. On the first download SteamCMD\n"
            "  signs in by itself and remembers the login.\n"
            "\n"
            "Steam Web API key (optional)\n"
            "  Only needed for the Workshop mod list.\n"
            "  Create a key: https://steamcommunity.com/dev/apikey\n"
            "\n"
            "Saved to: {path}\n"
        ),
        "setup_login": "Steam login: ",
        "setup_api_key": "Steam Web API key (optional): ",
        "setup_done": "Saved to {path}.",
        "api_key_missing": "No mod list cached and no Steam Web API key set. Add DZMOD_STEAM_API_KEY to {path}.",
        "api_key_invalid": "Steam rejected the Web API key. Check DZMOD_STEAM_API_KEY.",
        "mod_list_corrupt": "Mod list {path} is damaged. Set a Steam Web API key to reload it.",
        "mod_list_loading": "Loading the Workshop mod list from Steam (only needed once a week) ...",
        "mod_list_progress": "  {loaded} / {total} mods",
        "mod_list_empty": "The Workshop mod list is empty.",
        "col_id": "ID",
        "col_title": "Title",
        "col_updated": "Updated",
        "col_subscriptions": "Subscribers",
        "col_size": "Size",
        "col_created": "Created",
        "col_tags": "Tags",
        "date_format": "%Y-%m-%d",
        "picker_status": "{selected} selected  |  {position} / {total}",
        "picker_help": "Up/Down move  PgUp/PgDn page  Space select  Enter confirm  q cancel",
        "selection_cancelled": "Nothing selected.",
        "ask_collection": "Add the selection to the collection? [y/N] ",
        "yes_answers": "y,yes",
        "ask_collection_name": "Collection name: ",
        "ask_collection_description": "Description (optional): ",
        "collection_created": "Created {path} with {count} mod(s).",
        "collection_extended": "Added {count} mod(s) to {path}.",
        "title_not_unique": "Warning: the title '{title}' exists several times in the Workshop and cannot be resolved from the collection.",
        "collection_missing": "No collection found ({path}).",
        "collection_empty": "The collection {path} contains no mods.",
        "collection_header": "Collection: {name} ({count} mod(s))",
        "mod_not_found": "Not found in the Workshop list, skipped: {title}",
        "mod_ambiguous": "Title is not unique, skipped: {title} ({ids})",
        "invalid_id": "Invalid mod ID: {mod_id}",
        "unavailable_id": "{mod_id} is not available on the Workshop, skipped.",
        "nothing_to_install": "Nothing to install.",
        "install_list": "{count} mod(s) to install:",
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
        "downloads_failed": "{count} Mod(s) konnten nicht aktualisiert werden.",
        "login_missing": "Kein Steam-Login angegeben. --login nutzen oder DZMOD_STEAM_LOGIN in {path} setzen.",
        "api_unreachable": "Steam API nicht erreichbar: {error}",
        "api_http_error": "Steam API hat mit HTTP {code} geantwortet.",
        "api_invalid_response": "Steam API hat eine ungültige Antwort geliefert.",
        "steamcmd_missing": "SteamCMD nicht gefunden ('{binary}'). SteamCMD installieren oder den Pfad mit --steamcmd angeben.",
        "not_a_server": "{path} ist kein DayZ-Server-Verzeichnis ({binary} nicht gefunden).",
        "config_missing": "Keine Konfiguration gefunden. dzmod einmal im Terminal starten oder {path} anlegen.",
        "file_error": "Dateifehler bei {path}: {error}",
        "setup_intro": (
            "dzmod wird eingerichtet.\n"
            "\n"
            "Steam-Login\n"
            "  Benutzername eines Steam-Accounts, der DayZ besitzt.\n"
            "  dzmod speichert kein Passwort. Beim ersten Download meldet sich\n"
            "  SteamCMD selbst an und merkt sich die Anmeldung.\n"
            "\n"
            "Steam-Web-API-Key (optional)\n"
            "  Wird nur für die Mod-Liste aus dem Workshop gebraucht.\n"
            "  Key erstellen: https://steamcommunity.com/dev/apikey\n"
            "\n"
            "Gespeichert wird in: {path}\n"
        ),
        "setup_login": "Steam-Login: ",
        "setup_api_key": "Steam-Web-API-Key (optional): ",
        "setup_done": "Gespeichert in {path}.",
        "api_key_missing": "Keine Mod-Liste vorhanden und kein Steam-Web-API-Key gesetzt. DZMOD_STEAM_API_KEY in {path} eintragen.",
        "api_key_invalid": "Steam hat den Web-API-Key abgelehnt. DZMOD_STEAM_API_KEY prüfen.",
        "mod_list_corrupt": "Mod-Liste {path} ist beschädigt. Mit gesetztem Steam-Web-API-Key wird sie neu geladen.",
        "mod_list_loading": "Lade die Workshop-Mod-Liste von Steam (nur einmal pro Woche nötig) ...",
        "mod_list_progress": "  {loaded} / {total} Mods",
        "mod_list_empty": "Die Workshop-Mod-Liste ist leer.",
        "col_id": "ID",
        "col_title": "Titel",
        "col_updated": "Aktualisiert",
        "col_subscriptions": "Abonnenten",
        "col_size": "Größe",
        "col_created": "Erstellt",
        "col_tags": "Tags",
        "date_format": "%d.%m.%Y",
        "picker_status": "{selected} ausgewählt  |  {position} / {total}",
        "picker_help": "Hoch/Runter bewegen  Bild↑/Bild↓ blättern  Leertaste auswählen  Enter bestätigen  q abbrechen",
        "selection_cancelled": "Nichts ausgewählt.",
        "ask_collection": "Auswahl in die Kollektion aufnehmen? [j/N] ",
        "yes_answers": "j,ja,y,yes",
        "ask_collection_name": "Name der Kollektion: ",
        "ask_collection_description": "Beschreibung (optional): ",
        "collection_created": "{path} mit {count} Mod(s) angelegt.",
        "collection_extended": "{count} Mod(s) zu {path} hinzugefügt.",
        "title_not_unique": "Achtung: Der Titel '{title}' existiert mehrfach im Workshop und kann aus der Kollektion nicht aufgelöst werden.",
        "collection_missing": "Keine Kollektion gefunden ({path}).",
        "collection_empty": "Die Kollektion {path} enthält keine Mods.",
        "collection_header": "Kollektion: {name} ({count} Mod(s))",
        "mod_not_found": "Nicht in der Workshop-Liste gefunden, übersprungen: {title}",
        "mod_ambiguous": "Titel nicht eindeutig, übersprungen: {title} ({ids})",
        "invalid_id": "Ungültige Mod-ID: {mod_id}",
        "unavailable_id": "{mod_id} ist nicht im Workshop verfügbar, übersprungen.",
        "nothing_to_install": "Nichts zu installieren.",
        "install_list": "{count} Mod(s) zu installieren:",
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
