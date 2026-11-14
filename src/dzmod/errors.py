class DzmodError(Exception):
    """Carries a message key and its format values; the CLI resolves both into the localized text."""

    def __init__(self, key: str, **values) -> None:
        super().__init__(key)
        self.key = key
        self.values = values
