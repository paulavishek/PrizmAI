---
name: project_strategy_dropdown_scoping
description: Strategy dropdowns/lookups must use get_user_strategies(); create_board leaked all-tenant strategies into demo
metadata:
  type: project
---

The **Link to Strategy** dropdown in `create_board` (kanban/views.py) and its `selected_strategy` lookup both queried `Strategy.objects` unscoped, so demo users saw every tenant's strategies (display leak) and a crafted `strategy_id` could link a board cross-tenant (IDOR). Fixed June 2026 by routing both through `get_user_strategies(request.user)` (kanban/utils/demo_protection.py) — the demo/workspace-aware helper `edit_board` already used.

**Why:** demo is one shared org; only per-user board copies are isolated, so any unscoped Strategy query bleeds. See [[project_demo_sandbox_isolation_model]] and [[project_rbac_enforcement]].

**How to apply:** any strategy list or `.get(id=...)` lookup in a view must go through `get_user_strategies()`, never raw `Strategy.objects`. Same pattern applies to missions (`get_user_missions`) and boards (`get_user_boards`).
