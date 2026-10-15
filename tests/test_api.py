"""Test asynchronous PostNL requests at their HTTP boundaries."""

from unittest.mock import patch

from aiohttp import ClientConnectionError
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.postnl.api import (
    REQUEST_TIMEOUT,
    PostNLAuthenticationError,
    PostNLConnectionError,
    PostNLDataError,
)
from custom_components.postnl.graphql import PostNLGraphql
from custom_components.postnl.jouw_api import PostNLJouwAPI
from custom_components.postnl.login_api import PostNLLoginAPI
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

USERINFO_URL = f"{PostNLLoginAPI.base_url}/profiles/oidc/userinfo"


@pytest.mark.parametrize("tracking", [False, True])
async def test_rest_client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, tracking: bool
) -> None:
    """Send authentication, set bounded timeouts, and preserve session ownership."""
    session = async_get_clientsession(hass)
    if tracking:
        url = f"{PostNLJouwAPI.base_url}/api/trackAndTrace/test%2Fkey?language=nl"
        client = PostNLJouwAPI(session, "test-token")
        payload = {"colli": {}}
    else:
        url = USERINFO_URL
        client = PostNLLoginAPI(session, "test-token")
        payload = {"account_id": "test-account"}
    aioclient_mock.get(url, json=payload)
    with patch.object(session, "request", wraps=session.request) as request:
        result = (
            await client.track_and_trace("test/key")
            if tracking
            else await client.userinfo()
        )
    assert result == payload
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer test-token"
    assert request.call_args.kwargs["timeout"] == REQUEST_TIMEOUT
    assert not session.closed


@pytest.mark.parametrize(
    ("response", "exception"),
    [
        ({"status": 401}, PostNLAuthenticationError),
        ({"status": 403}, PostNLAuthenticationError),
        ({"status": 429}, PostNLConnectionError),
        ({"status": 500}, PostNLConnectionError),
        ({"exc": TimeoutError()}, PostNLConnectionError),
        ({"exc": ClientConnectionError()}, PostNLConnectionError),
        (
            {"text": "not-json", "headers": {"Content-Type": "application/json"}},
            PostNLDataError,
        ),
        ({"json": []}, PostNLDataError),
        ({"json": {"error": "invalid_token"}}, PostNLAuthenticationError),
        ({"json": {"error": "temporarily_unavailable"}}, PostNLDataError),
    ],
)
async def test_rest_failures(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict,
    exception: type[Exception],
) -> None:
    """Never treat an HTTP or payload error as valid account data."""
    aioclient_mock.get(USERINFO_URL, **response)
    with pytest.raises(exception):
        await PostNLLoginAPI(async_get_clientsession(hass), "test-token").userinfo()


@pytest.mark.parametrize("profile", [True, False])
async def test_graphql_client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, profile: bool
) -> None:
    """Submit the expected operation and unwrap GraphQL data."""
    field = "profile" if profile else "trackedShipments"
    payload = {field: {}}
    aioclient_mock.post(PostNLGraphql.endpoint, json={"data": payload})
    client = PostNLGraphql(async_get_clientsession(hass), "test-token")
    assert (await client.profile() if profile else await client.shipments()) == payload
    assert field in aioclient_mock.mock_calls[0][2]["query"]


@pytest.mark.parametrize(
    ("payload", "exception"),
    [
        ({"errors": [{"message": "denied"}]}, PostNLDataError),
        (
            {"errors": [{"extensions": {"code": "UNAUTHENTICATED"}}]},
            PostNLAuthenticationError,
        ),
        ({"errors": "bad response"}, PostNLDataError),
        ({"errors": [None]}, PostNLDataError),
        ({"data": None}, PostNLDataError),
    ],
)
async def test_graphql_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    payload: dict,
    exception: type[Exception],
) -> None:
    """Only explicit authentication errors trigger a credential refresh."""
    aioclient_mock.post(PostNLGraphql.endpoint, json=payload)
    with pytest.raises(exception):
        await PostNLGraphql(async_get_clientsession(hass), "test-token").shipments()
