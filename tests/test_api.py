"""Tests for LandPlanApiClient — verifies endpoint paths, response unwrapping, and error mapping."""
import pytest
from aioresponses import aioresponses
import aiohttp

from custom_components.landplan.api import (
    BASE_URL,
    LandPlanApiClient,
    LandPlanAuthError,
    LandPlanApiError,
)


@pytest.fixture
async def client():
    async with aiohttp.ClientSession() as session:
        yield LandPlanApiClient("test-token", session)


class TestValidateToken:
    async def test_returns_user_info(self, client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/auth/me", payload={"data": {"id": "u1", "email": "user@test.com"}})
            result = await client.validate_token()
        assert result == {"id": "u1", "email": "user@test.com"}

    async def test_raises_auth_error_on_401(self, client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/auth/me", status=401)
            with pytest.raises(LandPlanAuthError):
                await client.validate_token()


class TestListPlans:
    async def test_merges_owned_and_shared(self, client):
        payload = {
            "data": {
                "owned": [{"id": "p1", "name": "Plan A"}],
                "shared": [{"id": "p2", "name": "Plan B"}],
            }
        }
        with aioresponses() as m:
            m.get(f"{BASE_URL}/plans", payload=payload)
            result = await client.list_plans()
        assert len(result) == 2
        assert result[0]["id"] == "p1"
        assert result[1]["id"] == "p2"

    async def test_handles_owned_only(self, client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/plans", payload={"data": {"owned": [{"id": "p1", "name": "Solo"}]}})
            result = await client.list_plans()
        assert len(result) == 1

    async def test_handles_empty_response(self, client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/plans", payload={"data": {}})
            result = await client.list_plans()
        assert result == []


class TestListProjects:
    async def test_calls_correct_endpoint(self, client):
        projects = [{"id": "proj-1", "title": "Spring Planting"}]
        with aioresponses() as m:
            m.get(f"{BASE_URL}/plans/plan-abc/projects", payload={"data": projects})
            result = await client.list_projects("plan-abc")
        assert result == projects


class TestListActivities:
    async def test_calls_per_project_endpoint(self, client):
        activities = [{"id": "act-1", "title": "Prune"}]
        with aioresponses() as m:
            m.get(
                f"{BASE_URL}/plans/plan-abc/projects/proj-1/activities",
                payload={"data": activities},
            )
            result = await client.list_activities("plan-abc", "proj-1")
        assert result == activities

    async def test_list_all_activities_stamps_project_fields(self, client):
        projects = [{"id": "proj-1", "title": "Spring Planting"}]
        activities = [{"id": "act-1", "title": "Prune"}]
        with aioresponses() as m:
            m.get(
                f"{BASE_URL}/plans/plan-abc/projects/proj-1/activities",
                payload={"data": activities},
            )
            result = await client.list_all_activities("plan-abc", projects)
        assert result[0]["projectId"] == "proj-1"
        assert result[0]["projectTitle"] == "Spring Planting"

    async def test_list_all_activities_flattens_across_projects(self, client):
        projects = [
            {"id": "proj-1", "title": "A"},
            {"id": "proj-2", "title": "B"},
        ]
        with aioresponses() as m:
            m.get(
                f"{BASE_URL}/plans/p/projects/proj-1/activities",
                payload={"data": [{"id": "act-1", "title": "Task 1"}]},
            )
            m.get(
                f"{BASE_URL}/plans/p/projects/proj-2/activities",
                payload={"data": [{"id": "act-2", "title": "Task 2"}]},
            )
            result = await client.list_all_activities("p", projects)
        assert len(result) == 2


class TestListMapObjects:
    async def test_calls_objects_endpoint(self, client):
        objects = [{"id": "obj-1", "label": "Camera Node 1", "tags": ["camera-node"]}]
        with aioresponses() as m:
            m.get(f"{BASE_URL}/plans/plan-abc/objects", payload={"data": objects})
            result = await client.list_map_objects("plan-abc")
        assert result == objects

    async def test_passes_object_type_filter(self, client):
        # Embed the query string directly — aioresponses params= matching is version-sensitive
        with aioresponses() as m:
            m.get(
                f"{BASE_URL}/plans/plan-abc/objects?objectType=point",
                payload={"data": []},
            )
            await client.list_map_objects("plan-abc", object_type="point")


class TestErrorHandling:
    async def test_raises_api_error_on_500(self, client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/plans", status=500)
            with pytest.raises(LandPlanApiError):
                await client.list_plans()

    async def test_raises_auth_error_on_403(self, client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/plans", status=403)
            with pytest.raises(LandPlanAuthError):
                await client.list_plans()
