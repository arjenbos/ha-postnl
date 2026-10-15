"""Provide PostNL application credentials and PKCE authorization."""

import base64
import hashlib
import secrets
from typing import Any

from aiohttp import ClientError

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation

from .const import (
    POSTNL_AUTH_URL,
    POSTNL_CLIENT_ID,
    POSTNL_REDIRECT_URI,
    POSTNL_SCOPE,
    POSTNL_TOKEN_URL,
)


class OAuth2Impl(AuthImplementation):
    """Support the PostNL mobile client's PKCE redirect."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth_domain: str,
        credential: ClientCredential,
        authorization_server: AuthorizationServer,
        code_challenge: str,
        code_verifier: str,
    ) -> None:
        """Initialize the public client and its PKCE verifier."""
        super().__init__(hass, auth_domain, credential, authorization_server)
        self.code_verifier = code_verifier
        self.code_challenge = code_challenge

    @property
    def redirect_uri(self) -> str:
        """Return the provider's registered mobile redirect URI."""
        return POSTNL_REDIRECT_URI

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Include the requested scope and PKCE challenge."""
        return {
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
            "scope": POSTNL_SCOPE,
        }

    async def async_resolve_external_data(self, external_data: Any) -> dict[str, Any]:
        """Exchange the browser callback code using PKCE."""
        try:
            token = await self._token_request(
                {
                    "code": external_data["code"],
                    "code_verifier": self.code_verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": external_data["state"]["redirect_uri"],
                }
            )
        except ValueError:
            raise ClientError("PostNL returned invalid OAuth JSON") from None
        if not isinstance(token, dict):
            raise ClientError("PostNL returned an invalid OAuth response")
        # The base flow logs malformed token dictionaries; validate first so
        # credentials never reach that error path.
        if any(
            not isinstance(token.get(field), str) or not token[field]
            for field in ("access_token", "refresh_token")
        ):
            raise ClientError("PostNL returned invalid OAuth credentials")
        try:
            expires_in = int(token.get("expires_in", 0))
        except TypeError, ValueError:
            raise ClientError("PostNL returned an invalid OAuth expiry") from None
        if expires_in <= 0:
            raise ClientError("PostNL returned an invalid OAuth expiry")
        token["expires_in"] = expires_in
        return token


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return an implementation for PostNL's registered public OAuth client."""
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return OAuth2Impl(
        hass,
        auth_domain,
        ClientCredential(client_id=POSTNL_CLIENT_ID, client_secret=""),
        AuthorizationServer(authorize_url=POSTNL_AUTH_URL, token_url=POSTNL_TOKEN_URL),
        code_challenge=challenge,
        code_verifier=verifier,
    )
