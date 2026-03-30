"""
Integration tests for Playlist API endpoints.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from playlistapp.models import Playlist, UserPlaylistFollow, UserPlaylistLike


@pytest.mark.django_db
class TestPlaylistViewSet:
    """Test Playlist API endpoints."""

    def test_list_playlists_authenticated(self, api_client, authenticated_user):
        """Test listing playlists when authenticated."""
        Playlist.objects.create(owner_id=authenticated_user, name='My Playlist')

        url = reverse('playlist-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1

    def test_create_playlist(self, api_client, authenticated_user):
        """Test creating a new playlist."""
        url = reverse('playlist-list')
        data = {
            'name': 'New Playlist',
            'description': 'My new playlist',
            'visibility': 'public',
            'playlist_type': 'solo',
            'max_songs': 50
        }
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Playlist'
        assert response.data['owner_id'] == authenticated_user

    def test_retrieve_playlist(self, api_client, authenticated_user, test_playlist):
        """Test retrieving a specific playlist."""
        url = reverse('playlist-detail', kwargs={'pk': test_playlist.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == test_playlist.id
        assert response.data['name'] == test_playlist.name

    def test_update_own_playlist(self, api_client, authenticated_user, test_playlist):
        """Test updating own playlist."""
        url = reverse('playlist-detail', kwargs={'pk': test_playlist.id})
        data = {'name': 'Updated Playlist Name'}
        response = api_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Playlist Name'

    def test_delete_own_playlist(self, api_client, authenticated_user, test_playlist):
        """Test deleting own playlist."""
        url = reverse('playlist-detail', kwargs={'pk': test_playlist.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_filter_by_visibility(self, api_client, authenticated_user):
        """Test filtering playlists by visibility."""
        Playlist.objects.create(owner_id=authenticated_user, name='Public', visibility='public')
        Playlist.objects.create(owner_id=authenticated_user, name='Private', visibility='private')

        url = reverse('playlist-list')
        response = api_client.get(url, {'visibility': 'public'})

        assert response.status_code == status.HTTP_200_OK
        assert all(p['visibility'] == 'public' for p in response.data['results'])

    def test_search_playlists(self, api_client, authenticated_user):
        """Test searching playlists by name/description."""
        Playlist.objects.create(
            owner_id=authenticated_user,
            name='Rock Classics',
            description='Classic rock songs'
        )

        url = reverse('playlist-list')
        response = api_client.get(url, {'q': 'Rock'})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) > 0


@pytest.mark.django_db
class TestPlaylistStatsView:
    """Test playlist statistics endpoint."""

    def test_get_playlist_stats(self, api_client, authenticated_user, test_playlist):
        """Test retrieving playlist statistics."""
        url = reverse('playlist-stats', kwargs={'playlist_id': test_playlist.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'total_tracks' in response.data
        assert 'total_duration_seconds' in response.data
        assert 'genres' in response.data


@pytest.mark.django_db
class TestPlaylistFollowView:
    """Test playlist follow/unfollow endpoints."""

    def test_follow_playlist(self, api_client, authenticated_user, test_playlist):
        """Test following a playlist."""
        url = reverse('playlist-follow', kwargs={'pk': test_playlist.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_201_CREATED

        follow = UserPlaylistFollow.objects.filter(
            user_id=authenticated_user,
            playlist=test_playlist
        ).first()
        assert follow is not None

    def test_unfollow_playlist(self, api_client, authenticated_user, test_playlist):
        """Test unfollowing a playlist."""
        UserPlaylistFollow.objects.create(
            user_id=authenticated_user,
            playlist=test_playlist
        )

        url = reverse('playlist-follow', kwargs={'pk': test_playlist.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_200_OK

        follow_exists = UserPlaylistFollow.objects.filter(
            user_id=authenticated_user,
            playlist=test_playlist
        ).exists()
        assert follow_exists is False


@pytest.mark.django_db
class TestPlaylistLikeView:
    """Test playlist like/unlike endpoints."""

    def test_like_playlist(self, api_client, authenticated_user, test_playlist):
        """Test liking a playlist."""
        url = reverse('playlist-like', kwargs={'pk': test_playlist.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_201_CREATED

        like = UserPlaylistLike.objects.filter(
            user_id=authenticated_user,
            playlist=test_playlist
        ).first()
        assert like is not None

    def test_unlike_playlist(self, api_client, authenticated_user, test_playlist):
        """Test unliking a playlist."""
        UserPlaylistLike.objects.create(
            user_id=authenticated_user,
            playlist=test_playlist
        )

        url = reverse('playlist-like', kwargs={'pk': test_playlist.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_200_OK

        like_exists = UserPlaylistLike.objects.filter(
            user_id=authenticated_user,
            playlist=test_playlist
        ).exists()
        assert like_exists is False


@pytest.mark.django_db
class TestBatchOperations:
    """Test batch operation endpoints."""

    def test_batch_delete_playlists(self, api_client, authenticated_user):
        """Test batch deleting playlists."""
        playlist1 = Playlist.objects.create(owner_id=authenticated_user, name='Playlist 1')
        playlist2 = Playlist.objects.create(owner_id=authenticated_user, name='Playlist 2')

        url = reverse('playlist-batch-delete')
        data = {'playlist_ids': [playlist1.id, playlist2.id]}
        response = api_client.delete(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['deleted'] == 2

        # Verify playlists are deleted
        assert not Playlist.objects.filter(id=playlist1.id).exists()
        assert not Playlist.objects.filter(id=playlist2.id).exists()

    def test_batch_update_playlists(self, api_client, authenticated_user):
        """Test batch updating playlists."""
        playlist1 = Playlist.objects.create(owner_id=authenticated_user, name='Playlist 1')
        playlist2 = Playlist.objects.create(owner_id=authenticated_user, name='Playlist 2')

        url = reverse('playlist-batch-update')
        data = {
            'playlist_ids': [playlist1.id, playlist2.id],
            'updates': {'visibility': 'private'}
        }
        response = api_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['updated'] == 2

        # Verify playlists are updated
        playlist1.refresh_from_db()
        playlist2.refresh_from_db()
        assert playlist1.visibility == 'private'
        assert playlist2.visibility == 'private'
