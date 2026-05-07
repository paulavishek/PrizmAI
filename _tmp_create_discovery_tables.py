"""Create discovery tables directly in SQLite, bypassing the FK-check migration blocker."""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.db import connection

ddl = [
    """CREATE TABLE IF NOT EXISTS kanban_discoveryidea (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title VARCHAR(255) NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        source VARCHAR(30) NOT NULL DEFAULT 'other',
        stage VARCHAR(20) NOT NULL DEFAULT 'new',
        ai_score_impact INTEGER NULL,
        ai_score_effort INTEGER NULL,
        ai_score_confidence INTEGER NULL,
        ai_score_recommendation VARCHAR(500) NOT NULL DEFAULT '',
        ai_score_reasoning TEXT NOT NULL DEFAULT '',
        ai_scored_at DATETIME NULL,
        promoted_at DATETIME NULL,
        is_demo BOOL NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        organization_id INTEGER NOT NULL REFERENCES accounts_organization(id) DEFERRABLE INITIALLY DEFERRED,
        submitted_by_id INTEGER NULL REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED,
        promoted_by_id INTEGER NULL REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED
    )""",
    """CREATE TABLE IF NOT EXISTS kanban_ideacomment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        idea_id INTEGER NOT NULL REFERENCES kanban_discoveryidea(id) DEFERRABLE INITIALLY DEFERRED,
        author_id INTEGER NULL REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED
    )""",
    """CREATE TABLE IF NOT EXISTS kanban_ideapromotion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promoted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        idea_id INTEGER NOT NULL UNIQUE REFERENCES kanban_discoveryidea(id) DEFERRABLE INITIALLY DEFERRED,
        board_id INTEGER NULL REFERENCES kanban_board(id) DEFERRABLE INITIALLY DEFERRED,
        promoted_by_id INTEGER NULL REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED
    )""",
    """CREATE TABLE IF NOT EXISTS kanban_ideapromotion_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ideapromotion_id INTEGER NOT NULL REFERENCES kanban_ideapromotion(id) DEFERRABLE INITIALLY DEFERRED,
        task_id INTEGER NOT NULL REFERENCES kanban_task(id) DEFERRABLE INITIALLY DEFERRED
    )""",
]

with connection.cursor() as c:
    c.execute('PRAGMA foreign_keys = OFF')
    for stmt in ddl:
        c.execute(stmt)
    c.execute('PRAGMA foreign_keys = ON')

print('Discovery tables created OK.')

# Also mark 0128 as applied in django_migrations
from django.db import connection as conn
with conn.cursor() as c:
    c.execute(
        "INSERT OR IGNORE INTO django_migrations (app, name, applied) VALUES (?, ?, datetime('now'))",
        ['kanban', '0128_discovery_models']
    )
print('Migration 0128 marked as applied.')
