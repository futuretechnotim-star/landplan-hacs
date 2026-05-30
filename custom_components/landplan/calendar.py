"""LandPlan calendar platform — exposes project activities as HA calendar entities.

TODO: implement CalendarEntity per project, returning today's activities.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    # Placeholder — no entities registered until CalendarEntity is implemented.
    pass
