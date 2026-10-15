"""Set up the PostNL integration."""

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .account import Account, entry_account_id
from .api import PostNLAuthenticationError, PostNLError
from .auth import AsyncConfigEntryAuth
from .const import DOMAIN, PLATFORMS
from .coordinator import PostNLConfigEntry, PostNLCoordinator
from .login_api import PostNLLoginAPI


async def async_setup_entry(hass: HomeAssistant, entry: PostNLConfigEntry) -> bool:
    """Validate identity and the first update before forwarding platforms."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = async_get_clientsession(hass)
    auth = AsyncConfigEntryAuth(OAuth2Session(hass, entry, implementation), session)
    try:
        await auth.check_and_refresh_token()
        account = Account.from_userinfo(
            await PostNLLoginAPI(session, auth.access_token).userinfo()
        )
    except PostNLAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except (PostNLError, ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

    previous_account_id = entry_account_id(hass, entry)
    if previous_account_id is not None and previous_account_id != account.account_id:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="wrong_account"
        )
    if any(
        other.entry_id != entry.entry_id
        and entry_account_id(hass, other) == account.account_id
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="already_configured"
        )
    hass.config_entries.async_update_entry(
        entry,
        unique_id=account.account_id,
        data={**entry.data, "account_id": account.account_id},
    )
    coordinator = PostNLCoordinator(hass, entry, auth, account)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    _migrate_entity_ids(hass, entry, account.account_id)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _migrate_entity_ids(
    hass: HomeAssistant, entry: PostNLConfigEntry, account_id: str
) -> None:
    """Preserve entity IDs while updating recognized legacy unique IDs safely."""
    registry = er.async_get(hass)
    for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id):
        if device.identifiers != {(DOMAIN, account_id)}:
            continue
        for entity in er.async_entries_for_device(registry, device.id, True):
            if entity.platform != DOMAIN or entity.unique_id.startswith(
                f"{account_id}_"
            ):
                continue
            suffix = entity.unique_id.rsplit("_", 1)[-1]
            if suffix not in {"delivery", "distribution"}:
                continue
            unique_id = f"{account_id}_{suffix}"
            if registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None:
                registry.async_update_entity(entity.entity_id, new_unique_id=unique_id)


async def async_unload_entry(hass: HomeAssistant, entry: PostNLConfigEntry) -> bool:
    """Unload platforms; Home Assistant owns the shared session and runtime data."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
