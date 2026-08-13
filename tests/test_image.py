"""Tests for the LandPlan image platform."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioresponses import aioresponses

from custom_components.landplan.image import LandPlanPhotoImage
from custom_components.landplan.coordinator import LandPlanData


PHOTO_POINT = {
    "id": "obj-photo-1",
    "objectType": "photo_point",
    "label": "North Gate Photo",
    "photoId": "photo-abc",
    "updatedAt": "2026-05-30T10:00:00Z",
    "tags": [],
}

PHOTO_POINT_NO_PHOTO = {
    "id": "obj-photo-2",
    "objectType": "photo_point",
    "label": "Unlabelled",
    "photoId": None,
    "updatedAt": "2026-05-30T09:00:00Z",
    "tags": [],
}

NON_PHOTO = {
    "id": "obj-road-1",
    "objectType": "generic_line",
    "label": "North Trail",
    "tags": ["road"],
}


@pytest.fixture
def coordinator(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    from custom_components.landplan.coordinator import LandPlanCoordinator
    coord = LandPlanCoordinator.__new__(LandPlanCoordinator)
    coord.hass = hass
    coord._plan_id = mock_config_entry.data["plan_id"]
    coord.data = LandPlanData(map_objects=[PHOTO_POINT, PHOTO_POINT_NO_PHOTO, NON_PHOTO])
    coord.api = MagicMock()
    coord.api.get_photo_download_url = AsyncMock(
        return_value="https://storage.googleapis.com/signed/photo.jpg"
    )
    coord._listeners = {}
    return coord


class TestSetup:
    def test_only_photo_points_with_photo_id_are_created(self, coordinator):
        eligible = [
            obj for obj in coordinator.data.map_objects
            if obj.get("objectType") == "photo_point" and obj.get("photoId")
        ]
        assert len(eligible) == 1
        assert eligible[0]["id"] == "obj-photo-1"


class TestImageLastUpdated:
    def test_parses_updated_at(self, coordinator):
        entity = LandPlanPhotoImage(coordinator, PHOTO_POINT)
        assert entity.image_last_updated == datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)


class TestAsyncImage:
    async def test_fetches_signed_url_and_returns_bytes(self, hass, coordinator):
        entity = LandPlanPhotoImage(coordinator, PHOTO_POINT)
        entity.hass = hass

        with aioresponses() as m:
            m.get(
                "https://storage.googleapis.com/signed/photo.jpg",
                body=b"JPEG_BYTES",
                status=200,
            )
            result = await entity.async_image()

        coordinator.api.get_photo_download_url.assert_called_once_with(
            coordinator._plan_id, "photo-abc"
        )
        assert result == b"JPEG_BYTES"

    async def test_returns_none_when_photo_id_is_null(self, hass, coordinator):
        entity = LandPlanPhotoImage(coordinator, PHOTO_POINT_NO_PHOTO)
        entity.hass = hass
        result = await entity.async_image()
        assert result is None
        coordinator.api.get_photo_download_url.assert_not_called()

    async def test_returns_none_on_failed_download(self, hass, coordinator):
        entity = LandPlanPhotoImage(coordinator, PHOTO_POINT)
        entity.hass = hass

        with aioresponses() as m:
            m.get("https://storage.googleapis.com/signed/photo.jpg", status=403)
            result = await entity.async_image()

        assert result is None


class TestMetadata:
    def test_unique_id(self, coordinator):
        entity = LandPlanPhotoImage(coordinator, PHOTO_POINT)
        assert entity.unique_id == f"{coordinator._plan_id}_obj-photo-1_image"

    def test_name_from_label(self, coordinator):
        entity = LandPlanPhotoImage(coordinator, PHOTO_POINT)
        assert entity.name == "North Gate Photo"


class TestImageEntityInit:
    def test_access_tokens_initialised(self, coordinator):
        """Regression test: ImageEntity.__init__ must run alongside
        CoordinatorEntity.__init__, or access_tokens is never set and every
        state read raises AttributeError."""
        entity = LandPlanPhotoImage(coordinator, PHOTO_POINT)
        assert len(entity.access_tokens) > 0
