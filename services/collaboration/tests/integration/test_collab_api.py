"""
Integration tests for Collaboration API endpoints.
"""
import pytest
from rest_framework import status
from collabapp.models import Collaborator, InviteLink
import uuid


@pytest.mark.django_db
class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check(self, api_client):
        """Test health check returns service status."""
        url = '/api/collab/health/'
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['status'] == 'healthy'
        assert response.data['data']['service'] == 'collaboration'


@pytest.mark.django_db
class TestGenerateInvite:
    """Test invite link generation endpoint."""

    def test_generate_invite(self, authenticated_client, test_user):
        """Test generating an invite link."""
        playlist_id = 1
        url = f'/api/collab/{playlist_id}/invite/'
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_201_CREATED
        assert 'token' in response.data['data']
        assert response.data['data']['playlist_id'] == playlist_id

        # Verify invite was created in database
        invite = InviteLink.objects.get(token=response.data['data']['token'])
        assert invite.playlist_id == playlist_id
        assert invite.created_by_id == test_user.id

    def test_generate_invite_requires_auth(self, api_client):
        """Test generating invite requires authentication."""
        playlist_id = 1
        url = f'/api/collab/{playlist_id}/invite/'
        response = api_client.post(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestJoinViaInvite:
    """Test joining playlist via invite link endpoint."""

    def test_validate_invite_link(self, authenticated_client, test_user):
        """Test validating an invite link."""
        # Create an invite link
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=test_user.id + 1
        )

        url = f'/api/collab/join/{invite.token}/'
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['valid'] is True
        assert response.data['data']['playlist_id'] == 1

    def test_validate_invalid_token(self, authenticated_client):
        """Test validating with invalid token."""
        fake_token = uuid.uuid4()
        url = f'/api/collab/join/{fake_token}/'
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_validate_expired_invite(self, authenticated_client, test_user):
        """Test validating expired invite link."""
        from datetime import timedelta
        from django.utils import timezone

        # Create expired invite
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=test_user.id + 1,
            expires_at=timezone.now() - timedelta(days=1)
        )

        url = f'/api/collab/join/{invite.token}/'
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_join_playlist_success(self, authenticated_client, test_user):
        """Test successfully joining a playlist."""
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=test_user.id + 1
        )

        url = f'/api/collab/join/{invite.token}/'
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['data']['playlist_id'] == 1
        assert response.data['data']['user_id'] == test_user.id

        # Verify collaborator was created
        collab = Collaborator.objects.get(playlist_id=1, user_id=test_user.id)
        assert collab is not None

    def test_join_already_member(self, authenticated_client, test_user):
        """Test joining when already a member."""
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=test_user.id + 1
        )

        # First join
        url = f'/api/collab/join/{invite.token}/'
        response1 = authenticated_client.post(url)
        assert response1.status_code == status.HTTP_201_CREATED

        # Second join (already member)
        response2 = authenticated_client.post(url)
        assert response2.status_code == status.HTTP_200_OK
        assert response2.data['data']['already_member'] is True

    def test_join_requires_auth(self, api_client):
        """Test joining requires authentication."""
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=1
        )

        url = f'/api/collab/join/{invite.token}/'
        response = api_client.post(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCollaboratorList:
    """Test collaborator list endpoint."""

    def test_list_collaborators(self, authenticated_client):
        """Test listing all collaborators for a playlist."""
        playlist_id = 1

        # Create some collaborators
        Collaborator.objects.create(playlist_id=playlist_id, user_id=100)
        Collaborator.objects.create(playlist_id=playlist_id, user_id=101)

        url = f'/api/collab/{playlist_id}/members/'
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 2

    def test_list_empty_collaborators(self, authenticated_client):
        """Test listing collaborators when playlist has none."""
        playlist_id = 999

        url = f'/api/collab/{playlist_id}/members/'
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 0

    def test_remove_collaborator_self(self, authenticated_client, test_user):
        """Test a collaborator removing themselves."""
        playlist_id = 1

        # Add current user as collaborator
        Collaborator.objects.create(playlist_id=playlist_id, user_id=test_user.id)

        url = f'/api/collab/{playlist_id}/members/?user_id={test_user.id}'
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify removal
        exists = Collaborator.objects.filter(
            playlist_id=playlist_id,
            user_id=test_user.id
        ).exists()
        assert exists is False

    def test_remove_collaborator_missing_user_id(self, authenticated_client):
        """Test removing collaborator without user_id parameter."""
        playlist_id = 1

        url = f'/api/collab/{playlist_id}/members/'
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_remove_collaborator_requires_auth(self, api_client):
        """Test removing collaborator requires authentication."""
        playlist_id = 1

        url = f'/api/collab/{playlist_id}/members/'
        response = api_client.delete(url, {'user_id': 100})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMyCollaborations:
    """Test my collaborations endpoint."""

    def test_get_my_collaborations(self, authenticated_client, test_user):
        """Test getting all playlists user collaborates on."""
        # Create collaborations
        Collaborator.objects.create(playlist_id=1, user_id=test_user.id)
        Collaborator.objects.create(playlist_id=2, user_id=test_user.id)
        Collaborator.objects.create(playlist_id=3, user_id=999)  # Different user

        url = '/api/collab/my-collaborations/'
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']['playlist_ids']) == 2
        assert 1 in response.data['data']['playlist_ids']
        assert 2 in response.data['data']['playlist_ids']
        assert 3 not in response.data['data']['playlist_ids']

    def test_get_my_collaborations_empty(self, authenticated_client):
        """Test getting collaborations when user has none."""
        url = '/api/collab/my-collaborations/'
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']['playlist_ids']) == 0

    def test_get_my_collaborations_requires_auth(self, api_client):
        """Test getting collaborations requires authentication."""
        url = '/api/collab/my-collaborations/'
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMyRole:
    """Test my role endpoint."""

    def test_get_my_role_collaborator(self, authenticated_client, test_user):
        """Test getting role when user is a collaborator."""
        playlist_id = 1

        Collaborator.objects.create(
            playlist_id=playlist_id,
            user_id=test_user.id
        )

        url = f'/api/collab/{playlist_id}/my-role/'
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['role'] == 'collaborator'

    def test_get_my_role_not_collaborator(self, authenticated_client):
        """Test getting role when user is not a collaborator."""
        playlist_id = 999

        url = f'/api/collab/{playlist_id}/my-role/'
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_my_role_requires_auth(self, api_client):
        """Test getting role requires authentication."""
        playlist_id = 1

        url = f'/api/collab/{playlist_id}/my-role/'
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
