"""
Migration orchestrator — turns raw connector data into PrizmAI's hierarchy.

Structural mapping (general, provider-agnostic):
    Project  -> Strategy   (under an auto-created Mission)
    Epic     -> Board      (grouping level; providers without epics -> one board)
    Issue    -> Task

Reuse: the actual translation (status->column, priority, labels, story points,
assignees) stays entirely in the existing import adapters. This orchestrator only
(a) groups the raw issues into per-board buckets, (b) runs the matching adapter on
each bucket, and (c) wires the created boards to a Strategy.

Entry point: ``run_migration(...)`` -> ``MigrationResult``.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from kanban.utils.import_adapters import AdapterFactory

logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    strategy: Any = None
    mission: Any = None
    boards: List[Any] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def bump(self, key: str, n: int = 1):
        self.stats[key] = self.stats.get(key, 0) + n


def _resolve_workspace(user):
    """Same workspace resolution as file import (never the demo workspace)."""
    ws = None
    try:
        ws = user.profile.active_workspace
        if ws and ws.is_demo:
            ws = None
    except Exception:
        ws = None
    if not ws:
        from kanban.workspace_utils import get_or_create_real_workspace
        ws = get_or_create_real_workspace(user)
    return ws


def _group_raw_by_epic(provider: str, raw: Dict) -> List[Dict[str, Any]]:
    """
    Split raw connector data into per-board buckets.

    Returns a list of ``{"name": <board name>, "raw": <adapter-shaped subset>}``.
    For Jira, group issues by their normalised Epic (``fields.epic``); issues with
    no epic collect into a "General" board. Providers without an epic concept (or
    data with no epics at all) yield a single bucket = the whole project.
    """
    if provider == "jira" and isinstance(raw, dict) and "issues" in raw:
        buckets: Dict[str, Dict] = {}
        order: List[str] = []
        for issue in raw.get("issues", []) or []:
            fields = issue.get("fields", {}) or {}
            # An Epic is itself an issue in Jira. Epics become Boards (grouping
            # containers), so skip them here — otherwise the Epic card would also
            # be imported as a task in the "General" board.
            issue_type = ((fields.get("issuetype") or {}).get("name") or "").lower()
            if issue_type == "epic":
                continue
            epic = fields.get("epic") or {}
            if isinstance(epic, dict) and epic.get("key"):
                key = epic["key"]
                name = epic.get("name") or epic["key"]
            else:
                key = "__general__"
                name = "General"
            if key not in buckets:
                buckets[key] = {"name": name, "issues": []}
                order.append(key)
            buckets[key]["issues"].append(issue)

        # A single bucket that is only "General" means the project has no epics —
        # keep it as one board named after the project (name=None -> caller fills in).
        if order == ["__general__"]:
            return [{"name": None, "raw": raw}]

        result = []
        for key in order:
            result.append({"name": buckets[key]["name"], "raw": {"issues": buckets[key]["issues"]}})
        return result

    # Default: one board for the whole project.
    return [{"name": None, "raw": raw}]


def run_migration(
    *,
    provider: str,
    raw: Any,
    adapter_name: str,
    project_name: str,
    user,
    organization,
    session,
    progress_cb: Optional[Callable[[int, str], None]] = None,
) -> MigrationResult:
    """
    Build a Strategy + Boards + Tasks from raw connector data.

    Args:
        provider: SourceConnection.provider (e.g. "jira").
        raw: raw data from ``connector.fetch_project`` (adapter-shaped).
        adapter_name: registry key in AdapterFactory (e.g. "jira").
        project_name: source project name, used for the Mission/Strategy title.
        user / organization / session: as required by _create_board_from_import_result.
        progress_cb: optional callback(percent:int, message:str) for live progress.
    """
    from kanban.models import Mission, Strategy  # local import to avoid cycles
    from kanban.views import _create_board_from_import_result

    def progress(pct, msg):
        if progress_cb:
            try:
                progress_cb(pct, msg)
            except Exception:
                logger.debug("progress_cb failed", exc_info=True)

    result = MigrationResult()
    ws = _resolve_workspace(user)

    progress(10, f"Preparing '{project_name}'…")

    # Project -> Mission + Strategy
    mission = Mission.objects.create(
        name=f"{project_name} (migrated from {provider.title()})",
        description=f"Auto-created during migration of '{project_name}' from {provider.title()}.",
        created_by=user,
        owner=user,
        workspace=ws,
    )
    strategy = Strategy.objects.create(
        name=project_name,
        description=f"Migrated from {provider.title()}.",
        mission=mission,
        created_by=user,
        owner=user,
        workspace=ws,
    )
    result.mission = mission
    result.strategy = strategy

    # Epic -> Board buckets
    buckets = _group_raw_by_epic(provider, raw)
    total = len(buckets) or 1
    factory = AdapterFactory()

    for idx, bucket in enumerate(buckets):
        bucket_name = bucket["name"] or project_name
        progress(
            20 + int(60 * idx / total),
            f"Importing '{bucket_name}' ({idx + 1}/{total})…",
        )

        import_result = factory.import_with_adapter(
            adapter_name, json.dumps(bucket["raw"]), f"{provider}.json"
        )
        if not import_result.success:
            for err in import_result.errors:
                result.warnings.append(f"{bucket_name}: {err}")
            continue

        # Board title = epic/bucket name (overrides the adapter's project-derived name).
        import_result.board_data["name"] = bucket_name[:100]

        board = _create_board_from_import_result(import_result, user, organization, session)
        # Wire the board into the Strategy (and keep workspace consistent).
        board.strategy = strategy
        if ws and board.workspace_id != ws.id:
            board.workspace = ws
            board.save(update_fields=["strategy", "workspace"])
        else:
            board.save(update_fields=["strategy"])

        result.boards.append(board)
        result.bump("boards_created")
        result.bump("tasks_imported", import_result.stats.get("tasks_imported", 0))
        result.bump("labels_imported", import_result.stats.get("labels_imported", 0))

    progress(85, "Finalising…")
    logger.info(
        "Migration complete: provider=%s project=%s boards=%d tasks=%d",
        provider, project_name, result.stats.get("boards_created", 0),
        result.stats.get("tasks_imported", 0),
    )
    return result
