from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analytics'
    verbose_name = 'User Analytics & Feedback'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import analytics.signals  # noqa
        except ImportError:
            pass
