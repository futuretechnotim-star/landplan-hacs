"""Tests for LandPlanCoordinator — verifies data fetching, assembly, and device_nodes filter."""
import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.landplan.api import LandPlanAuthError, LandPlanApiError
from custom_components.landplan.coordinator import LandPlanCoordinator, LandPlanData
from custom_components.landplan.const import DOMAIN


@pytest.fixture
async def coordinator(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    return LandPlanCoordinator(hass, mock_config_entry)


@pytest.fixture
def patched_api(coordinator, mock_projects, mock_activities, mock_map_objects):
    """Patch the coordinator's api client with controllable AsyncMocks."""
    coordinator.api.get_plan = AsyncMock(return_value={"id": "cmn1uj27z", "name": "Smart Forest"})
    coordinator.api.list_projects = AsyncMock(return_value=mock_projects)
    coordinator.api.list_all_activities = AsyncMock(return_value=mock_activities)
    coordinator.api.list_map_objects = AsyncMock(return_value=mock_map_objects)
    return coordinator.api


class TestDataFetching:
    async def test_assembles_landplan_data(self, coordinator, patched_api, mock_projects, mock_activities, mock_map_objects):
        data = await coordinator._async_update_data()

        assert isinstance(data, LandPlanData)
        assert data.plan["name"] == "Smart Forest"
        assert data.projects == mock_projects
        assert data.activities == mock_activities
        assert data.map_objects == mock_map_objects

    async def test_passes_plan_id_to_api(self, coordinator, patched_api):
        await coordinator._async_update_data()

        patched_api.get_plan.assert_called_once_with("cmn1uj27z")
        patched_api.list_projects.assert_called_once_with("cmn1uj27z")
        patched_api.list_map_objects.assert_called_once_with("cmn1uj27z")

    async def test_passes_projects_to_list_all_activities(self, coordinator, patched_api, mock_projects):
        await coordinator._async_update_data()

        patched_api.list_all_activities.assert_called_once_with("cmn1uj27z", mock_projects)

    async def test_wraps_auth_error_as_update_failed(self, coordinator, patched_api):
        patched_api.get_plan.side_effect = LandPlanAuthError("bad token")

        with pytest.raises(UpdateFailed, match="Authentication error"):
            await coordinator._async_update_data()

    async def test_wraps_api_error_as_update_failed(self, coordinator, patched_api):
        patched_api.list_map_objects.side_effect = LandPlanApiError("500")

        with pytest.raises(UpdateFailed, match="LandPlan API error"):
            await coordinator._async_update_data()


class TestDeviceNodes:
    def test_returns_only_tagged_device_objects(self, mock_map_objects):
        data = LandPlanData(map_objects=mock_map_objects)
        nodes = data.device_nodes

        # obj-1 (camera-node) and obj-2 (mesh-node) should be included; obj-3 (road) excluded
        assert len(nodes) == 2
        assert {n["id"] for n in nodes} == {"obj-1", "obj-2"}

    def test_returns_empty_when_no_devices_tagged(self):
        data = LandPlanData(map_objects=[
            {"id": "obj-1", "label": "Pond", "tags": ["water"]},
        ])
        assert data.device_nodes == []

    def test_returns_empty_when_no_map_objects(self):
        data = LandPlanData()
        assert data.device_nodes == []

    def test_handles_objects_with_no_tags_field(self):
        data = LandPlanData(map_objects=[{"id": "obj-1", "label": "Trail"}])
        assert data.device_nodes == []

    def test_handles_tag_relation_object_shape(self):
        """Regression test: the LandPlan API now returns tags as relation
        objects ({"tag": {"name": ...}, ...}), not plain strings — this used
        to crash device_nodes with `TypeError: unhashable type: 'dict'`."""
        data = LandPlanData(map_objects=[
            {
                "id": "obj-1",
                "label": "Cam 1",
                "tags": [{"id": "rel-1", "tagId": "t-1", "tag": {"name": "camera-node"}}],
            },
            {
                "id": "obj-2",
                "label": "Cleanup site",
                "tags": [{"id": "rel-2", "tagId": "t-2", "tag": {"name": "cleanup"}}],
            },
        ])
        nodes = data.device_nodes
        assert {n["id"] for n in nodes} == {"obj-1"}
