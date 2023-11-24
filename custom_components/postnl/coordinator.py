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

        for shipment in shipments['trackedShipments']['receiverShipments']:
            _LOGGER.debug('Updating %s', shipment['barcode'])
            track_and_trace_details = await self.hass.async_add_executor_job(jouw_api.track_and_trace, shipment['key'])

            if 'colli' not in track_and_trace_details:
                _LOGGER.debug('No colli found.')
                _LOGGER.debug(track_and_trace_details)
                continue

            colli = track_and_trace_details['colli'][shipment['barcode']]

            data.append(Package(
                key=shipment['barcode'],
                name=shipment.get('title'),
                url=shipment.get('detailsUrl'),
                status_message=colli.get('statusPhase').get('message'),
                delivered=shipment.get('delivered'),
                delivery_date=shipment.get('deliveredTimeStamp', None),
                planned_date=shipment.get('deliveryWindowFrom', None),
                planned_from=shipment.get('deliveryWindowFrom', None),
                planned_to=shipment.get('deliveryWindowTo', None)
            ))

        _LOGGER.debug('Found %d packages', len(data))

        return data
