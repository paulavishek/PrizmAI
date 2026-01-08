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
# Use only the ModelBackend for testing to avoid Axes requiring request objects
# This is safe for testing because we're not testing brute force protection here

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# =============================================================================
# AXES CONFIGURATION FOR TESTING
# =============================================================================
# Disable axes for tests to prevent "request required" errors
AXES_ENABLED = False

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
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
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

