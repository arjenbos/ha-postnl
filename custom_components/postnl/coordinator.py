"""Coordinate bounded, asynchronous PostNL shipment updates."""

import asyncio
from dataclasses import replace
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .account import Account
from .api import JsonObject, PostNLAuthenticationError, PostNLDataError, PostNLError
from .auth import AsyncConfigEntryAuth
from .jouw_api import PostNLJouwAPI
from .structs.package import Package

_LOGGER = logging.getLogger(__name__)


def object_or_empty(value: Any) -> JsonObject:
    """Accept nullable optional objects but reject malformed responses."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PostNLDataError("PostNL returned an invalid object")
    return value


def optional_text(data: JsonObject, key: str) -> str | None:
    """Validate an optional text field from the service."""
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise PostNLDataError("PostNL returned an invalid text field")
    return value


class PostNLCoordinator(DataUpdateCoordinator[dict[str, list[Package]]]):
    """Maintain one shipment snapshot shared by both package sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[PostNLCoordinator],
        auth: AsyncConfigEntryAuth,
        account: Account,
    ) -> None:
        """Initialize reusable API clients and an explicit entry lifecycle."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="PostNL",
            update_interval=timedelta(seconds=90),
            # Time-based retention must expire even when upstream data is unchanged.
            always_update=True,
        )
        self.auth = auth
        self.account = account
        self.jouw_api = PostNLJouwAPI(auth.graphql.session, auth.access_token)
        self._tracking_limit = asyncio.Semaphore(4)

    async def _async_update_data(self) -> dict[str, list[Package]]:
        """Fetch a complete snapshot or let the coordinator report one failure."""
        try:
            async with asyncio.timeout(60):
                await self.auth.check_and_refresh_token()
                self.jouw_api.access_token = self.auth.access_token
                shipments = await self.auth.graphql.shipments()
                if "trackedShipments" not in shipments:
                    raise PostNLDataError("PostNL did not return shipment data")
                tracked = object_or_empty(shipments["trackedShipments"])
                data: dict[str, list[Package]] = {}
                for role in ("receiver", "sender"):
                    items = tracked.get(f"{role}Shipments")
                    if items is None:
                        items = []
                    if not isinstance(items, list) or not all(
                        isinstance(item, dict) for item in items
                    ):
                        raise PostNLDataError(
                            "PostNL returned an invalid shipment list"
                        )
                    results = await asyncio.gather(
                        *(self.transform_shipment(item) for item in items),
                        return_exceptions=True,
                    )
                    packages: list[Package] = []
                    for result in results:
                        if isinstance(result, BaseException):
                            raise result
                        packages.append(result)
                    data[role] = packages
                _LOGGER.debug(
                    "Updated %d incoming and %d outgoing packages",
                    len(data["receiver"]),
                    len(data["sender"]),
                )
                return data
        except PostNLAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain="postnl", translation_key="invalid_auth"
            ) from err
        except (PostNLError, ClientError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain="postnl", translation_key="cannot_connect"
            ) from err

    async def transform_shipment(self, shipment: JsonObject) -> Package:
        """Normalize optional tracking details into the package-card contract."""
        key = shipment.get("key")
        if not isinstance(key, str) or not key:
            raise PostNLDataError("PostNL returned a shipment without a key")
        delivered = shipment.get("delivered")
        if not isinstance(delivered, bool):
            raise PostNLDataError("PostNL returned an invalid delivery flag")
        package = Package(
            key=key,
            name=optional_text(shipment, "title") or "",
            url=optional_text(shipment, "detailsUrl") or "",
            shipment_type=optional_text(shipment, "shipmentType") or "",
            status_message="Pakket is bezorgd" if delivered else "Unknown",
            delivered=delivered,
            delivery_date=optional_text(shipment, "deliveredTimeStamp"),
            delivery_address_type=optional_text(shipment, "deliveryAddressType"),
        )
        if delivered:
            return package
        barcode = shipment.get("barcode")
        if not isinstance(barcode, str) or not barcode:
            raise PostNLDataError("PostNL returned a shipment without a barcode")
        async with self._tracking_limit:
            details = await self.jouw_api.track_and_trace(key)
        colli = object_or_empty(object_or_empty(details.get("colli")).get(barcode))
        route = object_or_empty(colli.get("routeInformation"))
        eta = object_or_empty(colli.get("eta"))
        planned_window = object_or_empty(route.get("plannedDeliveryTimeWindow"))
        expected_window = object_or_empty(route.get("expectedDeliveryTimeWindow"))
        if route:
            planned_date = optional_text(route, "plannedDeliveryTime")
            planned_from = optional_text(planned_window, "startDateTime")
            planned_to = optional_text(planned_window, "endDateTime")
        elif eta:
            planned_date = planned_from = optional_text(eta, "start")
            planned_to = optional_text(eta, "end")
        else:
            planned_date = planned_from = optional_text(shipment, "deliveryWindowFrom")
            planned_to = optional_text(shipment, "deliveryWindowTo")
        return replace(
            package,
            status_message=optional_text(
                object_or_empty(colli.get("statusPhase")), "message"
            )
            or "Unknown",
            planned_date=planned_date,
            planned_from=planned_from,
            planned_to=planned_to,
            expected_datetime=optional_text(route, "expectedDeliveryTime"),
            expected_from=optional_text(expected_window, "startDateTime"),
            expected_to=optional_text(expected_window, "endDateTime"),
            last_update=optional_text(route, "lastUpdate"),
        )


type PostNLConfigEntry = ConfigEntry[PostNLCoordinator]
