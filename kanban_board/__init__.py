# This will make sure the Celery app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

__all__ = ('celery_app',)


# ---------------------------------------------------------------------------
# Enable SQLite WAL mode on every new database connection.
# WAL allows concurrent reads + a single writer without blocking,
# which virtually eliminates "database is locked" errors from
# Celery Beat's DatabaseScheduler competing with the web server.
# ---------------------------------------------------------------------------
from django.db.backends.signals import connection_created


def _activate_wal_mode(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')


connection_created.connect(_activate_wal_mode)
