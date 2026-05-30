"""Tests for the config flow — token validation, plan dropdown, and duplicate prevention."""
import pytest
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.landplan.const import CONF_PLAN_ID, CONF_TOKEN, DOMAIN


@pytest.fixture
def mock_api_client(mock_plans):
    """Patch LandPlanApiClient with successful defaults."""
    with patch("custom_components.landplan.config_flow.LandPlanApiClient") as MockClient:
        instance = MockClient.return_value
        instance.validate_token = AsyncMock(return_value={"id": "u1", "email": "user@test.com"})
        instance.list_plans = AsyncMock(return_value=mock_plans)
        yield instance


async def _start_flow(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


class TestTokenStep:
    async def test_shows_token_form_initially(self, hass):
        result = await _start_flow(hass)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert not result["errors"]

    async def test_valid_token_advances_to_plan_step(self, hass, mock_api_client):
        result = await _start_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "good-token"}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "plan"

    async def test_strips_whitespace_from_token(self, hass, mock_api_client):
        result = await _start_flow(hass)
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "  good-token  "}
        )
        mock_api_client.validate_token.assert_called_once()

    async def test_invalid_auth_shows_error(self, hass, mock_plans):
        from custom_components.landplan.api import LandPlanAuthError

        with patch("custom_components.landplan.config_flow.LandPlanApiClient") as MockClient:
            MockClient.return_value.validate_token = AsyncMock(side_effect=LandPlanAuthError)
            result = await _start_flow(hass)
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_TOKEN: "bad-token"}
            )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "invalid_auth"

    async def test_api_error_shows_cannot_connect(self, hass):
        from custom_components.landplan.api import LandPlanApiError

        with patch("custom_components.landplan.config_flow.LandPlanApiClient") as MockClient:
            MockClient.return_value.validate_token = AsyncMock(side_effect=LandPlanApiError)
            result = await _start_flow(hass)
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_TOKEN: "any-token"}
            )

        assert result["errors"]["base"] == "cannot_connect"


class TestPlanStep:
    async def test_creates_entry_with_correct_data(self, hass, mock_api_client, mock_plans):
        result = await _start_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "good-token"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PLAN_ID: mock_plans[0]["id"]}
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Smart Forest"
        assert result["data"][CONF_TOKEN] == "good-token"
        assert result["data"][CONF_PLAN_ID] == mock_plans[0]["id"]

    async def test_aborts_on_duplicate_plan(self, hass, mock_api_client, mock_plans, mock_config_entry):
        mock_config_entry.add_to_hass(hass)

        result = await _start_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "good-token"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PLAN_ID: mock_plans[0]["id"]}
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"
