"""Sensor for PostNL packages."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .calendar import PostNLCalendar
from .coordinator import PostNLCoordinator
from .structs.package import Package

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the PostNL sensor platform."""

    coordinator = PostNLCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()

    async_add_entities([
        PostNLDelivery(
            coordinator=coordinator,
            name="PostNL_delivery"
        ),
        PostNLDelivery(
            coordinator=coordinator,
            name="PostNL_distribution",
            receiver=False
        )
    ])


class PostNLDelivery(CoordinatorEntity[PostNLCoordinator], Entity):
    def __init__(self, coordinator, name, receiver: bool = True):
        """Initialize the PostNL sensor."""
        super().__init__(coordinator, context=name)
        self._name: str = name
        self._attributes: dict[str, list[Package]] = {
            'enroute': [],
            'delivered': [],
        }
        self._state = None
        self.receiver: bool = receiver
        self.handle_coordinator_data()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'packages'

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:package-variant-closed"

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug('Updating sensor %s', self.name)

        self.handle_coordinator_data()

        super()._handle_coordinator_update()

    def handle_coordinator_data(self):
        self._attributes['delivered'] = []
        self._attributes['enroute'] = []

        if self.receiver:
            coordinator_data = self.coordinator.data['receiver']
        else:
            coordinator_data = self.coordinator.data['sender']

        for package in coordinator_data:
            if package.delivered:
                self._attributes['delivered'].append(vars(package))
            else:
                self._attributes['enroute'].append(vars(package))

        self._state = len(self._attributes['enroute'])
