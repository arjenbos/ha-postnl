"""Assert entity state and polling behavior through Home Assistant."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
import requests
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from .helpers import sensor_entity_id


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the entry and wait for platform tasks."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def poll(hass: HomeAssistant) -> None:
    """Fire timers at the current frozen time without sleeping."""
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_package_sensors(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Expose incoming/outgoing counts and the package-card attribute contract."""
    await setup_entry(hass, config_entry)
    incoming = hass.states.get(sensor_entity_id(hass, "delivery"))
    outgoing = hass.states.get(sensor_entity_id(hass, "distribution"))
    assert incoming.state == "1"
    assert outgoing.state == "0"
    assert incoming.attributes["unit_of_measurement"] == "packages"
    assert incoming.attributes["icon"] == "mdi:package-variant-closed"
    package = incoming.attributes["enroute"][0]
    assert package["key"] == "incoming-key"
    assert package["status_message"] == "Onderweg"
    assert package["planned_from"] == "2026-10-15T12:00:00+02:00"
    assert package["planned_to"] == "2026-10-15T14:00:00+02:00"
    assert incoming.attributes["delivered"][0]["key"] == "delivered-key"
    assert outgoing.attributes["delivered"][0]["key"] == "outgoing-key"
    # Delivered shipments must not incur another tracking request.
    mock_api.tracking.assert_called_once_with("incoming-key")


@pytest.mark.parametrize("failure_endpoint", ["shipments", "tracking"])
async def test_poll_failure_and_recovery(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    failure_endpoint: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Mark both sensors unavailable after failure and recover on the next poll."""
    await setup_entry(hass, config_entry)
    endpoint = getattr(mock_api, failure_endpoint)
    original = endpoint.side_effect
    endpoint.side_effect = requests.ConnectionError("offline")
    freezer.tick(timedelta(seconds=100))
    await poll(hass)
    assert hass.states.get(sensor_entity_id(hass, "delivery")).state == "unavailable"
    assert (
        hass.states.get(sensor_entity_id(hass, "distribution")).state == "unavailable"
    )
    endpoint.side_effect = original
    freezer.tick(timedelta(seconds=100))
    await poll(hass)
    assert hass.states.get(sensor_entity_id(hass, "delivery")).state == "1"
    assert hass.states.get(sensor_entity_id(hass, "distribution")).state == "0"


async def test_delivered_update_clears_old_attributes(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    shipments: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Move a package between lists and remove it when it disappears upstream."""
    await setup_entry(hass, config_entry)
    shipments["trackedShipments"]["receiverShipments"][0]["delivered"] = True
    freezer.tick(timedelta(seconds=100))
    await poll(hass)
    state = hass.states.get(sensor_entity_id(hass, "delivery"))
    assert state.state == "0"
    assert state.attributes["enroute"] == []
    assert len(state.attributes["delivered"]) == 2
    shipments["trackedShipments"]["receiverShipments"] = []
    freezer.tick(timedelta(seconds=100))
    await poll(hass)
    state = hass.states.get(sensor_entity_id(hass, "delivery"))
    assert state.attributes["delivered"] == []
    assert state.attributes["enroute"] == []


@pytest.mark.parametrize(
    ("colli", "expected"),
    [
        (
            {},
            {"status_message": "Unknown", "planned_date": "2026-10-15T10:00:00+02:00"},
        ),
        (
            {"statusPhase": {"message": "Sorting"}},
            {"status_message": "Sorting", "planned_from": "2026-10-15T10:00:00+02:00"},
        ),
        (
            {
                "routeInformation": {
                    "plannedDeliveryTime": "2026-10-15T12:00:00+02:00",
                    "plannedDeliveryTimeWindow": {
                        "startDateTime": "planned-start",
                        "endDateTime": "planned-end",
                    },
                    "expectedDeliveryTime": "expected",
                    "expectedDeliveryTimeWindow": {
                        "startDateTime": "expected-start",
                        "endDateTime": "expected-end",
                    },
                    "lastUpdate": "updated",
                }
            },
            {
                "planned_from": "planned-start",
                "planned_to": "planned-end",
                "expected_datetime": "expected",
                "expected_from": "expected-start",
                "expected_to": "expected-end",
                "last_update": "updated",
            },
        ),
    ],
)
async def test_tracking_delivery_windows(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    colli: dict,
    expected: dict,
) -> None:
    """Expose route information and fall back to shipment delivery windows."""
    mock_api.tracking.return_value = {"colli": {"incoming-barcode": colli}}
    await setup_entry(hass, config_entry)
    package = hass.states.get(sensor_entity_id(hass, "delivery")).attributes["enroute"][
        0
    ]
    for key, value in expected.items():
        assert package[key] == value
