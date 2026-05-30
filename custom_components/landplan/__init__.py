"""LandPlan Home Assistant integration."""
from __future__ import annotations

from pathlib import Path

import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import LandPlanCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_CARD_JS = "smartfarmview-snapshot-card.js"
_CARD_URL = f"/landplan/{_CARD_JS}"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Serve the bundled Lovelace card JS at a stable URL.

    The card is not auto-registered as a Lovelace resource because HA has no
    stable public API for that. Add it manually once:
      Settings → Dashboards → Resources → /landplan/smartfarmview-snapshot-card.js
      (type: JavaScript module)
    """
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                _CARD_URL,
                str(Path(__file__).parent / "www" / _CARD_JS),
                cache_headers=True,
            )
        ]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = LandPlanCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
