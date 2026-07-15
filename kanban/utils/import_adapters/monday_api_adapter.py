"""
Monday.com API adapter (JSON / GraphQL shape).

The existing ``MondayAdapter`` only parses Monday's *Excel* export. The live
connector talks to Monday's GraphQL API, whose response is a nested board/group/
item structure — so this adapter translates that JSON shape instead.

Expected input (from monday_connector.fetch_project):
    {"boards": [{
        "id": ..., "name": "...",
        "groups": [{"id": "g1", "title": "To Do"}, ...],
        "items_page": {"items": [
            {"id": "i1", "name": "Task", "group": {"id": "g1", "title": "To Do"},
             "column_values": [{"text": "...", "column": {"title": "Status"}}, ...]}
        ]}
    }]}

Mapping: group -> column, item -> task, column_values matched by column title for
status/owner/priority/due date/description/labels.
"""

import json
from typing import Any, Dict, List, Tuple

from .base_adapter import BaseImportAdapter, ImportResult, ImportError


class MondayApiAdapter(BaseImportAdapter):

    name = "Monday.com API Adapter"
    supported_extensions = ["json"]
    source_tool = "Monday.com"

    _STATUS_PROGRESS = {
        "done": 100, "complete": 100, "completed": 100,
        "working on it": 50, "in progress": 50,
        "stuck": 25,
        "not started": 0, "": 0,
    }

    def can_handle(self, data: Any, filename: str = None) -> Tuple[bool, float]:
        if isinstance(data, (bytes, bytearray)):
            return (False, 0.0)
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return (False, 0.0)
        if isinstance(data, dict) and isinstance(data.get("boards"), list):
            board = (data["boards"] or [{}])[0]
            if "items_page" in board or "groups" in board:
                return (True, 0.95)
        return (False, 0.0)

    def parse(self, raw_data: Any) -> Dict[str, Any]:
        if isinstance(raw_data, (bytes, bytearray)):
            raw_data = raw_data.decode("utf-8")
        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except json.JSONDecodeError as e:
                raise ImportError(f"Invalid JSON: {e}")
        if not isinstance(raw_data, dict) or "boards" not in raw_data:
            raise ImportError("Not a Monday.com API payload (missing 'boards').")
        return raw_data

    def validate(self, parsed_data: Dict[str, Any]) -> bool:
        if not parsed_data.get("boards"):
            raise ImportError("No boards found in Monday.com payload.")
        return True

    def transform_to_prizmAI(self, parsed_data: Dict[str, Any]) -> ImportResult:
        result = ImportResult(source_format="json", source_tool="Monday.com")
        board = (parsed_data.get("boards") or [{}])[0]

        columns_seen: Dict[str, Dict] = {}
        labels_seen: Dict[str, str] = {}

        # Seed columns from groups (preserves Monday's group order).
        for g in board.get("groups", []) or []:
            title = (g.get("title") or "").strip() or "Group"
            if title not in columns_seen:
                columns_seen[title] = {"order": len(columns_seen), "temp_id": f"col_{len(columns_seen)}"}

        items = ((board.get("items_page") or {}).get("items")) or board.get("items") or []
        for idx, item in enumerate(items):
            group_title = ((item.get("group") or {}).get("title") or "").strip() or "To Do"
            if group_title not in columns_seen:
                columns_seen[group_title] = {"order": len(columns_seen), "temp_id": f"col_{len(columns_seen)}"}

            cv = self._column_values(item)
            status = cv.get("status", "")
            label_names: List[str] = []
            for raw in (cv.get("labels", "") or "").split(","):
                lbl = raw.strip()
                if lbl:
                    label_names.append(lbl)
                    labels_seen.setdefault(lbl, self._label_color(len(labels_seen)))

            result.tasks_data.append({
                "title": self._sanitize_string(item.get("name", "Untitled"), max_length=200),
                "description": cv.get("description", "") or "",
                "column_temp_id": columns_seen[group_title]["temp_id"],
                "position": idx,
                "priority": self._normalize_priority(cv.get("priority", "")),
                "progress": self._STATUS_PROGRESS.get(status.lower().strip(), 0),
                "due_date": self._parse_date(cv.get("due_date")),
                "start_date": None,
                "assigned_to_username": cv.get("owner") or None,
                "label_names": label_names,
                "external_id": str(item.get("id")) if item.get("id") else None,
                "complexity_score": 5,
            })
            result.update_stats("tasks_imported")

        for col_name, info in sorted(columns_seen.items(), key=lambda x: x[1]["order"]):
            result.columns_data.append({"name": col_name, "position": info["order"], "temp_id": info["temp_id"]})
            result.update_stats("columns_imported")
        for lbl, color in labels_seen.items():
            result.labels_data.append({"name": lbl, "color": color})
            result.update_stats("labels_imported")

        result.board_data = {
            "name": board.get("name", "Imported from Monday.com"),
            "description": f"Imported {len(result.tasks_data)} items from Monday.com",
        }
        return result

    # ---- helpers ------------------------------------------------------------

    def _column_values(self, item: Dict) -> Dict[str, str]:
        """Pull common fields out of Monday column_values by matching column title."""
        out: Dict[str, str] = {}
        for cv in item.get("column_values", []) or []:
            title = ((cv.get("column") or {}).get("title") or "").lower().strip()
            text = cv.get("text") or ""
            if not text:
                continue
            if title in ("status", "state"):
                out["status"] = text
            elif title in ("owner", "person", "people", "assignee"):
                out["owner"] = text
            elif title == "priority":
                out["priority"] = text
            elif title in ("due date", "date", "deadline"):
                out["due_date"] = text
            elif title in ("notes", "text", "description", "long text"):
                out["description"] = text
            elif title in ("tags", "labels", "label", "dropdown"):
                out["labels"] = (out.get("labels", "") + "," + text).strip(",")
        return out

    def _label_color(self, index: int) -> str:
        colors = ["#61bd4f", "#f2d600", "#ff9f1a", "#eb5a46", "#c377e0",
                  "#0079bf", "#00c2e0", "#51e898", "#ff78cb", "#344563"]
        return colors[index % len(colors)]
