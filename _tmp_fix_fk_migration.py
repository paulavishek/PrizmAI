import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
import django
django.setup()

from django.db import connection

print("=== Cleaning orphaned FK rows ===")
with connection.cursor() as c:
    # Disable FK enforcement so we can delete in any order
    c.execute("PRAGMA foreign_keys = OFF")

    # Delete stakeholdertaskinvolvement rows whose task_id no longer exists
    c.execute("DELETE FROM kanban_stakeholdertaskinvolvement WHERE task_id NOT IN (SELECT id FROM kanban_task)")
    print(f"  Deleted {c.rowcount} rows from kanban_stakeholdertaskinvolvement")

    # Delete stakeholdertaskinvolvement rows whose stakeholder_id no longer exists
    c.execute("DELETE FROM kanban_stakeholdertaskinvolvement WHERE stakeholder_id NOT IN (SELECT id FROM kanban_projectstakeholder)")
    print(f"  Deleted {c.rowcount} orphaned involvement rows (dangling stakeholder ref)")

    # Delete projectstakeholder rows whose board_id no longer exists
    c.execute("DELETE FROM kanban_projectstakeholder WHERE board_id NOT IN (SELECT id FROM kanban_board)")
    print(f"  Deleted {c.rowcount} rows from kanban_projectstakeholder")

    # Delete projectsignal rows whose board_id no longer exists
    c.execute("DELETE FROM kanban_projectsignal WHERE board_id NOT IN (SELECT id FROM kanban_board)")
    print(f"  Deleted {c.rowcount} rows from kanban_projectsignal")

    # Re-enable FK enforcement
    c.execute("PRAGMA foreign_keys = ON")

print("\n=== Re-checking FK violations ===")
with connection.cursor() as c:
    c.execute("PRAGMA foreign_key_check")
    remaining = c.fetchall()

if remaining:
    print(f"Still {len(remaining)} violation(s) remaining:")
    for r in remaining:
        print(f"  table={r[0]} rowid={r[1]} parent={r[2]} fkid={r[3]}")
else:
    print("All FK violations cleared. You can now run: python manage.py migrate")
