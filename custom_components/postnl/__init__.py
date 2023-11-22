import logging
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .graphql import PostNLGraphql

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> True:
    """Set up Alpha Innotec from config entry."""
    _LOGGER.debug("Setup Entry PostNL")

    postnl_api = PostNLGraphql(
        entry.data['token']['access_token']
    )

    profile = await hass.async_add_executor_job(postnl_api.profile)
    _LOGGER.debug(profile)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {}


#    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
