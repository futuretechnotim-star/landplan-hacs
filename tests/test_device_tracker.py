"""Tests for the LandPlan device_tracker platform."""
from __future__ import annotations

import pytest

from custom_components.landplan.device_tracker import LandPlanNodeTracker
from custom_components.landplan.coordinator import LandPlanData


CAMERA_NODE = {
    "id": "obj-cam-1",
    "objectType": "point",
    "label": "Camera Node 1",
    "tags": ["camera-node"],
    "geometry": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
}

MESH_NODE = {
    "id": "obj-mesh-1",
    "objectType": "point",
    "label": "Mesh Node Alpha",
    "tags": ["mesh-node"],
    "geometry": {"type": "Point", "coordinates": [-122.4100, 37.7800]},
}

NON_DEVICE = {
    "id": "obj-road-1",
    "objectType": "generic_line",
    "label": "North Trail",
    "tags": ["road"],
    "geometry": {"type": "LineString", "coordinates": [[-122.4, 37.77], [-122.41, 37.78]]},
}


@pytest.fixture
def coordinator(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    from custom_components.landplan.coordinator import LandPlanCoordinator
    coord = LandPlanCoordinator.__new__(LandPlanCoordinator)
    coord.hass = hass
    coord._plan_id = mock_config_entry.data["plan_id"]
    coord.data = LandPlanData(map_objects=[CAMERA_NODE, MESH_NODE, NON_DEVICE])
    coord._listeners = {}
    return coord


class TestCoordinates:
    def test_latitude_is_coordinates_index_1(self, coordinator):
        entity = LandPlanNodeTracker(coordinator, CAMERA_NODE)
        assert entity.latitude == pytest.approx(37.7749)

    def test_longitude_is_coordinates_index_0(self, coordinator):
        entity = LandPlanNodeTracker(coordinator, CAMERA_NODE)
        assert entity.longitude == pytest.approx(-122.4194)

    def test_returns_none_when_geometry_missing(self, coordinator):
        obj = {**CAMERA_NODE, "geometry": None}
        entity = LandPlanNodeTracker(coordinator, obj)
        # _current_obj looks up from coordinator.data, not the constructor arg
        coordinator.data = LandPlanData(map_objects=[obj])
        assert entity.latitude is None
        assert entity.longitude is None


class TestExtraStateAttributes:
    def test_includes_tags(self, coordinator):
        entity = LandPlanNodeTracker(coordinator, CAMERA_NODE)
        assert entity.extra_state_attributes["tags"] == ["camera-node"]

    def test_includes_object_type(self, coordinator):
        entity = LandPlanNodeTracker(coordinator, CAMERA_NODE)
        assert entity.extra_state_attributes["object_type"] == "point"

    def test_normalizes_tag_relation_object_shape(self, coordinator):
        obj = {
            **CAMERA_NODE,
            "tags": [{"id": "rel-1", "tagId": "t-1", "tag": {"name": "camera-node"}}],
        }
        coordinator.data = LandPlanData(map_objects=[obj])
        entity = LandPlanNodeTracker(coordinator, obj)
        assert entity.extra_state_attributes["tags"] == ["camera-node"]


class TestLiveUpdate:
    def test_picks_up_updated_coordinates_from_coordinator(self, coordinator):
        entity = LandPlanNodeTracker(coordinator, CAMERA_NODE)
        updated = {**CAMERA_NODE, "geometry": {"type": "Point", "coordinates": [-120.0, 35.0]}}
        coordinator.data = LandPlanData(map_objects=[updated, MESH_NODE])
        assert entity.latitude == pytest.approx(35.0)
        assert entity.longitude == pytest.approx(-120.0)


class TestMetadata:
    def test_unique_id_format(self, coordinator):
        entity = LandPlanNodeTracker(coordinator, CAMERA_NODE)
        assert entity.unique_id == f"{coordinator._plan_id}_obj-cam-1_tracker"

    def test_name_from_label(self, coordinator):
        entity = LandPlanNodeTracker(coordinator, CAMERA_NODE)
        assert entity.name == "Camera Node 1"
