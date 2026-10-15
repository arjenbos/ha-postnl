"""Guard invalid provider data, account identity, and bounded polling."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.postnl.api import (
    PostNLAuthenticationError,
    PostNLConnectionError,
    PostNLDataError,
)
from custom_components.postnl.const import DOMAIN, POSTNL_TOKEN_URL
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .helpers import finish_oauth, sensor_entity_id, start_oauth
from .test_sensor import poll


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (PostNLAuthenticationError(), "invalid_auth"),
        (PostNLDataError(), "invalid_response"),
        (PostNLConnectionError(), "cannot_connect"),
    ],
)
async def test_account_validation_in_flow(
    hass: HomeAssistant,
    application_credentials: None,
    mock_api: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
    error: Exception,
    reason: str,
) -> None:
    """Do not save credentials when the account API cannot validate them."""
    mock_api.userinfo.side_effect = error
    aioclient_mock.post(POSTNL_TOKEN_URL, json=token)
    result = await finish_oauth(hass, await start_oauth(hass))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("identity_source", ["data", "device", "unknown"])
async def test_legacy_reauthentication(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
    identity_source: str,
) -> None:
    """Only reauthenticate a legacy entry when its original account is known."""
    hass.config_entries.async_update_entry(config_entry, unique_id=None)
    if identity_source == "data":
        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data, "account_id": "test-account"}
        )
    elif identity_source == "device":
        dr.async_get(hass).async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, "test-account")},
        )
    aioclient_mock.post(POSTNL_TOKEN_URL, json=token)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await start_oauth(hass, result)
    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock(return_value=True)
    ):
        result = await finish_oauth(hass, result)
        await hass.async_block_till_done()
    assert result["reason"] == (
        "account_identity_unknown"
        if identity_source == "unknown"
        else "reauth_successful"
    )


async def test_duplicate_legacy_account(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
) -> None:
    """Detect duplicate legacy entries even before their unique ID is migrated."""
    hass.config_entries.async_update_entry(
        config_entry,
        unique_id=None,
        data={**config_entry.data, "account_id": "test-account"},
    )
    aioclient_mock.post(POSTNL_TOKEN_URL, json=token)
    result = await finish_oauth(hass, await start_oauth(hass))
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("failure", ["auth", "wrong_account", "duplicate"])
async def test_setup_identity_failure(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    failure: str,
) -> None:
    """Reject incorrect identity instead of associating it with old entities."""
    if failure == "auth":
        mock_api.userinfo.side_effect = PostNLAuthenticationError()
    elif failure == "wrong_account":
        mock_api.userinfo.return_value = {"account_id": "other-account"}
    else:
        other = MockConfigEntry(
            domain=DOMAIN, unique_id="other-id", data={"account_id": "test-account"}
        )
        other.add_to_hass(hass)
        hass.config_entries.async_update_entry(other, unique_id=None)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert not er.async_entries_for_config_entry(
        er.async_get(hass), config_entry.entry_id
    )


@pytest.mark.parametrize("account_id", [None, "", 42])
async def test_missing_account_id(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    account_id: object,
) -> None:
    """Retry an invalid account response without creating broken identifiers."""
    mock_api.userinfo.return_value = {"account_id": account_id}
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "invalid", ["root", "list", "item", "key", "barcode", "delivered", "text", "object"]
)
async def test_invalid_shipments(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    shipments: dict,
    invalid: str,
) -> None:
    """Reject malformed data rather than reporting a successful zero count."""
    item = shipments["trackedShipments"]["receiverShipments"][0]
    if invalid == "root":
        mock_api.shipments.side_effect = None
        mock_api.shipments.return_value = {}
    elif invalid == "list":
        shipments["trackedShipments"]["receiverShipments"] = "bad"
    elif invalid == "item":
        shipments["trackedShipments"]["receiverShipments"] = [None]
    elif invalid in ("key", "barcode", "delivered"):
        item[invalid] = None
    elif invalid == "text":
        item["title"] = 42
    else:
        mock_api.tracking.return_value = {"colli": "bad"}
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_nullable_shipments(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    shipments: dict,
) -> None:
    """Handle nullable lists and tracking objects without losing availability."""
    shipments["trackedShipments"]["senderShipments"] = None
    mock_api.tracking.return_value = {"colli": None}
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(sensor_entity_id(hass, "distribution")).state == "0"
    assert hass.states.get(sensor_entity_id(hass, "delivery")).state == "1"


async def test_persistent_auth_failure(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
) -> None:
    """Stop refreshing after a second explicit authentication rejection."""
    mock_api.profile.side_effect = PostNLAuthenticationError()
    aioclient_mock.post(POSTNL_TOKEN_URL, json=token)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert mock_api.profile.call_count == 2
    assert hass.config_entries.flow.async_progress()[0]["context"]["source"] == "reauth"


async def test_oauth_refresh_connection_failure(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
) -> None:
    """Retry OAuth refresh transport failures without requesting new credentials."""
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, "token": {**token, "expires_at": 0}}
    )
    aioclient_mock.post(POSTNL_TOKEN_URL, exc=ClientConnectionError())
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


async def test_poll_auth_failure(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Trigger reauthentication on rejected shipment access during polling."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_api.shipments.side_effect = PostNLAuthenticationError()
    freezer.tick(timedelta(seconds=100))
    await poll(hass)
    assert hass.states.get(sensor_entity_id(hass, "delivery")).state == "unavailable"
    assert hass.config_entries.flow.async_progress()[0]["context"]["source"] == "reauth"


async def test_tracking_concurrency(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    shipments: dict,
) -> None:
    """Limit requests in flight even with many undelivered shipments."""
    template = shipments["trackedShipments"]["receiverShipments"][0]
    shipments["trackedShipments"]["receiverShipments"] = [
        {**deepcopy(template), "key": f"parcel-{n}"} for n in range(12)
    ]
    active = maximum = 0

    async def track(key: str) -> dict:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        active -= 1
        return {"colli": None}

    mock_api.tracking.side_effect = track
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert maximum == 4
    assert hass.states.get(sensor_entity_id(hass, "delivery")).state == "12"


async def test_failure_logging_and_recovery(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log one outage and one recovery instead of one error per poll."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    caplog.clear()
    original = mock_api.shipments.side_effect
    mock_api.shipments.side_effect = PostNLConnectionError()
    for _ in range(2):
        freezer.tick(timedelta(seconds=100))
        await poll(hass)
    failures = [
        record
        for record in caplog.records
        if record.name == "custom_components.postnl.coordinator"
        and record.levelno >= 40
    ]
    assert len(failures) == 1
    mock_api.shipments.side_effect = original
    freezer.tick(timedelta(seconds=100))
    await poll(hass)
    assert caplog.text.count("Fetching PostNL data recovered") == 1


async def test_diagnostics_excludes_private_data(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Return useful operational counts without leaking account or parcel data."""
    from custom_components.postnl.diagnostics import async_get_config_entry_diagnostics

    assert await async_get_config_entry_diagnostics(hass, config_entry) == {
        "loaded": False
    }
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    diagnostic = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostic["packages"]["receiver"] == {"delivered": 1, "enroute": 1}
    for private in [
        "test-account",
        "test@example.com",
        "test-access-token",
        "test-refresh-token",
        "incoming-key",
        "incoming-barcode",
        "example.com",
    ]:
        assert private not in str(diagnostic)


@pytest.mark.parametrize(
    "existing_kind", ["other_device", "unknown_suffix", "collision", "other_platform"]
)
async def test_migration_preserves_unrelated_entities(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    existing_kind: str,
) -> None:
    """Avoid renaming unrelated entities or colliding with a current identifier."""
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={
            (
                DOMAIN,
                "other-account" if existing_kind == "other_device" else "test-account",
            )
        },
    )
    registry = er.async_get(hass)
    unique_id = "unknown" if existing_kind == "unknown_suffix" else "old_delivery"
    entity = registry.async_get_or_create(
        "sensor",
        "other" if existing_kind == "other_platform" else DOMAIN,
        unique_id,
        config_entry=config_entry,
        device_id=device.id,
    )
    if existing_kind == "collision":
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "test-account_delivery",
            config_entry=config_entry,
            device_id=device.id,
        )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(entity.entity_id).unique_id == unique_id
