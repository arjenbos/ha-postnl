"""Shared helpers for exercising Home Assistant OAuth flows."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.postnl.const import DOMAIN, POSTNL_REDIRECT_URI


def sensor_entity_id(hass: HomeAssistant, suffix: str) -> str:
    """Find a sensor by stable identity rather than Core's generated name."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"test-account_{suffix}"
    )
    assert entity_id is not None
    return entity_id


async def start_oauth(hass: HomeAssistant, result: dict | None = None) -> dict:
    """Select the registered implementation and return the authorization step."""
    if result is None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": DOMAIN}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    return result


async def finish_oauth(hass: HomeAssistant, result: dict) -> dict:
    """Supply the external callback data and finish the token exchange."""
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": "test-code", "state": {"redirect_uri": POSTNL_REDIRECT_URI}},
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
    return await hass.config_entries.flow.async_configure(result["flow_id"])
