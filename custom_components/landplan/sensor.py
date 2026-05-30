"""LandPlan sensor platform — one task-count SensorEntity per project."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LandPlanCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: LandPlanCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LandPlanTaskCountSensor(coordinator, project)
        for project in coordinator.data.projects
    )


class LandPlanTaskCountSensor(CoordinatorEntity[LandPlanCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:format-list-checks"
    _attr_native_unit_of_measurement = "tasks"

    def __init__(self, coordinator: LandPlanCoordinator, project: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._project = project
        self._project_id = project["id"]
        self._attr_unique_id = f"{coordinator._plan_id}_{project['id']}_task_count"
        self._attr_name = f"{project['title']} Tasks"

    def _activities(self) -> list[dict[str, Any]]:
        return [
            a for a in self.coordinator.data.activities
            if a.get("projectId") == self._project_id
        ]

    @property
    def native_value(self) -> int:
        return len(self._activities())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        activities = self._activities()
        return {
            "project_status": self._project.get("status"),
            "activities": [a["title"] for a in activities],
        }
