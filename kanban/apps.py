from django.apps import AppConfig


class KanbanConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kanban'
    
    def ready(self):
        """Import signal handlers and register RBAC rules when the app is ready"""
        import kanban.signals  # noqa
        import kanban.permissions  # noqa — registers django-rules predicates & perms

        # Enable SQLite WAL (Write-Ahead Logging) mode for every new connection.
        # WAL allows concurrent reads and a single writer without readers blocking
        # writers, which eliminates the "database is locked" errors that occur when
        # Celery Beat's DatabaseScheduler writes schedule entries at the same time
        # as Daphne or a Celery worker holds a read/write lock.
        from django.db.backends.signals import connection_created
        from django.conf import settings

        def _enable_wal(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                connection.cursor().execute('PRAGMA journal_mode=WAL;')
                connection.cursor().execute('PRAGMA synchronous=NORMAL;')

        connection_created.connect(_enable_wal)
