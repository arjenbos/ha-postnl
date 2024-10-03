import logging
import time

import requests
import urllib3
from aiohttp.client_exceptions import ClientError, ClientResponseError
from gql.transport.exceptions import TransportQueryError
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (ConfigEntryNotReady, HomeAssistantError)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session, async_get_config_entry_implementation)

from .const import DOMAIN, PLATFORMS, VERSION
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # if not hass.http.app.router.get('/postnl/lovelace'):
    #     hass.http.register_static_path(
    #         url_path='/postnl/lovelace',
    #         path=hass.config.path("custom_components/postnl/lovelace"),
    #         cache_headers=True
    #     )

    if not await path_registered(hass=hass, url='/postnl/lovelace.js'):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path='/postnl/lovelace.js',
                path=hass.config.path("custom_components/postnl/lovelace.js"),
                cache_headers=True
            )
        ])

    await init_resource(
        hass=hass,
        url='/postnl/lovelace.js',
        ver=VERSION
    )

    return True


async def path_registered(hass: HomeAssistant, url: str):
    for resource in hass.http.app.router.resources():
        if url in resource.canonical:
            return True

    return False


async def init_resource(hass: HomeAssistant, url: str, ver: str) -> bool:
    resources: ResourceStorageCollection = hass.data["lovelace"]["resources"]
    # force load storage
    await resources.async_get_info()

    url2 = f"{url}?v={ver}"

    for item in resources.async_items():
        if not item.get("url", "").startswith(url):
            continue

        # no need to update
        if item["url"].endswith(ver):
            return False

        _LOGGER.debug(f"Update lovelace resource to: {url2}")

        if isinstance(resources, ResourceStorageCollection):
            await resources.async_update_item(
                item["id"], {"res_type": "module", "url": url2}
            )
        else:
            # not the best solution, but what else can we do
            item["url"] = url2

        return True

    if isinstance(resources, ResourceStorageCollection):
        _LOGGER.debug(f"Add new lovelace resource: {url2}")
        await resources.async_create_item({"res_type": "module", "url": url2})
    else:
        _LOGGER.debug(f"Add extra JS module: {url2}")
        add_extra_js_url(hass, url2)

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
