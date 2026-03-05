from django.apps import AppConfig


class KnowledgeGraphConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge_graph'

    def ready(self):
        """Import signal handlers when the app is ready."""
        import knowledge_graph.signals  # noqa
