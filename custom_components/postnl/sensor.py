"""Sensor for PostNL packages."""
import datetime
import logging
import pprint

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity

from custom_components.postnl import PostNLGraphql
from custom_components.postnl.coordinator import PostNLCoordinator
from custom_components.postnl.jouw_api import PostNLJouwAPI

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the PostNL sensor platform."""

    entities = [
        PostNLDelivery(
            name="PostNL",
            graphq_api=PostNLGraphql(
                entry.data['token']['access_token']
            ),
            jouw_api=PostNLJouwAPI(
                entry.data['token']['access_token']
            )
        )
    ]

    async_add_entities(entities)


class PostNLDelivery(Entity):
    def __init__(self, name, graphq_api: PostNLGraphql, jouw_api: PostNLJouwAPI):
        """Initialize the PostNL sensor."""
        self._name = name + "_delivery"
        self._attributes = {
            'enroute': [],
            'delivered': [],
        }
        self._state = None
        self.graphq_api = graphq_api
        self.jouw_api = jouw_api

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
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:package-variant-closed"

    async def async_update(self):
        """Update device state."""
        shipments = await self.hass.async_add_executor_job(self.graphq_api.shipments)

        self._attributes['enroute'] = []
        self._attributes['delivered'] = []

        for shipment in shipments['trackedShipments']['receiverShipments']:
            track_and_trace_details = await self.hass.async_add_executor_job(self.jouw_api.track_and_trace, shipment['key'])

            colli = track_and_trace_details['colli'][shipment['barcode']]

            if shipment['delivered']:
                self._attributes['delivered'].append({
                    'name': shipment['title'],
                    'url':  shipment['detailsUrl'],
                    'delivery_date': shipment['deliveredTimeStamp'],
                    'status_message': colli['statusPhase']['message']
                })
            else:
                self._attributes['enroute'].append({
                    'name': shipment['title'],
                    'url': shipment['detailsUrl'],
                    'planned_date': shipment['deliveryWindowFrom'],
                    'planned_from': shipment['deliveryWindowFrom'],
                    'planned_to': shipment['deliveryWindowTo'],
                    'status_message': colli['statusPhase']['message']
                })

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