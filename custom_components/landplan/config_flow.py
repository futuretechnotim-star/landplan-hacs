"""Config flow: token auth → plan selection.

Step 1: user pastes their LandPlan API token (same key used by the MCP server).
        The flow validates it by calling GET /auth/me.
Step 2: the flow fetches available plans and presents a dropdown.
The config entry stores {token, plan_id}.

Multiple config entries are supported — one per plan.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LandPlanApiClient, LandPlanAuthError, LandPlanApiError
from .const import CONF_PLAN_ID, CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LandPlanConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._token: str | None = None
        self._plans: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: collect API token and validate it via GET /auth/me."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            client = LandPlanApiClient(token, async_get_clientsession(self.hass))
            try:
                await client.validate_token()
                plans = await client.list_plans()
            except LandPlanAuthError:
                errors["base"] = "invalid_auth"
            except LandPlanApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during token validation")
                errors["base"] = "unknown"
            else:
                self._token = token
                self._plans = plans
                return await self.async_step_plan()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )

    async def async_step_plan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: choose which plan to track."""
        errors: dict[str, str] = {}

        if user_input is not None:
            plan_id = user_input[CONF_PLAN_ID]
            plan_name = next(
                (p.get("name", plan_id) for p in self._plans if p["id"] == plan_id),
                plan_id,
            )
            await self.async_set_unique_id(plan_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=plan_name,
                data={CONF_TOKEN: self._token, CONF_PLAN_ID: plan_id},
            )

        plan_options = {p["id"]: p.get("name", p["id"]) for p in self._plans}

        return self.async_show_form(
            step_id="plan",
            data_schema=vol.Schema({vol.Required(CONF_PLAN_ID): vol.In(plan_options)}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> LandPlanOptionsFlow:
        return LandPlanOptionsFlow(config_entry)


class LandPlanOptionsFlow(OptionsFlow):
    """Options flow — placeholder for future node-mapping configuration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Node-mapping options will be added here once device discovery is implemented.
        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
