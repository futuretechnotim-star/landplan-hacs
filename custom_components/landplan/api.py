"""Thin async client for the LandPlan API.

All HTTP calls must go through this module so that private-endpoint changes
are a one-file fix.

Auth: Bearer token (same key used by the LandPlan MCP server via LANDPLAN_API_KEY).
All successful responses are wrapped: { "data": <T> } — _get/_post unwrap automatically.
"""
from __future__ import annotations

from typing import Any

import aiohttp

BASE_URL = "https://api.landplan.app"


class LandPlanAuthError(Exception):
    """Raised when authentication fails (401/403)."""


class LandPlanApiError(Exception):
    """Raised on any non-auth API error."""


class LandPlanApiClient:
    def __init__(self, token: str, session: aiohttp.ClientSession) -> None:
        self._token = token
        self._session = session

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _get(self, path: str, **params: Any) -> Any:
        url = f"{BASE_URL}{path}"
        async with self._session.get(url, headers=self._headers(), params=params or None) as resp:
            if resp.status in (401, 403):
                raise LandPlanAuthError(f"Auth failed: {resp.status}")
            if not resp.ok:
                raise LandPlanApiError(f"API error {resp.status} for {path}")
            body = await resp.json()
            return body["data"]

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def validate_token(self) -> dict[str, Any]:
        """Validate the token and return { id, email } for the authenticated user."""
        return await self._get("/auth/me")

    # ------------------------------------------------------------------
    # Plans
    # ------------------------------------------------------------------

    async def list_plans(self) -> list[dict[str, Any]]:
        """Return all plans visible to the authenticated user (owned + shared)."""
        data = await self._get("/plans")
        # Response shape: { owned?: PlanSummary[], shared?: PlanSummary[] }
        return (data.get("owned") or []) + (data.get("shared") or [])

    async def get_plan(self, plan_id: str) -> dict[str, Any]:
        return await self._get(f"/plans/{plan_id}")

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    async def list_projects(self, plan_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/plans/{plan_id}/projects")

    # ------------------------------------------------------------------
    # Activities / tasks
    # ------------------------------------------------------------------

    async def list_activities(self, plan_id: str, project_id: str) -> list[dict[str, Any]]:
        """Return all activities for a single project."""
        return await self._get(f"/plans/{plan_id}/projects/{project_id}/activities")

    async def list_all_activities(
        self, plan_id: str, projects: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Fetch and flatten activities across all projects for a plan."""
        results: list[dict[str, Any]] = []
        for project in projects:
            activities = await self.list_activities(plan_id, project["id"])
            for activity in activities:
                activity.setdefault("projectId", project["id"])
                activity.setdefault("projectTitle", project.get("title", ""))
            results.extend(activities)
        return results

    # ------------------------------------------------------------------
    # Map objects
    # ------------------------------------------------------------------

    async def list_map_objects(
        self, plan_id: str, object_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Return map objects for a plan, optionally filtered by objectType."""
        params = {"objectType": object_type} if object_type else {}
        return await self._get(f"/plans/{plan_id}/objects", **params)

    async def get_map_object(self, plan_id: str, object_id: str) -> dict[str, Any]:
        """Return a single map object with geometry metrics."""
        return await self._get(f"/plans/{plan_id}/objects/{object_id}", metrics="true")
