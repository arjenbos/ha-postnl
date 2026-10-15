"""Exercise OAuth and reauthentication through Home Assistant's flow manager."""

import base64
import hashlib
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientConnectionError
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from yarl import URL

from custom_components.postnl.const import (
    DOMAIN,
    POSTNL_AUTH_URL,
    POSTNL_CLIENT_ID,
    POSTNL_REDIRECT_URI,
    POSTNL_SCOPE,
    POSTNL_TOKEN_URL,
)

from .helpers import finish_oauth, start_oauth


async def test_oauth_creates_entry(
    hass: HomeAssistant,
    application_credentials: None,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
) -> None:
    """Exchange a PKCE code and persist the resulting OAuth entry."""
    aioclient_mock.post(POSTNL_TOKEN_URL, json=token)
    result = await start_oauth(hass)
    url = URL(result["url"])
    assert str(url.with_query(None)) == POSTNL_AUTH_URL
    assert url.query["client_id"] == POSTNL_CLIENT_ID
    assert url.query["redirect_uri"] == POSTNL_REDIRECT_URI
    assert url.query["scope"] == POSTNL_SCOPE
    assert url.query["code_challenge_method"] == "S256"
    assert url.query["state"]

    with patch("custom_components.postnl.async_setup_entry", return_value=True):
        result = await finish_oauth(hass, result)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"]["token"]["access_token"] == token["access_token"]
    request = aioclient_mock.mock_calls[0][2]
    assert request["code"] == "test-code"
    assert request["redirect_uri"] == POSTNL_REDIRECT_URI
    assert request["client_id"] == POSTNL_CLIENT_ID
    assert "client_secret" not in request
    verifier = request["code_verifier"]
    assert 43 <= len(verifier) <= 128
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    assert challenge.decode().rstrip("=") == url.query["code_challenge"]


async def test_missing_credentials(hass: HomeAssistant) -> None:
    """Explain why OAuth cannot start without application credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        ({"status": 401, "json": {"error": "invalid_client"}}, "oauth_unauthorized"),
        ({"status": 500, "json": {}}, "oauth_failed"),
        ({"exc": ClientConnectionError()}, "oauth_failed"),
        ({"exc": TimeoutError()}, "oauth_timeout"),
        ({"json": {"access_token": "invalid"}}, "oauth_error"),
        ({"json": {"expires_in": "invalid"}}, "oauth_error"),
    ],
)
async def test_oauth_failure(
    hass: HomeAssistant,
    application_credentials: None,
    aioclient_mock: AiohttpClientMocker,
    response: dict,
    reason: str,
) -> None:
    """Reject failed exchanges without creating an unusable entry."""
    aioclient_mock.post(POSTNL_TOKEN_URL, **response)
    result = await finish_oauth(hass, await start_oauth(hass))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_user_rejects_authorization(
    hass: HomeAssistant,
    application_credentials: None,
) -> None:
    """Allow the user to cancel at the provider without creating an entry."""
    result = await start_oauth(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"error": "access_denied"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "user_rejected_authorize"


async def test_reauth_updates_existing_entry(
    hass: HomeAssistant,
    application_credentials: None,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    token: dict,
) -> None:
    """Confirm reauth, replace the token, and reload without creating a duplicate."""
    aioclient_mock.post(POSTNL_TOKEN_URL, json={**token, "access_token": "new-token"})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await start_oauth(hass, result)
    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock(return_value=True)
    ) as reload_entry:
        result = await finish_oauth(hass, result)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["token"]["access_token"] == "new-token"
    assert hass.config_entries.async_entries(DOMAIN) == [config_entry]
    reload_entry.assert_awaited_once_with(config_entry.entry_id)
