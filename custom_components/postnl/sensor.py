"""Sensor for PostNL packages."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.postnl.coordinator import PostNLCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the PostNL sensor platform."""

    coordinator = PostNLCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()

    async_add_entities([
        PostNLDelivery(
            coordinator=coordinator,
            name="PostNL_delivery"
        )
    ])


class PostNLDelivery(CoordinatorEntity, Entity):
    def __init__(self, coordinator, name):
        """Initialize the PostNL sensor."""
        super().__init__(coordinator, context=name)
        self._name = name
        self._attributes = {
            'enroute': [],
            'delivered': [],
        }
        self._state = None

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

        self.async_write_ha_state()

    def handle_coordinator_data(self):
        self._attributes['delivered'] = []
        self._attributes['enroute'] = []

        for package in self.coordinator.data:
            if package.delivered:
                self._attributes['delivered'].append(vars(package))
            else:
                self._attributes['enroute'].append(vars(package))

        self._state = len(self._attributes['enroute'])


class PostNLDistribution(Entity):
    def __init__(self, api, name):
        """Initialize the PostNL sensor."""
        self._name = name + "_distribution"
        self._attributes = {
            'enroute': [],
            'delivered': [],
        }
        self._state = None
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor."""
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
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:package-variant-closed"

    def update(self):
        """Update device state."""
        shipments = self._api.get_distribution()

        self._attributes['enroute'] = []
        self._attributes['delivered'] = []

        for shipment in shipments:
            if shipment.delivery_date is None:
                self._attributes['enroute'].append(vars(shipment))
            else:
                self._attributes['delivered'].append(vars(shipment))

        self._state = len(self._attributes['enroute'])