"""Test config-entry setup, retries, migrations, and unloading."""

from unittest.mock import MagicMock, patch

from aiohttp import ClientConnectionError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.postnl.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .helpers import sensor_entity_id


async def test_setup_and_unload(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Create sensors and registry records, then unload through Core."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, config_entry.entry_id)
    assert {entity.unique_id for entity in entities} == {
        "test-account_delivery",
        "test-account_distribution",
    }
    devices = dr.async_entries_for_config_entry(
        dr.async_get(hass), config_entry.entry_id
    )
    assert len(devices) == 1
    assert devices[0].identifiers == {(DOMAIN, "test-account")}
    assert devices[0].manufacturer == "PostNL"
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    for entity in entities:
        assert hass.states.get(entity.entity_id).state == "unavailable"


@pytest.mark.parametrize(
    ("endpoint", "error"),
    [
        ("profile", ClientConnectionError("offline")),
        ("userinfo", TimeoutError("timeout")),
        ("userinfo", ClientConnectionError("offline")),
    ],
)
async def test_setup_connection_failure(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    endpoint: str,
    error: Exception,
) -> None:
    """Leave transient setup failures retryable instead of marking them loaded."""
    getattr(mock_api, endpoint).side_effect = error
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not er.async_entries_for_config_entry(
        er.async_get(hass), config_entry.entry_id
    )


async def test_userinfo_error(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Do not create entities from an error response."""
    mock_api.userinfo.return_value = {"error": "temporarily_unavailable"}
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "old_unique_id", ["old_delivery", "delivery", "test-account_delivery"]
)
async def test_migrate_entity_unique_id(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    old_unique_id: str,
) -> None:
    """Preserve an existing entity ID while migrating its account identifier."""
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "test-account")}
    )
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id,
        config_entry=config_entry,
        device_id=device.id,
        suggested_object_id="my_parcels",
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(entity.entity_id).unique_id == "test-account_delivery"
    assert hass.states.get(entity.entity_id).state == "1"


async def test_failed_unload_keeps_entry_loaded(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Keep the entry usable when a platform cannot be unloaded."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert hass.states.get(sensor_entity_id(hass, "delivery")).state == "1"
