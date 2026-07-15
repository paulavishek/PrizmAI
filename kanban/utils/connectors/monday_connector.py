"""
Monday.com connector (GraphQL API v2).

Authenticates with a single API token (Monday: Avatar → Developers → My Access
Tokens), lists boards, and fetches a board's groups + items shaped for the
``MondayApiAdapter`` (adapter key "monday_api").

Docs: https://developer.monday.com/api-reference/docs
"""

import logging
from typing import Any, Dict, List

import requests

from .base_connector import BaseSourceConnector, ConnectorError

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.monday.com/v2"


class MondayConnector(BaseSourceConnector):

    provider = "monday"
    adapter_name = "monday_api"
    PAGE_SIZE = 100

    def _post(self, query: str, variables: Dict = None) -> Dict:
        try:
            resp = requests.post(
                _ENDPOINT,
                json={"query": query, "variables": variables or {}},
                headers={
                    "Authorization": self.connection.get_token(),
                    "Content-Type": "application/json",
                    "API-Version": "2024-01",
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ConnectorError(f"Could not reach Monday.com: {exc}")

        if resp.status_code in (401, 403):
            raise ConnectorError("Monday.com rejected the token.", status_code=resp.status_code)
        if resp.status_code >= 400:
            raise ConnectorError(f"Monday.com returned HTTP {resp.status_code}.", status_code=resp.status_code)
        try:
            body = resp.json()
        except ValueError:
            raise ConnectorError("Monday.com returned a non-JSON response.")
        if body.get("errors"):
            msg = body["errors"][0].get("message", "GraphQL error")
            # 401-style auth failures often arrive as 200 + errors.
            raise ConnectorError(f"Monday.com error: {msg}")
        return body.get("data", {}) or {}

    def test_connection(self) -> Dict[str, Any]:
        data = self._post("query { me { name email } }")
        me = data.get("me") or {}
        return {"account": me.get("email") or me.get("name")}

    def list_projects(self) -> List[Dict[str, Any]]:
        data = self._post("query { boards(limit: 200, state: active) { id name } }")
        return [{"id": str(b["id"]), "name": b.get("name") or str(b["id"])}
                for b in (data.get("boards") or [])]

    def fetch_project(self, project_id: str) -> Dict[str, Any]:
        """Return ``{"boards": [ {name, groups, items_page:{items}} ]}``."""
        query = """
        query ($ids: [ID!], $limit: Int!) {
          boards(ids: $ids) {
            id
            name
            groups { id title }
            items_page(limit: $limit) {
              cursor
              items {
                id
                name
                group { id title }
                column_values { text column { title } }
              }
            }
          }
        }
        """
        data = self._post(query, {"ids": [project_id], "limit": self.PAGE_SIZE})
        boards = data.get("boards") or []
        if not boards:
            raise ConnectorError("Monday.com board not found.", status_code=404)
        board = boards[0]

        items = list(((board.get("items_page") or {}).get("items")) or [])
        cursor = (board.get("items_page") or {}).get("cursor")

        # Follow the cursor for additional pages of items.
        next_query = """
        query ($cursor: String!, $limit: Int!) {
          next_items_page(cursor: $cursor, limit: $limit) {
            cursor
            items {
              id
              name
              group { id title }
              column_values { text column { title } }
            }
          }
        }
        """
        while cursor:
            page = self._post(next_query, {"cursor": cursor, "limit": self.PAGE_SIZE})
            nip = page.get("next_items_page") or {}
            items.extend(nip.get("items") or [])
            cursor = nip.get("cursor")

        board["items_page"] = {"items": items}
        return {"boards": [board]}
