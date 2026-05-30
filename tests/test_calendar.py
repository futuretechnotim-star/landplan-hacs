"""Tests for the LandPlan calendar platform."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.landplan.calendar import LandPlanProjectCalendar
from custom_components.landplan.coordinator import LandPlanData
from custom_components.landplan.const import DOMAIN


@pytest.fixture
def project():
    return {"id": "proj-1", "title": "Spring Planting", "status": "active"}


@pytest.fixture
def activity_with_dates():
    return {
        "id": "act-1",
        "title": "Prune apple trees",
        "details": "Cut back crossing branches",
        "projectId": "proj-1",
        "plannedStartDate": "2026-06-01T09:00:00Z",
        "plannedEndDate": "2026-06-01T17:00:00Z",
    }


@pytest.fixture
def activity_no_dates():
    return {
        "id": "act-2",
        "title": "Order compost",
        "details": None,
        "projectId": "proj-1",
        "plannedStartDate": None,
        "plannedEndDate": None,
    }


@pytest.fixture
def activity_other_project():
    return {
        "id": "act-3",
        "title": "Fix fence",
        "projectId": "proj-2",
        "plannedStartDate": "2026-06-05T08:00:00Z",
        "plannedEndDate": "2026-06-05T12:00:00Z",
    }


@pytest.fixture
def coordinator(hass, mock_config_entry, project, activity_with_dates, activity_other_project):
    mock_config_entry.add_to_hass(hass)
    from custom_components.landplan.coordinator import LandPlanCoordinator
    coord = LandPlanCoordinator.__new__(LandPlanCoordinator)
    coord.hass = hass
    coord._plan_id = mock_config_entry.data["plan_id"]
    coord.data = LandPlanData(
        projects=[project],
        activities=[activity_with_dates, activity_other_project],
        map_objects=[],
    )
    coord._listeners = {}
    return coord


class TestActivitiesFiltering:
    def test_only_returns_own_project_activities(self, coordinator, project):
        entity = LandPlanProjectCalendar(coordinator, project)
        activities = entity._activities()
        assert len(activities) == 1
        assert activities[0]["id"] == "act-1"

    def test_excludes_other_project_activities(self, coordinator, project):
        entity = LandPlanProjectCalendar(coordinator, project)
        assert all(a["projectId"] == "proj-1" for a in entity._activities())


class TestToEvent:
    def test_converts_activity_with_dates(self, coordinator, project, activity_with_dates):
        entity = LandPlanProjectCalendar(coordinator, project)
        ev = entity._to_event(activity_with_dates)
        assert ev is not None
        assert ev.summary == "Prune apple trees"
        assert ev.description == "Cut back crossing branches"
        assert ev.start == datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        assert ev.end == datetime(2026, 6, 1, 17, 0, tzinfo=timezone.utc)

    def test_returns_none_for_activity_without_start_date(self, coordinator, project, activity_no_dates):
        entity = LandPlanProjectCalendar(coordinator, project)
        assert entity._to_event(activity_no_dates) is None

    def test_uses_start_as_end_when_end_is_null(self, coordinator, project):
        activity = {
            "id": "act-x",
            "title": "Quick task",
            "details": None,
            "projectId": "proj-1",
            "plannedStartDate": "2026-06-10T10:00:00Z",
            "plannedEndDate": None,
        }
        entity = LandPlanProjectCalendar(coordinator, project)
        ev = entity._to_event(activity)
        assert ev is not None
        assert ev.start == ev.end

    def test_empty_description_when_details_null(self, coordinator, project, activity_no_dates):
        activity = {**activity_no_dates, "plannedStartDate": "2026-06-01T08:00:00Z"}
        entity = LandPlanProjectCalendar(coordinator, project)
        ev = entity._to_event(activity)
        assert ev.description == ""


class TestEventProperty:
    async def test_returns_upcoming_event(self, coordinator, project):
        entity = LandPlanProjectCalendar(coordinator, project)
        ev = entity.event
        assert ev is not None
        assert ev.summary == "Prune apple trees"

    async def test_returns_none_when_no_dated_activities(self, coordinator, project, activity_no_dates):
        coordinator.data = LandPlanData(
            projects=[project],
            activities=[activity_no_dates],
            map_objects=[],
        )
        entity = LandPlanProjectCalendar(coordinator, project)
        assert entity.event is None


class TestGetEvents:
    async def test_returns_events_in_range(self, hass, coordinator, project):
        entity = LandPlanProjectCalendar(coordinator, project)
        start = datetime(2026, 5, 1, tzinfo=timezone.utc)
        end = datetime(2026, 7, 1, tzinfo=timezone.utc)
        events = await entity.async_get_events(hass, start, end)
        assert len(events) == 1
        assert events[0].summary == "Prune apple trees"

    async def test_excludes_events_outside_range(self, hass, coordinator, project):
        entity = LandPlanProjectCalendar(coordinator, project)
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        end = datetime(2026, 8, 1, tzinfo=timezone.utc)
        events = await entity.async_get_events(hass, start, end)
        assert events == []

    async def test_excludes_activities_with_no_dates(self, hass, coordinator, project, activity_no_dates):
        coordinator.data.activities.append(activity_no_dates)
        entity = LandPlanProjectCalendar(coordinator, project)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 12, 31, tzinfo=timezone.utc)
        events = await entity.async_get_events(hass, start, end)
        assert all(ev.summary != "Order compost" for ev in events)
