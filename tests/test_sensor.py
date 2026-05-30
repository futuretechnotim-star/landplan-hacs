"""Tests for the LandPlan sensor platform."""
from __future__ import annotations

import pytest

from custom_components.landplan.sensor import LandPlanTaskCountSensor
from custom_components.landplan.coordinator import LandPlanData


@pytest.fixture
def project():
    return {"id": "proj-1", "title": "Spring Planting", "status": "active"}


@pytest.fixture
def coordinator(hass, mock_config_entry, project, mock_activities, mock_map_objects):
    mock_config_entry.add_to_hass(hass)
    from custom_components.landplan.coordinator import LandPlanCoordinator
    coord = LandPlanCoordinator.__new__(LandPlanCoordinator)
    coord.hass = hass
    coord._plan_id = mock_config_entry.data["plan_id"]
    coord.data = LandPlanData(
        projects=[project],
        activities=mock_activities,
        map_objects=mock_map_objects,
    )
    coord._listeners = {}
    return coord


class TestNativeValue:
    def test_counts_activities_for_project(self, coordinator, project, mock_activities):
        entity = LandPlanTaskCountSensor(coordinator, project)
        # mock_activities has 1 activity for proj-1 ("Prune apple trees")
        assert entity.native_value == 1

    def test_returns_zero_for_project_with_no_activities(self, coordinator):
        empty_project = {"id": "proj-empty", "title": "Empty", "status": "planned"}
        entity = LandPlanTaskCountSensor(coordinator, empty_project)
        assert entity.native_value == 0

    def test_does_not_count_other_project_activities(self, coordinator):
        # mock_activities already has act-2 for proj-2; add a second one
        other_project = {"id": "proj-2", "title": "Other", "status": "planned"}
        coordinator.data.activities.append(
            {"id": "act-x", "title": "Other task", "projectId": "proj-2"}
        )
        entity = LandPlanTaskCountSensor(coordinator, other_project)
        assert entity.native_value == 2


class TestExtraStateAttributes:
    def test_includes_project_status(self, coordinator, project):
        entity = LandPlanTaskCountSensor(coordinator, project)
        assert entity.extra_state_attributes["project_status"] == "active"

    def test_includes_activity_titles(self, coordinator, project, mock_activities):
        entity = LandPlanTaskCountSensor(coordinator, project)
        titles = entity.extra_state_attributes["activities"]
        # Only proj-1's activity is included; proj-2's "Replace posts" is excluded
        assert "Prune apple trees" in titles
        assert "Replace posts" not in titles

    def test_empty_activities_list_for_empty_project(self, coordinator):
        empty_project = {"id": "proj-empty", "title": "Empty", "status": "planned"}
        entity = LandPlanTaskCountSensor(coordinator, empty_project)
        assert entity.extra_state_attributes["activities"] == []


class TestMetadata:
    def test_unique_id_format(self, coordinator, project):
        entity = LandPlanTaskCountSensor(coordinator, project)
        assert entity.unique_id == f"{coordinator._plan_id}_proj-1_task_count"

    def test_name_includes_project_title(self, coordinator, project):
        entity = LandPlanTaskCountSensor(coordinator, project)
        assert entity.name == "Spring Planting Tasks"
