import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.landplan.const import CONF_PLAN_ID, CONF_TOKEN, DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow custom integrations to load in tests."""
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: "test-token-abc", CONF_PLAN_ID: "cmn1uj27z"},
        title="Smart Forest",
        unique_id="cmn1uj27z",
    )


@pytest.fixture
def mock_plans() -> list:
    return [
        {"id": "cmn1uj27z", "name": "Smart Forest"},
        {"id": "cmojgegfv", "name": "Maui Surf Shack"},
    ]


@pytest.fixture
def mock_projects() -> list:
    return [
        {"id": "proj-1", "title": "Spring Planting", "status": "active"},
        {"id": "proj-2", "title": "Fence Repair", "status": "planned"},
    ]


@pytest.fixture
def mock_activities() -> list:
    return [
        {"id": "act-1", "title": "Prune apple trees", "projectId": "proj-1", "projectTitle": "Spring Planting"},
        {"id": "act-2", "title": "Replace posts", "projectId": "proj-2", "projectTitle": "Fence Repair"},
    ]


@pytest.fixture
def mock_map_objects() -> list:
    return [
        {"id": "obj-1", "label": "Camera Node 1", "tags": ["camera-node"], "objectType": "point"},
        {"id": "obj-2", "label": "Mesh Node A", "tags": ["mesh-node"], "objectType": "point"},
        {"id": "obj-3", "label": "North Trail", "tags": ["road"], "objectType": "line"},
    ]
