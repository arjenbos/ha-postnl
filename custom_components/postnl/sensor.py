"""Sensor for PostNL packages."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import PostNLCoordinator
from .structs.package import Package

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the PostNL sensor platform."""

    coordinator = PostNLCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()
    userinfo = hass.data[DOMAIN][entry.entry_id]['userinfo']

    # Backwards compatibility support with old sensor names and to support the legacy lovelace.
    unique_id_prefix = "postnl_"
    entity_registry = async_get_entity_registry(hass)
    if entity_registry.async_get_entity_id(
        domain="sensor",
        platform="postnl",
        unique_id="postnl_delivery"
    ) or entity_registry.async_get_entity_id(
        domain="sensor",
        platform="postnl",
        unique_id="postnl_distribution"
    ):
        unique_id_prefix = userinfo.get('account_id') + "_"

    async_add_entities([
        PostNLDelivery(
            coordinator=coordinator,
            postnl_userinfo=userinfo,
            unique_id= unique_id_prefix + "delivery",
            name="PostNL_delivery"
        ),
        PostNLDelivery(
            coordinator=coordinator,
            postnl_userinfo=userinfo,
            name="PostNL_distribution",
            unique_id=unique_id_prefix + "distribution",
            receiver=False
        )
    ])


class PostNLDelivery(CoordinatorEntity, Entity):
    def __init__(self, coordinator, postnl_userinfo, unique_id, name, receiver: bool = True):
        """Initialize the PostNL sensor."""
        super().__init__(coordinator, context=name)
        self.postnl_userinfo = postnl_userinfo
        self._unique_id = unique_id
        self._name: str = name
        self._attributes: dict[str, list[Package]] = {
            'enroute': [],
            'delivered': [],
        }
        self._state = None
        self.receiver: bool = receiver
        self.handle_coordinator_data()

    @property
    def unique_id(self) -> str | None:
        """Return the unique id of the sensor."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.postnl_userinfo.get('account_id'))
            },
            name=self.postnl_userinfo.get('email'),
            manufacturer="PostNL",
        )

    @property
    def name(self) -> str:
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
