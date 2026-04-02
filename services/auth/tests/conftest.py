"""
Pytest configuration and shared fixtures for auth service.
"""
import pytest


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
