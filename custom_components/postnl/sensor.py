"""Sensors for incoming and outgoing PostNL packages."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PostNLConfigEntry, PostNLCoordinator

PARALLEL_UPDATES = 0

SENSORS = (
    SensorEntityDescription(
        key="delivery",
        translation_key="delivery",
        native_unit_of_measurement="packages",
        icon="mdi:package-variant-closed",
    ),
    SensorEntityDescription(
        key="distribution",
        translation_key="distribution",
        native_unit_of_measurement="packages",
        icon="mdi:package-variant-closed",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PostNLConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors from the entry's validated coordinator."""
    async_add_entities(
        PostNLDelivery(entry.runtime_data, description) for description in SENSORS
    )


class PostNLDelivery(CoordinatorEntity[PostNLCoordinator], SensorEntity):
    """Expose a package count and the existing package-card attributes."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: PostNLCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize a sensor with the existing account-based unique ID."""
        super().__init__(coordinator, context=description.key)
        self.entity_description = description
        self._role = "receiver" if description.key == "delivery" else "sender"
        self._attr_unique_id = f"{coordinator.account.account_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.account.account_id)},
            name=coordinator.account.email or "PostNL",
            manufacturer="PostNL",
        )

    @property
    def native_value(self) -> int:
        """Return the number of packages still in transit."""
        return sum(
            not package.delivered for package in self.coordinator.data[self._role]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Keep package payloads compatible with existing dashboard cards."""
        packages = self.coordinator.data[self._role]
        return {
            "delivered": [asdict(package) for package in packages if package.delivered],
            "enroute": [
                asdict(package) for package in packages if not package.delivered
            ],
        }
