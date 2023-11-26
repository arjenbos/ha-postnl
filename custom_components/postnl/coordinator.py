import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import AsyncConfigEntryAuth, PostNLGraphql
from .const import DOMAIN
from .jouw_api import PostNLJouwAPI
from .structs.package import Package

_LOGGER = logging.getLogger(__name__)


class PostNLCoordinator(DataUpdateCoordinator):

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize PostNL coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="PostNL",
            update_interval=timedelta(seconds=120),
        )

    async def _async_update_data(self) -> list[Package]:
        _LOGGER.debug('Get API data')

        auth: AsyncConfigEntryAuth = self.hass.data[DOMAIN][self.config_entry.entry_id]
        await auth.check_and_refresh_token()

        graphq_api = PostNLGraphql(auth.access_token)
        jouw_api = PostNLJouwAPI(auth.access_token)

        data: list[Package] = []

        shipments = await self.hass.async_add_executor_job(graphq_api.shipments)

        for shipment in shipments.get('trackedShipments', {}).get('receiverShipments', []):
            _LOGGER.debug('Updating %s', shipment.get('barcode'))
            track_and_trace_details = await self.hass.async_add_executor_job(jouw_api.track_and_trace, shipment['key'])

            if not track_and_trace_details.get('colli'):
                _LOGGER.debug('No colli found.')
                _LOGGER.debug(track_and_trace_details)

            colli = track_and_trace_details['colli'].get(shipment['barcode'], {})

            if not colli:
                _LOGGER.debug('Barcode not found in track and trace details.')
                _LOGGER.debug(track_and_trace_details)

            if colli.get("routeInformation"):
                route_information = colli.get("routeInformation")
                planned_date = route_information.get("plannedDeliveryTime")
                planned_from = route_information.get("plannedDeliveryTimeWindow", {}).get("startDateTime")
                planned_to = route_information.get("plannedDeliveryTimeWindow", {}).get('endDateTime')
                expected_datetime = route_information.get('expectedDeliveryTime')
            else:
                planned_date = colli.get('eta', None).get('start')
                planned_from = colli.get('eta', None).get('start')
                planned_to = colli.get('eta', None).get('end')
                expected_datetime = None

            data.append(Package(
                key=shipment.get('key'),
                name=shipment.get('title'),
                url=shipment.get('detailsUrl'),
                status_message=colli.get('statusPhase').get('message'),
                delivered=colli.get('isDelivered'),
                delivery_date=colli.get('deliveryDate'),
                planned_date=planned_date,
                planned_from=planned_from,
                planned_to=planned_to,
                expected_datetime=expected_datetime
            ))

        _LOGGER.debug('Found %d packages', len(data))

        return data
