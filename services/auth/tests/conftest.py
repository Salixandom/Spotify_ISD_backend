"""
Pytest configuration and shared fixtures for auth service.
"""
import pytest
import django
from django.conf import settings

# Configure Django settings for tests
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'rest_framework',
            'rest_framework_simplejwt',
            'authapp',
        ],
        SECRET_KEY='test-secret-key',
        USE_TZ=True,
    )

    django.setup()


@pytest.fixture(autouse=True)
def enable_db_access(db):
    """
    Enable database access for all tests.
    """
    pass


@pytest.fixture
def api_client():
    """
    Provide an API client for making requests.
    """
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def test_user():
    """
    Create a test user.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )

    return user


@pytest.fixture
def authenticated_client(api_client, test_user):
    """
    Create an authenticated API client with JWT token.
    """
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(test_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    return api_client
