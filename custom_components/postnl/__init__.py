import logging
import time

import requests
import urllib3
from aiohttp.client_exceptions import ClientError, ClientResponseError
from gql.transport.exceptions import TransportQueryError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (ConfigEntryNotReady, HomeAssistantError)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session, async_get_config_entry_implementation)

from .const import DOMAIN, PLATFORMS
from .graphql import PostNLGraphql
from .login_api import PostNLLoginAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> True:
    """Set up PostNL from config entry."""
    _LOGGER.debug("Setup Entry PostNL")

    hass.data.setdefault(DOMAIN, {})

    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    auth = AsyncConfigEntryAuth(session)

    try:
        await auth.check_and_refresh_token()
    except requests.exceptions.ConnectionError as exception:
        raise ConfigEntryNotReady("Unable to retrieve oauth data from PostNL") from exception

    hass.data[DOMAIN][entry.entry_id] = {
        'auth': auth
    }

    _LOGGER.debug('Using access token: %s', auth.access_token)

    postnl_login_api = PostNLLoginAPI(auth.access_token)

    try:
        userinfo = await hass.async_add_executor_job(postnl_login_api.userinfo)
    except (requests.exceptions.RequestException, urllib3.exceptions.MaxRetryError) as exception:
        raise ConfigEntryNotReady("Unable to retrieve user information from PostNL.") from exception

    if "error" in userinfo:
        raise ConfigEntryNotReady("Error in retrieving user information from PostNL.")

    hass.data[DOMAIN][entry.entry_id]['userinfo'] = userinfo

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
    ):
        if (
                device_entry.identifiers == {(DOMAIN, userinfo.get('account_id'))}
        ):
            _LOGGER.debug(
                "Migrating entry %s", device_entry.identifiers
            )
            for entity_entry in er.async_entries_for_device(
                    entity_registry, device_entry.id, True
            ):
                _LOGGER.debug('Migrating entity: %s', entity_entry.unique_id)
                if entity_entry.unique_id.startswith(userinfo.get('account_id')):
                    continue

                unique_id_parts = entity_entry.unique_id.split("_")
                entity_new_unique_id = userinfo.get('account_id') + "_" + (
                    unique_id_parts[1] if len(unique_id_parts) > 1 else unique_id_parts[0])
                _LOGGER.debug('New unique ID for entity: %s', entity_new_unique_id)
                entity_registry.async_update_entity(
                    entity_id=entity_entry.entity_id, new_unique_id=entity_new_unique_id
                )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload PostNL config entry."""
    _LOGGER.debug('Reloading PostNL integration')
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


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

    async def force_refresh_expire(self):
        _LOGGER.debug('Force token refresh')
        self.oauth_session.token["expires_at"] = time.time() - 600

    async def check_and_refresh_token(self) -> str:
        """Check the token."""

        try:
            await self.oauth_session.async_ensure_token_valid()
            graphql = PostNLGraphql(self.access_token)
            await self.oauth_session.hass.async_add_executor_job(graphql.profile)

        except (ClientResponseError, ClientError) as exception:
            _LOGGER.debug("API error: %s", exception)
            if exception.status == 400:
                self.oauth_session.config_entry.async_start_reauth(
                    self.oauth_session.hass
                )

            raise HomeAssistantError(exception) from exception
        except TransportQueryError as exception:
            _LOGGER.debug("GraphQL error: %s", exception)

            await self.force_refresh_expire()
            await self.oauth_session.async_ensure_token_valid()

        return self.access_token
