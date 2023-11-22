from __future__ import annotations

import logging
import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the sensor platform."""

    half_hour_from_now = dt_util.now() + datetime.timedelta(minutes=30)
    half_hour_from_now_2 = dt_util.now() + datetime.timedelta(minutes=60)

    entities = [
        PostNLCalendarEntity(
            None,
            "PostNL"
        )
    ]

    async_add_entities(entities)


class PostNLCalendarEntity(CalendarEntity):
    def __init__(self, event: CalendarEvent, name: str) -> None:
        """Initialize demo calendar."""
        self._event = event
        self._attr_name = name

    @property
    def event(self) -> CalendarEvent:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        half_hour_from_now = dt_util.now() + datetime.timedelta(minutes=30)
        half_hour_from_now2 = dt_util.now() + datetime.timedelta(minutes=120)

        return [
            CalendarEvent(
                start=half_hour_from_now,
                end=half_hour_from_now + datetime.timedelta(minutes=60),
                summary="Pakketje 1",
                location="https://jouw.postnl.nl/track-and-trace/***REMOVED***"
            ),
            CalendarEvent(
                start=half_hour_from_now2,
                end=half_hour_from_now2 + datetime.timedelta(minutes=60),
                summary="Pakketje 2",
            )
        ]