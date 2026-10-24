"""Sensors for incoming and outgoing PostNL packages."""

from dataclasses import asdict
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DELIVERED_RETENTION_DAYS,
    DEFAULT_DELIVERED_RETENTION_DAYS,
    DOMAIN,
)
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
        PostNLDelivery(
            entry.runtime_data,
            description,
            entry.options.get(
                CONF_DELIVERED_RETENTION_DAYS, DEFAULT_DELIVERED_RETENTION_DAYS
            ),
        )
        for description in SENSORS
    )


class PostNLDelivery(CoordinatorEntity[PostNLCoordinator], SensorEntity):
    """Expose a package count and the existing package-card attributes."""

    _attr_has_entity_name = True
    # Keep full package lists available to cards without filling recorder history.
    _unrecorded_attributes = frozenset({"delivered", "enroute"})

    def __init__(
        self,
        coordinator: PostNLCoordinator,
        description: SensorEntityDescription,
        delivered_retention_days: int = DEFAULT_DELIVERED_RETENTION_DAYS,
    ) -> None:
        """Initialize a sensor with the existing account-based unique ID."""
        super().__init__(coordinator, context=description.key)
        self.entity_description = description
        self._delivered_retention_days = delivered_retention_days
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
        """Expose compact parcels, applying retention only to delivered items."""
        packages = self.coordinator.data[self._role]
        cutoff = dt_util.utcnow() - timedelta(days=self._delivered_retention_days)
        attributes: dict[str, Any] = {"delivered": [], "enroute": []}
        for package in packages:
            if package.delivered and self._delivered_retention_days:
                delivered_at = dt_util.parse_datetime(package.delivery_date or "")
                if delivered_at is not None and dt_util.as_utc(delivered_at) < cutoff:
                    continue
            attributes["delivered" if package.delivered else "enroute"].append(
                {
                    key: value
                    for key, value in asdict(package).items()
                    if value is not None
                }
            )
        return attributes
