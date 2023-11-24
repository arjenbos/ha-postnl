import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import async_get_config_entry_implementation, OAuth2Session

from .login_api import PostNLLoginAPI
from .const import DOMAIN, PLATFORMS
from .graphql import PostNLGraphql
from aiohttp.client_exceptions import ClientError, ClientResponseError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> True:
    """Set up PostNL from config entry."""
    _LOGGER.debug("Setup Entry PostNL")

    hass.data.setdefault(DOMAIN, {})

    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    auth = AsyncConfigEntryAuth(session)
    await auth.check_and_refresh_token()

    hass.data[DOMAIN][entry.entry_id] = auth

    _LOGGER.debug('Using access token: %s', auth.access_token)

    postnl_login_api = PostNLLoginAPI(auth.access_token)
    userinfo = await hass.async_add_executor_job(postnl_login_api.userinfo)

    if "error" in userinfo:
        raise ConfigEntryNotReady

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


class AsyncConfigEntryAuth:
    """Provide PostNL authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        oauth2_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize PostNL Auth."""
        self.oauth_session = oauth2_session

    @property
    def access_token(self) -> str:
        """Return the access token."""
        return self.oauth_session.token[CONF_ACCESS_TOKEN]

    async def check_and_refresh_token(self) -> str:
        """Check the token."""

        try:
            await self.oauth_session.async_ensure_token_valid()
        except (ClientResponseError, ClientError) as ex:
            if (
                self.oauth_session.config_entry.state
                is ConfigEntryState.SETUP_IN_PROGRESS
            ):
                if isinstance(ex, ClientResponseError) and 400 <= ex.status < 500:
                    raise ConfigEntryAuthFailed(
                        "OAuth session is not valid, reauth required"
                    ) from ex
                raise ConfigEntryNotReady from ex
            if hasattr(ex, "status") and ex.status == 400:
                self.oauth_session.config_entry.async_start_reauth(
                    self.oauth_session.hass
                )
            raise HomeAssistantError(ex) from ex

        return self.access_token
