"""Test token refresh through the config-entry lifecycle."""

import time
from unittest.mock import MagicMock

import pytest
from gql.transport.exceptions import TransportQueryError
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.postnl.const import POSTNL_TOKEN_URL


@pytest.mark.parametrize("expired", [True, False])
async def test_refresh_token(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
    expired: bool,
) -> None:
    """Persist a refreshed token for expiry or a rejected profile request."""
    if expired:
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                "token": {**token, "expires_at": time.time() - 1},
            },
        )
    else:
        mock_api.profile.side_effect = [TransportQueryError("Token expired"), {}]
    aioclient_mock.post(
        POSTNL_TOKEN_URL, json={**token, "access_token": "refreshed-token"}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.data["token"]["access_token"] == "refreshed-token"
    assert config_entry.data["token"]["expires_at"] > time.time()
    request = aioclient_mock.mock_calls[0][2]
    assert request["grant_type"] == "refresh_token"
    assert request["refresh_token"] == "test-refresh-token"


async def test_refresh_rejected_starts_reauth(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
) -> None:
    """Ask for reauthentication when PostNL rejects a refresh token."""
    hass.config_entries.async_update_entry(
        config_entry,
        data={**config_entry.data, "token": {**token, "expires_at": time.time() - 1}},
    )
    aioclient_mock.post(POSTNL_TOKEN_URL, status=400, json={"error": "invalid_grant"})
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id
