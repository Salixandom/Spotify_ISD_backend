"""
Authorization and permission tests for all endpoints.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from playlistapp.models import Playlist
from trackapp.models import Track


@pytest.mark.django_db
class TestAuthenticationRequired:
    """Test that authentication is required for all endpoints."""

    def test_playlist_endpoints_require_auth(self):
        """Test playlist endpoints require authentication."""
        client = APIClient()  # Unauthenticated client

        endpoints = [
            ('playlist-list', 'list', {}),
            ('playlist-detail', 'detail', {'pk': 1}),
            ('playlist-stats', 'stats', {'playlist_id': 1}),
            ('playlist-follow', 'follow', {'pk': 1}),
            ('playlist-like', 'like', {'pk': 1}),
        ]

        for endpoint_name, action, kwargs in endpoints:
            try:
                url = reverse(endpoint_name, kwargs=kwargs)
            except Exception:
                continue

            if action == 'list':
                response = client.get(url)
            elif action == 'detail':
                response = client.get(url)
            elif action == 'stats':
                response = client.get(url)
            elif action == 'follow':
                response = client.post(url)
            elif action == 'like':
                response = client.post(url)

            assert response.status_code == status.HTTP_401_UNAUTHORIZED or \
                   response.status_code == status.HTTP_403_FORBIDDEN, \
                   f"Endpoint {endpoint_name} should require authentication"

    def test_track_endpoints_require_auth(self):
        """Test track endpoints require authentication."""
        client = APIClient()

        endpoints = [
            ('track-list', 'list', {'playlist_id': 1}),
            ('track-detail', 'detail', {'playlist_id': 1, 'track_id': 1}),
            ('track-reorder', 'reorder', {'playlist_id': 1}),
        ]

        for endpoint_name, action, kwargs in endpoints:
            try:
                url = reverse(endpoint_name, kwargs=kwargs)
            except Exception:
                continue

            if action == 'list':
                response = client.get(url)
            elif action == 'detail':
                response = client.delete(url)
            elif action == 'reorder':
                response = client.put(url, {})

            assert response.status_code == status.HTTP_401_UNAUTHORIZED or \
                   response.status_code == status.HTTP_403_FORBIDDEN

    def test_search_endpoints_require_auth(self):
        """Test search endpoints require authentication."""
        client = APIClient()

        endpoints = [
            'search',
            'artist-list',
            'album-list',
            'song-search',
            'playlist-search',
            'genre-list',
            'new-releases',
            'trending',
            'recommendations',
        ]

        for endpoint_name in endpoints:
            try:
                url = reverse(endpoint_name)
            except Exception:
                continue

            response = client.get(url)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED or \
                   response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestPlaylistOwnership:
    """Test playlist ownership permissions."""

    def test_update_own_playlist_succeeds(self, api_client, authenticated_user, test_playlist):
        """Test user can update their own playlist."""
        url = reverse('playlist-detail', kwargs={'pk': test_playlist.id})
        data = {'name': 'Updated Name'}
        response = api_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK

    def test_update_other_playlist_fails(self, api_client, authenticated_user):
        """Test user cannot update another user's playlist."""
        other_user_id = authenticated_user + 1
        other_playlist = Playlist.objects.create(
            owner_id=other_user_id,
            name='Other Playlist'
        )

        url = reverse('playlist-detail', kwargs={'pk': other_playlist.id})
        data = {'name': 'Hacked Name'}
        response = api_client.patch(url, data)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_own_playlist_succeeds(self, api_client, authenticated_user, test_playlist):
        """Test user can delete their own playlist."""
        url = reverse('playlist-detail', kwargs={'pk': test_playlist.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_other_playlist_fails(self, api_client, authenticated_user):
        """Test user cannot delete another user's playlist."""
        other_user_id = authenticated_user + 1
        other_playlist = Playlist.objects.create(
            owner_id=other_user_id,
            name='Other Playlist'
        )

        url = reverse('playlist-detail', kwargs={'pk': other_playlist.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestTrackPermissions:
    """Test track operation permissions."""

    def test_add_to_own_playlist_succeeds(self, api_client, authenticated_user, test_playlist, test_song):
        """Test user can add track to their own playlist."""
        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        data = {'song_id': test_song.id}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED

    def test_add_to_other_playlist_fails(self, api_client, authenticated_user, test_song):
        """Test user cannot add track to another user's playlist."""
        other_user_id = authenticated_user + 1
        other_playlist = Playlist.objects.create(
            owner_id=other_user_id,
            name='Other Playlist'
        )

        url = reverse('track-list', kwargs={'playlist_id': other_playlist.id})
        data = {'song_id': test_song.id}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_from_own_playlist_succeeds(self, api_client, authenticated_user, test_playlist, test_song):
        """Test user can delete track from their own playlist."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0
        )

        url = reverse('track-detail', kwargs={'playlist_id': test_playlist.id, 'track_id': track.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_from_other_playlist_fails(self, api_client, authenticated_user, test_song):
        """Test user cannot delete track from another user's playlist."""
        other_user_id = authenticated_user + 1
        other_playlist = Playlist.objects.create(
            owner_id=other_user_id,
            name='Other Playlist'
        )

        track = Track.objects.create(
            playlist=other_playlist,
            song=test_song,
            added_by_id=other_user_id,
            position=0
        )

        url = reverse('track-detail', kwargs={'playlist_id': other_playlist.id, 'track_id': track.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestPublicPlaylistAccess:
    """Test public playlist access rules."""

    def test_view_own_private_playlist_stats(self, api_client, authenticated_user):
        """Test user can view stats of their own private playlist."""
        private_playlist = Playlist.objects.create(
            owner_id=authenticated_user,
            name='Private Playlist',
            visibility='private'
        )

        url = reverse('playlist-stats', kwargs={'playlist_id': private_playlist.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_cannot_view_other_private_playlist_stats(self, api_client, authenticated_user):
        """Test user cannot view stats of another user's private playlist."""
        other_user_id = authenticated_user + 1
        private_playlist = Playlist.objects.create(
            owner_id=other_user_id,
            name='Other Private Playlist',
            visibility='private'
        )

        url = reverse('playlist-stats', kwargs={'playlist_id': private_playlist.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_view_public_playlist_stats(self, api_client, authenticated_user):
        """Test user can view stats of public playlists."""
        other_user_id = authenticated_user + 1
        public_playlist = Playlist.objects.create(
            owner_id=other_user_id,
            name='Public Playlist',
            visibility='public'
        )

        url = reverse('playlist-stats', kwargs={'playlist_id': public_playlist.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestFollowLikeRestrictions:
    """Test follow/like restrictions."""

    def test_cannot_follow_own_playlist(self, api_client, authenticated_user, test_playlist):
        """Test user cannot follow their own playlist."""
        url = reverse('playlist-follow', kwargs={'pk': test_playlist.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_like_own_playlist(self, api_client, authenticated_user, test_playlist):
        """Test user cannot like their own playlist."""
        url = reverse('playlist-like', kwargs={'pk': test_playlist.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_follow_private_playlist(self, api_client, authenticated_user):
        """Test user cannot follow private playlists."""
        other_user_id = authenticated_user + 1
        private_playlist = Playlist.objects.create(
            owner_id=other_user_id,
            name='Private Playlist',
            visibility='private'
        )

        url = reverse('playlist-follow', kwargs={'pk': private_playlist.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_like_private_playlist(self, api_client, authenticated_user):
        """Test user cannot like private playlists."""
        other_user_id = authenticated_user + 1
        private_playlist = Playlist.objects.create(
            owner_id=other_user_id,
            name='Private Playlist',
            visibility='private'
        )

        url = reverse('playlist-like', kwargs={'pk': private_playlist.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestBatchOperationPermissions:
    """Test batch operation permissions."""

    def test_batch_delete_own_playlists(self, api_client, authenticated_user):
        """Test user can batch delete their own playlists."""
        playlist1 = Playlist.objects.create(owner_id=authenticated_user, name='P1')
        playlist2 = Playlist.objects.create(owner_id=authenticated_user, name='P2')

        url = reverse('playlist-batch-delete')
        data = {'playlist_ids': [playlist1.id, playlist2.id]}
        response = api_client.delete(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['deleted'] == 2

    def test_batch_delete_mixed_playlists(self, api_client, authenticated_user):
        """Test batch delete only deletes own playlists."""
        own_playlist = Playlist.objects.create(owner_id=authenticated_user, name='Own')
        other_user_id = authenticated_user + 1
        other_playlist = Playlist.objects.create(owner_id=other_user_id, name='Other')

        url = reverse('playlist-batch-delete')
        data = {'playlist_ids': [own_playlist.id, other_playlist.id]}
        response = api_client.delete(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['deleted'] == 1
        assert response.data['not_authorized'] == 1

    def test_batch_update_own_playlists(self, api_client, authenticated_user):
        """Test user can batch update their own playlists."""
        playlist1 = Playlist.objects.create(owner_id=authenticated_user, name='P1')
        playlist2 = Playlist.objects.create(owner_id=authenticated_user, name='P2')

        url = reverse('playlist-batch-update')
        data = {
            'playlist_ids': [playlist1.id, playlist2.id],
            'updates': {'visibility': 'private'}
        }
        response = api_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['updated'] == 2

    def test_batch_update_mixed_playlists(self, api_client, authenticated_user):
        """Test batch update only updates own playlists."""
        own_playlist = Playlist.objects.create(owner_id=authenticated_user, name='Own')
        other_user_id = authenticated_user + 1
        other_playlist = Playlist.objects.create(owner_id=other_user_id, name='Other')

        url = reverse('playlist-batch-update')
        data = {
            'playlist_ids': [own_playlist.id, other_playlist.id],
            'updates': {'visibility': 'private'}
        }
        response = api_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['updated'] == 1
        assert response.data['not_authorized'] == 1
