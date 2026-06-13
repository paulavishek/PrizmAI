"""
Regenerate monday_board.xlsx — a fixture mimicking Monday.com's "Export board to Excel".

Run from the repo root:
    python tests/fixtures/import_samples/make_monday_xlsx.py

Layout expected by kanban/utils/import_adapters/monday_adapter.py:
    Row 1: board name (single cell)
    Row 2: board description (single cell)
    Row 3: empty
    Row 4: group name (single cell)        <- group header
    Row 5: column headers                   <- detection keys off this row (index 4)
    Row 6+: task rows
    ...group pattern repeats...
"""
import os

import openpyxl

HEADERS = ["Name", "Owner", "Status", "Due Date", "Priority", "Tags", "Notes"]


def build():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Board"

    rows = []
    # Board metadata
    rows.append(["Product Roadmap (Monday)"])
    rows.append(["Roadmap board exported from Monday.com for import testing."])
    rows.append([])  # empty separator

    # --- Group 1 ---
    rows.append(["This Quarter"])
    rows.append(HEADERS)
    rows.append(["Launch billing v2", "testuser1", "Working on it", "2026-07-15", "High", "billing,backend", "Stripe migration"])
    rows.append(["Redesign settings page", "maria", "Stuck", "2026-07-22", "Medium", "design,ux", "Blocked on specs"])
    rows.append(["Audit access logs", "", "Not Started", "2026-08-01", "Low", "security", "Quarterly compliance audit"])

    # --- Group 2 ---
    rows.append(["Shipped"])
    rows.append(HEADERS)
    rows.append(["Dark mode", "paul.biotech10@gmail.com", "Done", "2026-06-10", "Medium", "frontend", "Rolled out to all users"])
    rows.append(["Onboarding emails", "testuser1", "Done", "2026-06-05", "Low", "marketing,content", "3-part drip series"])

    for row in rows:
        ws.append(row)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monday_board.xlsx")
    wb.save(out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    build()
