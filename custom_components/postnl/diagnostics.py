"""Provide diagnostics without account details or shipment payloads."""

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .coordinator import PostNLConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PostNLConfigEntry
) -> dict[str, Any]:
    """Return operational counts without tokens, identifiers, URLs, or email."""
    if entry.state is not ConfigEntryState.LOADED:
        return {"loaded": False}
    coordinator = entry.runtime_data
    return {
        "loaded": True,
        "last_update_success": coordinator.last_update_success,
        "update_interval_seconds": 90,
        "tracking_concurrency": 4,
        "packages": {
            role: {
                "delivered": sum(package.delivered for package in packages),
                "enroute": sum(not package.delivered for package in packages),
            }
            for role, packages in coordinator.data.items()
        },
    }
