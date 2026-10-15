"""Home Assistant fixtures and mocked PostNL service boundaries."""

from collections.abc import Generator
from copy import deepcopy
import json
from pathlib import Path
import time
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.postnl.const import DOMAIN
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def custom_integrations_enabled(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load this repository's custom integration."""


@pytest.fixture
async def application_credentials(hass: HomeAssistant) -> None:
    """Register credentials through Home Assistant's real credential store."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("test-client", "test-secret", "PostNL"),
    )


@pytest.fixture
def token() -> dict:
    """Return synthetic, unexpired OAuth credentials."""
    return {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "expires_at": time.time() + 3600,
    }


@pytest.fixture
def config_entry(hass: HomeAssistant, token: dict) -> MockConfigEntry:
    """Add an OAuth config entry without setting it up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PostNL",
        unique_id="test-account",
        data={"auth_implementation": DOMAIN, "token": token},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def shipments() -> dict:
    """Load a synthetic shipment response shared by integration tests."""
    return json.loads((Path(__file__).parent / "fixtures/shipments.json").read_text())


@pytest.fixture
def mock_api(shipments: dict) -> Generator[MagicMock]:
    """Mock service calls, retaining real auth, coordinator, and entity code."""
    with (
        patch(
            "custom_components.postnl.login_api.PostNLLoginAPI.userinfo",
            return_value={"account_id": "test-account", "email": "test@example.com"},
        ) as userinfo,
        patch(
            "custom_components.postnl.graphql.PostNLGraphql.profile",
            return_value={"profile": {"username": "test@example.com"}},
        ) as profile,
        patch(
            "custom_components.postnl.graphql.PostNLGraphql.shipments",
            side_effect=lambda: deepcopy(shipments),
        ) as shipment_call,
        patch(
            "custom_components.postnl.jouw_api.PostNLJouwAPI.track_and_trace",
            return_value={
                "colli": {
                    "incoming-barcode": {
                        "statusPhase": {"message": "Onderweg"},
                        "eta": {
                            "start": "2026-10-15T12:00:00+02:00",
                            "end": "2026-10-15T14:00:00+02:00",
                        },
                    }
                }
            },
        ) as tracking,
    ):
        api = MagicMock()
        api.userinfo = userinfo
        api.profile = profile
        api.shipments = shipment_call
        api.tracking = tracking
        yield api
