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

# HA's frontend component reads this key when serving the Lovelace HTML page
# and injects a <script type="module"> tag for each URL in the set.
_FRONTEND_EXTRA_MODULE_URL = "frontend_extra_module_url"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the card's JS file and inject it into the Lovelace frontend."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                _CARD_URL,
                str(Path(__file__).parent / "www" / _CARD_JS),
                cache_headers=True,
            )
        ]
    )
    hass.data.setdefault(_FRONTEND_EXTRA_MODULE_URL, set()).add(_CARD_URL)
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
