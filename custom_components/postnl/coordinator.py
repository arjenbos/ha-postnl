import asyncio
import logging
from datetime import timedelta

import requests
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)

from . import AsyncConfigEntryAuth, PostNLGraphql
from .const import DOMAIN
from .jouw_api import PostNLJouwAPI
from .structs.package import Package

_LOGGER = logging.getLogger(__name__)

class PostNLCoordinator(DataUpdateCoordinator):
    data: dict[str, list[Package]]
    graphq_api: PostNLGraphql
    jouw_api: PostNLJouwAPI

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize PostNL coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="PostNL",
            update_interval=timedelta(seconds=90),
        )
        _LOGGER.debug("PostNLCoordinator initialized with update interval: %s", self.update_interval)
        
    async def _async_update_data(self) -> dict[str, list[Package]]:
        _LOGGER.debug("Starting data update for PostNL.")
        try:
            auth: AsyncConfigEntryAuth = self.hass.data[DOMAIN][self.config_entry.entry_id]['auth']
            _LOGGER.debug("Authenticating with PostNL API.")
            await auth.check_and_refresh_token()

            self.graphq_api = PostNLGraphql(auth.access_token)
            self.jouw_api = PostNLJouwAPI(auth.access_token)

            data: dict[str, list[Package]] = {
                'receiver': [],
                'sender': []
            }

            shipments = await self.hass.async_add_executor_job(self.graphq_api.shipments)

            _LOGGER.debug("Shipments fetched: %s", shipments)
            receiver_shipments = [self.transform_shipment(shipment) for shipment in
                                  shipments.get('trackedShipments', {}).get('receiverShipments', [])]
            data['receiver'] = await asyncio.gather(*receiver_shipments)

            sender_shipments = [self.transform_shipment(shipment) for shipment in
                                shipments.get('trackedShipments', {}).get('senderShipments', [])]
            data['sender'] = await asyncio.gather(*sender_shipments)

            _LOGGER.info("Updated PostNL data: %d receiver packages, %d sender packages.", len(data['receiver']), len(data['sender']))

            return data
        except requests.exceptions.RequestException as exception:
            _LOGGER.error("Network error during PostNL data update: %s", exception, exc_info=True)
            raise UpdateFailed("Unable to update PostNL data") from exception

    async def transform_shipment(self, shipment) -> Package:
        _LOGGER.debug('Updating %s', shipment.get('key'))

        try:
            if shipment.get('delivered'):
                _LOGGER.debug('%s already delivered, no need to call jouw.postnl.', shipment.get('key'))

                return Package(
                    key=shipment.get('key'),
                    name=shipment.get('title'),
                    url=shipment.get('detailsUrl'),
                    shipment_type=shipment.get('shipmentType'),
                    status_message="Pakket is bezorgd",
                    delivered=shipment.get('delivered'),
                    delivery_date=shipment.get('deliveredTimeStamp'),
                    delivery_address_type=shipment.get('deliveryAddressType')
                )

            _LOGGER.debug("Fetching Track and Trace details for shipment %s.", shipment['key'])
            track_and_trace_details = await self.hass.async_add_executor_job(self.jouw_api.track_and_trace,
                                                                             shipment['key'])

            if not track_and_trace_details.get('colli'):
                _LOGGER.warning("No colli found for shipment %s. Details: %s", shipment['key'], track_and_trace_details)

            colli = track_and_trace_details.get('colli', {}).get(shipment['barcode'], {})

            status_message = "Unknown"

            if colli:
                _LOGGER.debug("Colli details found for shipment %s: %s", shipment['key'], colli)
                if colli.get("routeInformation"):
                    route_information = colli.get("routeInformation")
                    planned_date = route_information.get("plannedDeliveryTime")
                    planned_from = route_information.get("plannedDeliveryTimeWindow", {}).get("startDateTime")
                    planned_to = route_information.get("plannedDeliveryTimeWindow", {}).get('endDateTime')
                    expected_datetime = route_information.get('expectedDeliveryTime')
                elif colli.get('eta'):
                    planned_date = colli.get('eta', {}).get('start')
                    planned_from = colli.get('eta', {}).get('start')
                    planned_to = colli.get('eta', {}).get('end')
                    expected_datetime = None
                else:
                    planned_date = shipment.get('deliveryWindowFrom', None)
                    planned_from = shipment.get('deliveryWindowFrom', None)
                    planned_to = shipment.get('deliveryWindowTo', None)
                    expected_datetime = None

                status_message = colli.get('statusPhase', {}).get('message', "Unknown")
            else:
                _LOGGER.warning("Barcode not found in colli details for shipment %s.", shipment['key'])
                planned_date = shipment.get('deliveryWindowFrom', None)
                planned_from = shipment.get('deliveryWindowFrom', None)
                planned_to = shipment.get('deliveryWindowTo', None)
                expected_datetime = None

            return Package(
                key=shipment.get('key'),
                name=shipment.get('title'),
                url=shipment.get('detailsUrl'),
                shipment_type=shipment.get('shipmentType'),
                status_message=status_message,
                delivered=shipment.get('delivered'),
                delivery_date=shipment.get('deliveredTimeStamp'),
                delivery_address_type=shipment.get('deliveryAddressType'),
                planned_date=planned_date,
                planned_from=planned_from,
                planned_to=planned_to,
                expected_datetime=expected_datetime
            )
        except requests.exceptions.RequestException as exception:
            _LOGGER.error("Error fetching Track and Trace details for shipment %s: %s", shipment.get('key'), exception, exc_info=True)
            raise UpdateFailed("Unable to update PostNL data") from exception
