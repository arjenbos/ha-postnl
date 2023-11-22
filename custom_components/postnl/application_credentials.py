import base64
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from typing import cast, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.components.application_credentials import AuthImplementation, AuthorizationServer, ClientCredential
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class OAuth2Impl(AuthImplementation):
    """Custom OAuth2 implementation."""

    code_challenge: str | None
    code_verifier: str | None

    def __init__(self, hass: HomeAssistant, auth_domain: str, credential: ClientCredential,
                 authorization_server: AuthorizationServer, code_challenge: str | None, code_verifier: str | None) -> None:

        super().__init__(hass, auth_domain, credential, authorization_server)

        self.code_verifier = code_verifier
        self.code_challenge = code_challenge

    @property
    def redirect_uri(self) -> str:
        return "postnl://login"

    @property
    def extra_authorize_data(self) -> dict:
        return {
            "scope": "profile openid email address phone poa-profiles-api",
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256"
        }

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": external_data["state"]["redirect_uri"],
                "code_verifier": self.code_verifier
            }
        )

async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation for a custom auth implementation."""

    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
    code_verifier = re.sub('[^a-zA-Z0-9]+', '', code_verifier)
    code_verifier, len(code_verifier)

    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
    code_challenge = code_challenge.replace('=', '')
    code_challenge, len(code_challenge)

    return OAuth2Impl(
        hass,
        auth_domain,
        ClientCredential(
            client_id="deb0a372-6d72-4e09-83fe-997beacbd137",
            client_secret=""
        ),
        AuthorizationServer(
            authorize_url="https://login.postnl.nl/101112a0-4a0f-4bbb-8176-2f1b2d370d7c/login/authorize",
            token_url="https://login.postnl.nl/101112a0-4a0f-4bbb-8176-2f1b2d370d7c/login/token"
        ),
        code_challenge=code_challenge,
        code_verifier=code_verifier
    )