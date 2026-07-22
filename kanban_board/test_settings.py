"""
Test settings for PrizmAI Django Project
========================================

This settings file is used during test runs to configure Django appropriately
for testing. It imports from the main settings and overrides settings that
cause issues during testing (like Axes backend requiring request objects).

Usage:
    python manage.py test --settings=kanban_board.test_settings
"""

from .settings import *  # noqa: F401, F403

# =============================================================================
# AUTHENTICATION BACKENDS FOR TESTING
# =============================================================================
# Drop only the Axes backend for testing (it requires request objects). The
# django-rules ObjectPermissionBackend MUST stay — without it, has_perm() for
# object-level permissions like 'prizmai.edit_board' returns False for everyone,
# so any rules-guarded view 403s under tests.
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'rules.permissions.ObjectPermissionBackend',
]

# =============================================================================
# AXES CONFIGURATION FOR TESTING
# =============================================================================
# Disable axes for tests to prevent "request required" errors
AXES_ENABLED = False

# =============================================================================
# BYOK ENCRYPTION KEY FOR TESTING
# =============================================================================
# A fixed, throwaway Fernet key so BYOK encryption/decryption tests work without
# depending on the developer's .env. This is NOT a production secret — it exists
# only to exercise the Fernet round-trip in AIRouter._encrypt_key/_decrypt_key.
AI_KEY_ENCRYPTION_KEY = '-WiWzmB1OcCFAIrVdDpBd39LbDWQOvQ9-4BoztHTgsU='

# Deterministic platform keys so _resolve_provider tests can assert which key the
# router selected without relying on whatever is (or isn't) set in the real env.
GEMINI_API_KEY = 'test-gemini-platform-key'
OPENAI_API_KEY = 'test-openai-platform-key'
ANTHROPIC_API_KEY = 'test-anthropic-platform-key'

# =============================================================================
# CELERY CONFIGURATION FOR TESTING
# =============================================================================
# Use synchronous task execution for tests (no Redis required)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Override broker URL to avoid connection attempts
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'

# =============================================================================
# DATABASE FOR TESTING
# =============================================================================
# Use in-memory SQLite for faster tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'TEST': {
            'NAME': ':memory:',
        }
    }
}

# =============================================================================
# PASSWORD HASHERS FOR TESTING
# =============================================================================
# Use faster password hasher for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# =============================================================================
# EMAIL BACKEND FOR TESTING
# =============================================================================
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# =============================================================================
# CACHES FOR TESTING
# =============================================================================
# Mirror every cache alias the app uses (settings.py defines default, ai_cache,
# session_cache, analytics_cache, local — several backed by Redis in prod) as an
# isolated in-memory cache, so code that does caches['session_cache'] etc. works
# under tests instead of raising InvalidCacheBackendError.
CACHES = {
    alias: {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': f'test-{alias}',
    }
    for alias in ('default', 'ai_cache', 'session_cache', 'analytics_cache', 'local')
}

# =============================================================================
# CHANNELS FOR TESTING
# =============================================================================
# Use in-memory channel layer for tests
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# =============================================================================
# DEBUG MODE FOR TESTING
# =============================================================================
DEBUG = True

# =============================================================================
# LOGGING FOR TESTING
# =============================================================================
# Reduce logging noise during tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'root': {
        'handlers': ['null'],
        'level': 'CRITICAL',
    },
}

# =============================================================================
# STATIC FILES FOR TESTING
# =============================================================================
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# =============================================================================
# MIDDLEWARE ADJUSTMENTS FOR TESTING
# =============================================================================
# Remove middleware that might cause issues in testing
MIDDLEWARE = [m for m in MIDDLEWARE if 'Axes' not in m]  # noqa: F405

