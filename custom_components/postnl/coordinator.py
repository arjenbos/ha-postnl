import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PostNLGraphql

_LOGGER = logging.getLogger(__name__)


class PostNLCoordinator(DataUpdateCoordinator):

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="PostNL",
            update_interval=timedelta(seconds=60),
        )

        self.graphq_api = PostNLGraphql(
            self.config_entry.data['token']['access_token']
        )

    async def _async_update_data(self):
        shipments = []

        _LOGGER.debug(self.data)

        return shipments
