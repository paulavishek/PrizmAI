"""
Asana connector.

Authenticates to Asana with a Personal Access Token (single token — paste-and-go),
lists projects across the user's workspaces, and fetches a project's tasks shaped
exactly like the input the existing ``AsanaAdapter`` consumes: ``{"data": [ ... ]}``
with gid/name/notes/completed/assignee/due_on/memberships.section/tags.

Docs: https://developers.asana.com/reference/rest-api-reference
"""

import logging
from typing import Any, Dict, List

import requests

from .base_connector import BaseSourceConnector, ConnectorError

logger = logging.getLogger(__name__)

_BASE = "https://app.asana.com/api/1.0"
_TASK_FIELDS = (
    "name,notes,completed,assignee.name,assignee.email,due_on,due_at,"
    "start_on,created_at,tags.name,tags.color,memberships.section.name,parent"
)


class AsanaConnector(BaseSourceConnector):

    provider = "asana"
    adapter_name = "asana"  # AdapterFactory registry key
    PAGE_SIZE = 100

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.connection.get_token()}",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: Dict = None) -> Dict:
        try:
            resp = requests.get(
                f"{_BASE}{path}", headers=self._headers(),
                params=params, timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ConnectorError(f"Could not reach Asana: {exc}")

        if resp.status_code in (401, 403):
            raise ConnectorError(
                "Asana rejected the token. Check your Personal Access Token.",
                status_code=resp.status_code,
            )
        if resp.status_code >= 400:
            raise ConnectorError(f"Asana returned HTTP {resp.status_code}.", status_code=resp.status_code)
        try:
            return resp.json()
        except ValueError:
            raise ConnectorError("Asana returned a non-JSON response.")

    def test_connection(self) -> Dict[str, Any]:
        data = self._get("/users/me").get("data", {}) or {}
        return {"account": data.get("email") or data.get("name")}

    def list_projects(self) -> List[Dict[str, Any]]:
        projects: List[Dict[str, Any]] = []
        workspaces = self._get("/workspaces").get("data", []) or []
        for ws in workspaces:
            ws_gid = ws.get("gid")
            ws_name = ws.get("name") or ""
            if not ws_gid:
                continue
            data = self._get(
                "/projects",
                params={"workspace": ws_gid, "opt_fields": "name,archived", "limit": 100},
            )
            for proj in data.get("data", []) or []:
                if proj.get("archived"):
                    continue
                label = proj.get("name") or proj.get("gid")
                if ws_name:
                    label = f"{ws_name} / {label}"
                projects.append({"id": proj.get("gid"), "name": label})
        return projects

    def fetch_project(self, project_id: str) -> Dict[str, Any]:
        """Return ``{"data": [tasks]}`` for the whole project (all pages)."""
        tasks: List[Dict[str, Any]] = []
        offset = None
        while True:
            params = {"project": project_id, "opt_fields": _TASK_FIELDS, "limit": self.PAGE_SIZE}
            if offset:
                params["offset"] = offset
            data = self._get("/tasks", params=params)
            tasks.extend(data.get("data", []) or [])
            offset = (data.get("next_page") or {}).get("offset")
            if not offset:
                break
        return {"data": tasks}
