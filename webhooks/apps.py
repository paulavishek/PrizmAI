"""
Webhooks App Configuration
"""
from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'webhooks'
    verbose_name = 'Webhooks & Event System'
    
    def ready(self):
        # Import signal handlers
        import webhooks.signals
