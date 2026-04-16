import sqlite3
conn = sqlite3.connect('db.sqlite3')

# Check celery-beat tables
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'django_celery_beat%'")
print("Celery beat tables:")
for r in cursor.fetchall():
    print(f"  {r[0]}")
    fks = conn.execute(f"PRAGMA foreign_key_list({r[0]})").fetchall()
    for fk in fks:
        print(f"    FK: {fk[3]} -> {fk[2]}.{fk[4]} on_delete={fk[6]}")

# Check if PRAGMA foreign_keys is ON in Django
print("\n--- PRAGMA foreign_keys ---")
cursor = conn.execute("PRAGMA foreign_keys")
print(f"foreign_keys = {cursor.fetchone()[0]}")

# Check for any tables with FK to kanban_board that aren't in our model list
print("\n--- Tables with FKs referencing kanban_board (not models) ---")
all_tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
for t in sorted(all_tables):
    fks = conn.execute(f"PRAGMA foreign_key_list({t})").fetchall()
    for fk in fks:
        if fk[2] == 'kanban_board':
            print(f"  {t}.{fk[3]} -> kanban_board.{fk[4]}  on_update={fk[5]} on_delete={fk[6]}")

conn.close()
