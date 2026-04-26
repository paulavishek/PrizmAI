import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()
from django.db import connection

cursor = connection.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS kanban_savedbrief (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(120) NOT NULL,
    audience VARCHAR(30) NOT NULL,
    purpose VARCHAR(30) NOT NULL,
    mode VARCHAR(30) NOT NULL,
    audience_label VARCHAR(80) NOT NULL DEFAULT '',
    purpose_label VARCHAR(80) NOT NULL DEFAULT '',
    mode_label VARCHAR(80) NOT NULL DEFAULT '',
    slides_json TEXT NOT NULL,
    full_text TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    board_id INTEGER NOT NULL REFERENCES kanban_board(id) DEFERRABLE INITIALLY DEFERRED,
    user_id INTEGER NOT NULL REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED
)""")
print('Table created successfully')

# Create indexes
cursor.execute("CREATE INDEX IF NOT EXISTS idx_savedbrief_board_user ON kanban_savedbrief(board_id, user_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_savedbrief_created ON kanban_savedbrief(created_at DESC)")
print('Indexes created')

# Verify
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kanban_savedbrief'")
print('Table exists:', cursor.fetchone())
