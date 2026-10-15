"""Refresh PostNL tokens through Home Assistant's OAuth helper."""

import time

from aiohttp import ClientError, ClientSession

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
)

from .api import PostNLAuthenticationError, PostNLConnectionError
from .graphql import PostNLGraphql


class AsyncConfigEntryAuth:
    """Keep a reusable API client synchronized with the config-entry token."""

    def __init__(self, oauth_session: OAuth2Session, session: ClientSession) -> None:
        """Initialize auth without creating an HTTP session."""
        self.oauth_session = oauth_session
        self.graphql = PostNLGraphql(session, self.access_token)

    @property
    def access_token(self) -> str:
        """Return the currently persisted access token."""
        return str(self.oauth_session.token["access_token"])

    async def _ensure_token(self) -> None:
        """Classify OAuth helper errors without assuming a status attribute."""
        try:
            await self.oauth_session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain="postnl", translation_key="invalid_auth"
            ) from err
        except (ClientError, TimeoutError) as err:
            raise PostNLConnectionError(
                "Unable to refresh PostNL authentication"
            ) from err
        self.graphql.access_token = self.access_token

    async def check_and_refresh_token(self) -> str:
        """Refresh a rejected access token once, then require reauthentication."""
        await self._ensure_token()
        try:
            await self.graphql.profile()
        except PostNLAuthenticationError:
            entry = self.oauth_session.config_entry
            self.oauth_session.hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    "token": {
                        **self.oauth_session.token,
                        "expires_at": time.time() - 1,
                    },
                },
            )
            await self._ensure_token()
            try:
                await self.graphql.profile()
            except PostNLAuthenticationError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain="postnl", translation_key="invalid_auth"
                ) from err
        return self.access_token
