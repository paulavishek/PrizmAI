"""
Pytest configuration for PrizmAI Django Project
=================================================

This file configures pytest and provides fixtures for testing.
"""

import os
import django
from django.conf import settings

# Set the Django settings module for pytest
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.test_settings')


def pytest_configure():
    """Configure Django before running tests."""
    django.setup()


import pytest
from django.test import Client
from django.contrib.auth.models import User


@pytest.fixture
def client():
    """Provide a Django test client."""
    return Client()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def admin_user(db):
    """Create a test admin user."""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )


@pytest.fixture
def authenticated_client(client, user):
    """Provide an authenticated Django test client."""
    client.force_login(user)
    return client


@pytest.fixture
def admin_client(client, admin_user):
    """Provide an admin-authenticated Django test client."""
    client.force_login(admin_user)
    return client
