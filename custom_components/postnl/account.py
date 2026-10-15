"""Validate account identity and resolve identifiers from legacy entries."""

from dataclasses import dataclass
from typing import Self

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .api import JsonObject, PostNLDataError
from .const import DOMAIN


@dataclass(frozen=True, slots=True)
class Account:
    """The stable identity and optional display name of a PostNL account."""

    account_id: str
    email: str | None = None

    @classmethod
    def from_userinfo(cls, data: JsonObject) -> Self:
        """Require a nonempty account identifier before creating entities."""
        account_id = data.get("account_id")
        if not isinstance(account_id, str) or not account_id.strip():
            raise PostNLDataError("PostNL did not return a valid account identifier")
        email = data.get("email")
        return cls(account_id, email if isinstance(email, str) and email else None)


def entry_account_id(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """Resolve identity without accepting a different account during reauth."""
    if entry.unique_id:
        return entry.unique_id
    if account_id := entry.data.get("account_id"):
        return str(account_id)
    identifiers = {
        identifier
        for device in dr.async_entries_for_config_entry(
            dr.async_get(hass), entry.entry_id
        )
        for domain, identifier in device.identifiers
        if domain == DOMAIN
    }
    if len(identifiers) == 1:
        return identifiers.pop()
    return None
