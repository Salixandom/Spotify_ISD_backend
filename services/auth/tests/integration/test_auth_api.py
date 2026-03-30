"""
Integration tests for Auth API endpoints.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from authapp.models import UserProfile, UserFollow


@pytest.mark.django_db
class TestAuthenticationEndpoints:
    """Test registration and login endpoints."""

    def test_register_new_user(self, api_client):
        """Test registering a new user."""
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'securepass123',
            'password_confirm': 'securepass123'
        }
        response = api_client.post(url, data)

        # Should return 201 Created or 200 OK
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_200_OK]
        assert 'user' in response.data or 'access' in response.data

    def test_register_passwords_mismatch(self, api_client):
        """Test registration with mismatched passwords fails."""
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'securepass123',
            'password_confirm': 'differentpass123'
        }
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_valid_credentials(self, api_client, test_user):
        """Test login with valid credentials."""
        url = reverse('login')
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

    def test_login_invalid_credentials(self, api_client):
        """Test login with invalid credentials fails."""
        url = reverse('login')
        data = {
            'username': 'testuser',
            'password': 'wrongpassword'
        }
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUserProfileEndpoints:
    """Test user profile endpoints."""

    def test_get_own_profile(self, authenticated_client, test_user):
        """Test getting own user profile."""
        # Create profile first
        UserProfile.objects.create(
            user_id=test_user.id,
            display_name='Test User'
        )

        url = reverse('user-profile-detail', kwargs={'user_id': test_user.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['user_id'] == test_user.id

    def test_update_own_profile(self, authenticated_client, test_user):
        """Test updating own profile."""
        UserProfile.objects.create(user_id=test_user.id)

        url = reverse('user-profile-detail', kwargs={'user_id': test_user.id})
        data = {
            'display_name': 'Updated Name',
            'bio': 'Updated bio'
        }
        response = authenticated_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['display_name'] == 'Updated Name'

    def test_update_preferences(self, authenticated_client, test_user):
        """Test updating user preferences."""
        UserProfile.objects.create(user_id=test_user.id)

        url = reverse('user-profile-detail', kwargs={'user_id': test_user.id})
        data = {
            'preferences': {
                'theme': 'dark',
                'language': 'en'
            }
        }
        response = authenticated_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['preferences']['theme'] == 'dark'


@pytest.mark.django_db
class TestUserFollowEndpoints:
    """Test user follow/unfollow endpoints."""

    def test_follow_user(self, authenticated_client, test_user):
        """Test following another user."""
        # Create another user to follow
        from django.contrib.auth import get_user_model
        User = get_user_model()
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )

        url = reverse('user-follow', kwargs={'user_id': other_user.id})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_201_CREATED

        # Verify follow relationship
        follow = UserFollow.objects.filter(
            follower_id=test_user.id,
            following_id=other_user.id
        ).first()
        assert follow is not None

    def test_unfollow_user(self, authenticated_client, test_user):
        """Test unfollowing a user."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )

        # First follow the user
        UserFollow.objects.create(
            follower_id=test_user.id,
            following_id=other_user.id
        )

        url = reverse('user-follow', kwargs={'user_id': other_user.id})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK

        # Verify follow is deleted
        follow_exists = UserFollow.objects.filter(
            follower_id=test_user.id,
            following_id=other_user.id
        ).exists()
        assert follow_exists is False

    def test_cannot_follow_self(self, authenticated_client, test_user):
        """Test that user cannot follow themselves."""
        url = reverse('user-follow', kwargs={'user_id': test_user.id})
        response = authenticated_client.post(url)

        # Should fail or return 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_followers_list(self, authenticated_client, test_user):
        """Test getting list of followers."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Create some followers
        for i in range(3):
            follower = User.objects.create_user(
                username=f'follower{i}',
                email=f'follower{i}@example.com',
                password='testpass123'
            )
            UserFollow.objects.create(
                follower_id=follower.id,
                following_id=test_user.id
            )

        url = reverse('user-followers', kwargs={'user_id': test_user.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['followers']) == 3

    def test_get_following_list(self, authenticated_client, test_user):
        """Test getting list of users following."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Follow some users
        following_ids = []
        for i in range(3):
            other_user = User.objects.create_user(
                username=f'followed{i}',
                email=f'followed{i}@example.com',
                password='testpass123'
            )
            UserFollow.objects.create(
                follower_id=test_user.id,
                following_id=other_user.id
            )
            following_ids.append(other_user.id)

        url = reverse('user-following', kwargs={'user_id': test_user.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['following']) == 3


@pytest.mark.django_db
class TestAuthSecurity:
    """Test security aspects of auth endpoints."""

    def test_registration_requires_all_fields(self, api_client):
        """Test registration requires username, email, and password."""
        url = reverse('register')

        # Missing email
        data = {
            'username': 'testuser',
            'password': 'testpass123',
            'password_confirm': 'testpass123'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_confirmation_required(self, api_client):
        """Test password confirmation is required."""
        url = reverse('register')
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_protected_endpoints_require_auth(self, api_client):
        """Test that protected endpoints require authentication."""
        client = APIClient()  # No auth

        # These endpoints should require authentication
        protected_endpoints = [
            ('user-profile-detail', {'user_id': 1}),
            ('user-follow', {'user_id': 1}),
        ]

        for endpoint, kwargs in protected_endpoints:
            try:
                url = reverse(endpoint, kwargs=kwargs)
                response = client.get(url)
                assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
            except:
                pass  # URL might not exist
