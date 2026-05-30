"""LandPlan device_tracker platform — one TrackerEntity per device-tagged map object.

Device nodes are discovered by filtering map objects for tags in DEVICE_TAGS
(camera-node, mesh-node, robot). Positions come from GeoJSON Point geometry:
coordinates[0] = longitude, coordinates[1] = latitude (WGS 84).
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
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
        LandPlanNodeTracker(coordinator, obj)
        for obj in coordinator.data.device_nodes
    )


class LandPlanNodeTracker(CoordinatorEntity[LandPlanCoordinator], TrackerEntity):
    _attr_has_entity_name = True
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator: LandPlanCoordinator, obj: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._obj_id = obj["id"]
        self._attr_unique_id = f"{coordinator._plan_id}_{obj['id']}_tracker"
        self._attr_name = obj.get("label", obj["id"])

    def _current_obj(self) -> dict[str, Any] | None:
        """Return live map object so position updates are reflected after a coordinator refresh."""
        for obj in self.coordinator.data.device_nodes:
            if obj["id"] == self._obj_id:
                return obj
        return None

    @property
    def latitude(self) -> float | None:
        obj = self._current_obj()
        try:
            return obj["geometry"]["coordinates"][1]
        except (TypeError, KeyError, IndexError):
            return None

    @property
    def longitude(self) -> float | None:
        obj = self._current_obj()
        try:
            return obj["geometry"]["coordinates"][0]
        except (TypeError, KeyError, IndexError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        obj = self._current_obj() or {}
        return {
            "tags": obj.get("tags", []),
            "object_type": obj.get("objectType"),
        }
