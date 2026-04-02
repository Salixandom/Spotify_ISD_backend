"""
Pytest configuration and shared fixtures for collaboration service.
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
    Create an authenticated API client.
    """
    # For collaboration service, auth might be handled differently
    # Adjust based on actual auth implementation
    api_client.force_authenticate(user=test_user)
    return api_client


@pytest.fixture
def test_playlist_id():
    """
    Return a test playlist ID.
    """
    return 123


@pytest.fixture
def test_collaborator(test_user, test_playlist_id):
    """
    Create a test collaborator.
    """
    from collabapp.models import Collaborator

    collaborator = Collaborator.objects.create(
        playlist_id=test_playlist_id,
        user_id=test_user.id
    )
    return collaborator
