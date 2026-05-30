"""LandPlan calendar platform — one CalendarEntity per project.

Each entity exposes that project's activities as calendar events, using
plannedStartDate / plannedEndDate from the activity record. Activities
with no dates are excluded from calendar results.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import LandPlanCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: LandPlanCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LandPlanProjectCalendar(coordinator, project)
        for project in coordinator.data.projects
    )


class LandPlanProjectCalendar(CoordinatorEntity[LandPlanCoordinator], CalendarEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: LandPlanCoordinator, project: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._project = project
        self._project_id = project["id"]
        self._attr_unique_id = f"{coordinator._plan_id}_{project['id']}_calendar"
        self._attr_name = project["title"]

    def _activities(self) -> list[dict[str, Any]]:
        return [
            a for a in self.coordinator.data.activities
            if a.get("projectId") == self._project_id
        ]

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        return dt_util.parse_datetime(value)

    def _to_event(self, activity: dict[str, Any]) -> CalendarEvent | None:
        start = self._parse_dt(activity.get("plannedStartDate"))
        if start is None:
            return None
        end = self._parse_dt(activity.get("plannedEndDate")) or start
        return CalendarEvent(
            summary=activity["title"],
            description=activity.get("details") or "",
            start=start,
            end=end,
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming (or current) activity."""
        now = dt_util.now()
        upcoming = None
        for act in self._activities():
            ev = self._to_event(act)
            if ev is None:
                continue
            if ev.end >= now and (upcoming is None or ev.start < upcoming.start):
                upcoming = ev
        return upcoming

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        events = []
        for act in self._activities():
            ev = self._to_event(act)
            if ev is None:
                continue
            if ev.start < end_date and ev.end > start_date:
                events.append(ev)
        return events
