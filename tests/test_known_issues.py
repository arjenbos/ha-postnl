"""Desired behavior for confirmed bugs, pending separate implementation fixes.

Strict xfail markers keep these defects visible without accepting their current
behavior as the contract. Unexpected passes fail CI so fixes remove the markers.
Only assertion failures are expected; unexpected exception types still fail.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from aiohttp import ClientConnectionError
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.postnl.const import DOMAIN, POSTNL_TOKEN_URL

from .helpers import finish_oauth, start_oauth


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="Review #1: setup logs the bearer token"
)
async def test_access_token_is_not_logged(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep secrets out of logs even when integration debug logging is enabled."""
    caplog.set_level(logging.DEBUG, logger="custom_components.postnl")
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.data["token"]["access_token"] not in caplog.text


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Review #2: ClientConnectionError has no status attribute",
)
async def test_oauth_connection_failure_is_retryable(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Retry an OAuth connection failure instead of crashing error handling."""
    mock_api.profile.side_effect = ClientConnectionError("offline")
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Review #4: first refresh is performed in platform setup",
)
async def test_first_refresh_failure_retries_entry(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Retry the whole entry if its initial shipment fetch fails."""
    mock_api.shipments.side_effect = requests.ConnectionError("offline")
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Review #5: account duplicates are not rejected",
)
async def test_duplicate_account_is_rejected(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
) -> None:
    """Prevent two entries from owning the same account entities."""
    hass.config_entries.async_update_entry(config_entry, unique_id="test-account")
    aioclient_mock.post(POSTNL_TOKEN_URL, json=token)
    result = await start_oauth(hass)
    with patch("custom_components.postnl.async_setup_entry", return_value=True):
        result = await finish_oauth(hass, result)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Review #5: reauth does not check account identity",
)
async def test_reauth_rejects_different_account(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
) -> None:
    """Reject credentials for another account without overwriting the entry."""
    hass.config_entries.async_update_entry(config_entry, unique_id="test-account")
    mock_api.userinfo.return_value = {
        "account_id": "other-account",
        "email": "other@example.com",
    }
    aioclient_mock.post(POSTNL_TOKEN_URL, json={**token, "access_token": "other-token"})
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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert config_entry.data["token"]["access_token"] == token["access_token"]


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Review #16: null statusPhase crashes transformation",
)
async def test_null_status_uses_unknown_fallback(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Keep a shipment usable when its optional status is null."""
    mock_api.tracking.return_value = {
        "colli": {"incoming-barcode": {"statusPhase": None}}
    }
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.postnl_delivery")
    assert state is not None
    assert state.state == "1"
    assert state.attributes["enroute"][0]["status_message"] == "Unknown"
