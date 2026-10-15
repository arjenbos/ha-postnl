"""Configure and reauthenticate a PostNL account through OAuth."""

import logging
from typing import Any

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .account import Account, entry_account_id
from .api import PostNLAuthenticationError, PostNLDataError, PostNLError
from .const import DOMAIN
from .login_api import PostNLLoginAPI

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Validate account identity before creating or updating an entry."""

    DOMAIN = DOMAIN
    reauth_entry: ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return the integration logger."""
        return _LOGGER

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for confirmation before replacing an existing account's tokens."""
        self.reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Present the account reauthentication confirmation."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Verify API access, reject duplicates, and enforce reauth identity."""
        try:
            client = PostNLLoginAPI(
                async_get_clientsession(self.hass), data["token"]["access_token"]
            )
            account = Account.from_userinfo(await client.userinfo())
        except PostNLAuthenticationError:
            return self.async_abort(reason="invalid_auth")
        except PostNLDataError:
            return self.async_abort(reason="invalid_response")
        except PostNLError, ClientError, TimeoutError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(account.account_id)
        data = {**data, "account_id": account.account_id}
        if self.reauth_entry is not None:
            previous = entry_account_id(self.hass, self.reauth_entry)
            if previous is None:
                return self.async_abort(reason="account_identity_unknown")
            if previous != account.account_id:
                return self.async_abort(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self.reauth_entry,
                unique_id=account.account_id,
                data_updates=data,
            )

        self._abort_if_unique_id_configured()
        if any(
            entry_account_id(self.hass, entry) == account.account_id
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(title=account.email or "PostNL", data=data)
