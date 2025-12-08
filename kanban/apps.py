from django.apps import AppConfig


class KanbanConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kanban'
    
    def ready(self):
        """Import signal handlers when the app is ready"""
        import kanban.signals  # noqa
