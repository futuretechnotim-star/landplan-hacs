"""Shared helpers for LandPlan platform setup."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


def remove_stale_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    platform_domain: str,
    valid_unique_ids: set[str],
) -> None:
    """Remove registry entries for this platform that are no longer in coordinator data.

    Call this in async_setup_entry before async_add_entities so that entities
    deleted from LandPlan don't persist as unavailable orphans in HA.

    Args:
        platform_domain: the HA domain for this platform, e.g. "calendar", "sensor".
        valid_unique_ids: unique_ids of entities that should exist after this setup.
    """
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            entity_entry.domain == platform_domain
            and entity_entry.unique_id not in valid_unique_ids
        ):
            registry.async_remove(entity_entry.entity_id)
