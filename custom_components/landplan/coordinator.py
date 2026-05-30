"""Slow-tier DataUpdateCoordinator for LandPlan.

Polls the LandPlan API every SLOW_UPDATE_INTERVAL seconds and caches:
  - plan metadata
  - projects list
  - activities list (fetched per-project and flattened)
  - map objects (filtered device nodes available via .device_nodes)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LandPlanApiClient, LandPlanApiError, LandPlanAuthError
from .const import CONF_PLAN_ID, CONF_TOKEN, DEVICE_TAGS, DOMAIN, SLOW_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class LandPlanData:
    plan: dict[str, Any] = field(default_factory=dict)
    projects: list[dict[str, Any]] = field(default_factory=list)
    activities: list[dict[str, Any]] = field(default_factory=list)
    map_objects: list[dict[str, Any]] = field(default_factory=list)

    @property
    def device_nodes(self) -> list[dict[str, Any]]:
        """Map objects tagged as physical devices (camera-node / mesh-node / robot)."""
        return [
            obj for obj in self.map_objects
            if DEVICE_TAGS.intersection(obj.get("tags") or [])
        ]


class LandPlanCoordinator(DataUpdateCoordinator[LandPlanData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._plan_id: str = entry.data[CONF_PLAN_ID]
        self.api = LandPlanApiClient(
            token=entry.data[CONF_TOKEN],
            session=async_get_clientsession(hass),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self._plan_id}",
            update_interval=timedelta(seconds=SLOW_UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> LandPlanData:
        try:
            # Fetch plan, projects, and map objects concurrently.
            plan, projects, map_objects = await asyncio.gather(
                self.api.get_plan(self._plan_id),
                self.api.list_projects(self._plan_id),
                self.api.list_map_objects(self._plan_id),
            )
            # Activities are per-project; fetch after projects are known.
            activities = await self.api.list_all_activities(self._plan_id, projects)
        except LandPlanAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except LandPlanApiError as err:
            raise UpdateFailed(f"LandPlan API error: {err}") from err

        return LandPlanData(
            plan=plan,
            projects=projects,
            activities=activities,
            map_objects=map_objects,
        )
