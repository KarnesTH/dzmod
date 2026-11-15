from dataclasses import dataclass


@dataclass(frozen=True)
class ModState:
    mod_id: str
    title: str
    local_updated: int
    remote_updated: int

    @property
    def available(self) -> bool:
        """True if the Steam API returned the item."""

        return self.remote_updated is not None

    @property
    def outdated(self) -> bool:
        """True if the remote timestamp is newer than the local ACF timestamp."""

        return self.available and self.remote_updated > self.local_updated
