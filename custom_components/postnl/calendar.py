import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PostNLCoordinator
from .structs.package import Package

_LOGGER = logging.getLogger(__name__)



async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the PostNL Calendar config entry."""

    coordinator = PostNLCoordinator(hass)

    async_add_entities(
        [
            PostNLCalendar(coordinator=coordinator)
        ]
    )


class PostNLCalendar(CoordinatorEntity[PostNLCoordinator], CalendarEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator=coordinator)
        self._attr_name = "PostNL"
        self._events: list[CalendarEvent] = []

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug('Updating calendar %s', self.name)

        self._events = []

        for package in self.coordinator.data['receiver']:
            calendar_event = CalendarEvent(
                start=datetime.datetime.fromisoformat(package.planned_from),
                end=datetime.datetime.fromisoformat(package.planned_to),
                summary=package.name,
                uid=package.key
            )

            self._events.append(calendar_event)

        for package in self.coordinator.data['sender']:
            calendar_event = CalendarEvent(
                start=datetime.datetime.fromisoformat(package.planned_from),
                end=datetime.datetime.fromisoformat(package.planned_to),
                summary=package.name,
                uid=package.key
            )

            self._events.append(calendar_event)

        self._events.sort(key=lambda event: event.start)

        super()._handle_coordinator_update()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""

        filtered_events = filter(lambda event: event.start.timestamp() > datetime.datetime.now().timestamp(), self._events)
        events = list(filtered_events)

        return events[0] if len(events) > 0 else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        _LOGGER.debug("Getting events between %s and %s", start_date, end_date)

        filtered_events = filter(lambda event: event.start >= start_date <= end_date, self._events)
        events = list(filtered_events)

        _LOGGER.debug("Events: %s", events)

        return events
