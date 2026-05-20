from django.apps import AppConfig


class AiAssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_assistant'
    verbose_name = 'AI Project Assistant'

    def ready(self):
        # Import signals so post_save handlers register, then wire the
        # cross-app cache-invalidation receivers.
        from ai_assistant import signals  # noqa: F401
        try:
            signals.register_cache_invalidators()
        except Exception:
            # Cache invalidation is best-effort — never block startup.
            pass
