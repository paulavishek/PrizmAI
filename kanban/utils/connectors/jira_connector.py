"""
Jira Cloud connector (reference implementation).

Authenticates to Jira Cloud with Basic auth (account email + API token — the
"paste a token" flow described in the onboarding doc), lists projects, and
fetches all issues for a project shaped exactly like the input ``JiraAdapter``
already consumes: ``{"issues": [{"key": ..., "fields": {...}}, ...]}``.

Two Jira-specific normalisations happen here so the adapter stays unchanged:
  * ``description`` (Atlassian Document Format / ADF JSON) is flattened to text.
  * The issue's Epic is normalised to ``fields["epic"] = {"key", "name"}`` from
    the ``parent`` field, so the adapter/orchestrator can group by epic.

Docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
"""

import logging
from typing import Any, Dict, List

import requests
from requests.auth import HTTPBasicAuth

from .base_connector import BaseSourceConnector, ConnectorError

logger = logging.getLogger(__name__)

# Story Points live in a custom field whose id varies per site; these are the
# most common defaults. The adapter reads customfield_10016.
_STORY_POINT_FIELDS = ["customfield_10016", "customfield_10026", "customfield_10004"]

# Fields we ask Jira to return (keeps payloads small vs. *all).
_ISSUE_FIELDS = [
    "summary", "status", "priority", "issuetype", "assignee",
    "labels", "description", "duedate", "created", "parent",
] + _STORY_POINT_FIELDS


class JiraConnector(BaseSourceConnector):

    provider = "jira"
    # Registry key in AdapterFactory.ADAPTER_REGISTRY (not the display name).
    adapter_name = "jira"

    # Jira caps enhanced-search page size at 100.
    PAGE_SIZE = 100

    def __init__(self, connection):
        super().__init__(connection)
        self.base_url = (connection.base_url or "").rstrip("/")
        self.email = connection.account_email or ""

    # ---- HTTP helpers -------------------------------------------------------

    def _auth(self) -> HTTPBasicAuth:
        # Token decrypted in memory only, at call time.
        return HTTPBasicAuth(self.email, self.connection.get_token())

    def _get(self, path: str, params: Dict = None) -> Dict:
        return self._request("GET", path, params=params)

    def _request(self, method: str, path: str, params: Dict = None, json: Dict = None) -> Dict:
        if not self.base_url:
            raise ConnectorError("No Jira site URL configured for this connection.")
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(
                method, url,
                auth=self._auth(),
                headers={"Accept": "application/json"},
                params=params, json=json,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            # Note: never include auth in the message.
            raise ConnectorError(f"Could not reach Jira at {self.base_url}: {exc}")

        if resp.status_code in (401, 403):
            raise ConnectorError(
                "Jira rejected the credentials. Check the site URL, email, and API token.",
                status_code=resp.status_code,
            )
        if resp.status_code == 404:
            raise ConnectorError("Jira resource not found.", status_code=404)
        if resp.status_code >= 400:
            raise ConnectorError(
                f"Jira returned HTTP {resp.status_code}.", status_code=resp.status_code
            )
        try:
            return resp.json()
        except ValueError:
            raise ConnectorError("Jira returned a non-JSON response.")

    # ---- Public interface ---------------------------------------------------

    def test_connection(self) -> Dict[str, Any]:
        data = self._get("/rest/api/3/myself")
        return {
            "account": data.get("emailAddress") or data.get("displayName"),
            "account_id": data.get("accountId"),
        }

    def list_projects(self) -> List[Dict[str, Any]]:
        projects: List[Dict[str, Any]] = []
        start_at = 0
        while True:
            data = self._get(
                "/rest/api/3/project/search",
                params={"startAt": start_at, "maxResults": 50},
            )
            for proj in data.get("values", []):
                projects.append({"id": proj.get("key"), "name": proj.get("name")})
            if data.get("isLast", True):
                break
            start_at += len(data.get("values", []) or [])
            if not data.get("values"):
                break
        return projects

    def fetch_project(self, project_id: str) -> Dict[str, Any]:
        """Return ``{"issues": [...]}`` for the whole project (all pages)."""
        issues: List[Dict[str, Any]] = []
        next_token = None
        while True:
            body = {
                "jql": f'project = "{project_id}" ORDER BY created ASC',
                "maxResults": self.PAGE_SIZE,
                "fields": _ISSUE_FIELDS,
            }
            if next_token:
                body["nextPageToken"] = next_token
            data = self._request("POST", "/rest/api/3/search/jql", json=body)
            page = data.get("issues", []) or []
            for issue in page:
                issues.append(self._normalise_issue(issue))
            next_token = data.get("nextPageToken")
            if data.get("isLast", True) or not next_token or not page:
                break
        return {"issues": issues}

    # ---- Normalisation ------------------------------------------------------

    def _normalise_issue(self, issue: Dict) -> Dict:
        """Reshape a raw Jira issue into the shape JiraAdapter expects."""
        fields = issue.get("fields", {}) or {}

        # Flatten ADF description (v3 returns a JSON doc, not a string).
        fields["description"] = self._adf_to_text(fields.get("description"))

        # Fold whichever story-point custom field exists into customfield_10016.
        if not fields.get("customfield_10016"):
            for fid in _STORY_POINT_FIELDS:
                if fields.get(fid) is not None:
                    fields["customfield_10016"] = fields[fid]
                    break

        # Normalise Epic from parent so the orchestrator can group by epic.
        parent = fields.get("parent") or {}
        if isinstance(parent, dict):
            parent_type = (
                (parent.get("fields", {}) or {}).get("issuetype", {}) or {}
            ).get("name", "")
            if str(parent_type).lower() == "epic":
                fields["epic"] = {
                    "key": parent.get("key"),
                    "name": (parent.get("fields", {}) or {}).get("summary"),
                }

        issue["fields"] = fields
        return issue

    @staticmethod
    def _adf_to_text(adf: Any) -> str:
        """Flatten Atlassian Document Format (or a plain string) to plain text."""
        if not adf:
            return ""
        if isinstance(adf, str):
            return adf
        if not isinstance(adf, dict):
            return str(adf)

        parts: List[str] = []

        def walk(node):
            if isinstance(node, dict):
                if node.get("type") == "text" and node.get("text"):
                    parts.append(node["text"])
                for child in node.get("content", []) or []:
                    walk(child)
                if node.get("type") in ("paragraph", "heading"):
                    parts.append("\n")
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(adf)
        return "".join(parts).strip()
