import sqlite3
conn = sqlite3.connect('db.sqlite3')

# Check for old kanban_board_members M2M table
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%board_member%' ORDER BY name")
print("Tables matching 'board_member':", [r[0] for r in cursor.fetchall()])

# Check all FK constraints that reference kanban_board
print("\n--- All tables with FK to kanban_board ---")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for (table_name,) in tables:
    fks = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    for fk in fks:
        if fk[2] == 'kanban_board':
            print(f"  {table_name}.{fk[3]} -> kanban_board.{fk[4]}  on_delete={fk[6]}")

conn.close()
