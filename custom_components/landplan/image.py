"""LandPlan image platform — one ImageEntity per photo_point map object.

The image is fetched on demand via a GCS signed URL obtained from the LandPlan API.
Signed URLs are valid for ~1 hour; HA's ImageEntity caches based on image_last_updated
so fetches are infrequent (only when the photo's updatedAt timestamp changes).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
        LandPlanPhotoImage(coordinator, obj)
        for obj in coordinator.data.map_objects
        if obj.get("objectType") == "photo_point" and obj.get("photoId")
    )


class LandPlanPhotoImage(CoordinatorEntity[LandPlanCoordinator], ImageEntity):
    _attr_has_entity_name = True
    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator: LandPlanCoordinator, obj: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._obj = obj
        self._attr_unique_id = f"{coordinator._plan_id}_{obj['id']}_image"
        self._attr_name = obj.get("label", obj["id"])

    @property
    def image_last_updated(self) -> datetime | None:
        return dt_util.parse_datetime(self._obj.get("updatedAt", ""))

    def _current_obj(self) -> dict[str, Any]:
        """Return the live map object from coordinator data (picks up updatedAt changes)."""
        for obj in self.coordinator.data.map_objects:
            if obj["id"] == self._obj["id"]:
                return obj
        return self._obj

    async def async_image(self) -> bytes | None:
        obj = self._current_obj()
        photo_id = obj.get("photoId")
        if not photo_id:
            return None
        signed_url = await self.coordinator.api.get_photo_download_url(
            self.coordinator._plan_id, photo_id
        )
        async with async_get_clientsession(self.hass).get(signed_url) as resp:
            if not resp.ok:
                return None
            return await resp.read()
