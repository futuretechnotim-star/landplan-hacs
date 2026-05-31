"""LandPlan Home Assistant integration."""
from __future__ import annotations

import shutil
from pathlib import Path

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import LandPlanCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_CARD_JS = "smartfarmview-snapshot-card.js"

# /local/ always maps to config/www/ in every HA installation — no HACS dependency.
CARD_URL = f"/local/landplan/{_CARD_JS}"


def _install_card(src: Path, dest_dir: Path) -> None:
    """Copy card JS into www/landplan/ (blocking, run in executor)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / _CARD_JS)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Copy the bundled card JS into config/www/landplan/ so it is served at
    /local/landplan/smartfarmview-snapshot-card.js — HA always serves /local/
    from config/www/ with no startup-order dependency."""
    src = Path(__file__).parent / "www" / _CARD_JS
    dest_dir = Path(hass.config.config_dir) / "www" / "landplan"
    await hass.async_add_executor_job(_install_card, src, dest_dir)
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
