"""
Integration tests for Track API endpoints.

All views return the standard SuccessResponse / ErrorResponse envelope:
  { "success": bool, "data": <payload>, "message": str }
Assertions therefore read response.data['data'] for the actual payload.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from trackapp.models import Track


def _make_song(suffix='2'):
    """Helper: create a second song to avoid the unique (playlist, song) constraint."""
    from searchapp.models import Artist, Album, Song
    artist = Artist.objects.create(name=f'Artist {suffix}')
    album = Album.objects.create(name=f'Album {suffix}', artist=artist)
    return Song.objects.create(
        title=f'Song {suffix}',
        artist=artist,
        album=album,
        duration_seconds=180,
    )


@pytest.mark.django_db
class TestTrackListView:
    """Test track list and add endpoints."""

    def test_list_tracks(self, api_client, authenticated_user, test_playlist, test_song):
        """Test listing tracks in a playlist."""
        Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0,
        )

        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) >= 1

    def test_list_tracks_unauthenticated(self, api_client, test_playlist):
        """Test listing tracks requires authentication."""
        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_add_track_to_playlist(self, api_client, authenticated_user, test_playlist, test_song):
        """Test adding a track to a playlist (owner only)."""
        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        data = {'song_id': test_song.id}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['data']['song']['id'] == test_song.id

    def test_add_track_non_owner_forbidden(self, api_client, authenticated_user, test_song):
        """Test adding a track to another user's playlist returns 403."""
        from playlistapp.models import Playlist
        other_playlist = Playlist.objects.create(
            owner_id=authenticated_user + 999,
            name='Other Playlist',
        )

        url = reverse('track-list', kwargs={'playlist_id': other_playlist.id})
        data = {'song_id': test_song.id}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_add_duplicate_track_fails(self, api_client, authenticated_user, test_playlist, test_song):
        """Test adding duplicate track fails with 409 Conflict."""
        Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0,
        )

        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        data = {'song_id': test_song.id}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_add_track_requires_song_id(self, api_client, authenticated_user, test_playlist):
        """Test adding track without song_id returns 400."""
        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        response = api_client.post(url, {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_add_track_invalid_song_id(self, api_client, authenticated_user, test_playlist):
        """Test adding track with non-existent song_id returns 404."""
        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        data = {'song_id': 999999}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_add_track_playlist_not_found(self, api_client, authenticated_user, test_song):
        """Test adding track to non-existent playlist returns 404."""
        url = reverse('track-list', kwargs={'playlist_id': 999999})
        data = {'song_id': test_song.id}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_add_track_respects_max_songs(self, api_client, authenticated_user, test_song):
        """Test playlist max_songs limit is enforced."""
        from playlistapp.models import Playlist
        limited_playlist = Playlist.objects.create(
            owner_id=authenticated_user,
            name='Limited Playlist',
            max_songs=1,
        )
        # Fill to capacity
        Track.objects.create(
            playlist=limited_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0,
        )

        song2 = _make_song('limit')
        url = reverse('track-list', kwargs={'playlist_id': limited_playlist.id})
        response = api_client.post(url, {'song_id': song2.id})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_tracks_sort_by_title(self, api_client, authenticated_user, test_playlist, test_song):
        """Test sort query param is accepted."""
        Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0,
        )

        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        response = api_client.get(url, {'sort': 'title', 'order': 'asc'})

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestTrackDetailView:
    """Test track delete endpoint."""

    def test_delete_own_track(self, api_client, authenticated_user, test_playlist, test_song):
        """Test owner can delete a track from their playlist."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0,
        )

        url = reverse('track-detail', kwargs={
            'playlist_id': test_playlist.id,
            'track_id': track.id,
        })
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Track.objects.filter(id=track.id).exists()

    def test_delete_track_not_found(self, api_client, authenticated_user, test_playlist):
        """Test deleting non-existent track returns 404."""
        url = reverse('track-detail', kwargs={
            'playlist_id': test_playlist.id,
            'track_id': 999999,
        })
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_track_other_playlist_forbidden(self, api_client, authenticated_user, test_song):
        """Test deleting track from another user's playlist returns 403."""
        from playlistapp.models import Playlist
        other_playlist = Playlist.objects.create(
            owner_id=authenticated_user + 999,
            name='Other Playlist',
        )
        track = Track.objects.create(
            playlist=other_playlist,
            song=test_song,
            added_by_id=authenticated_user + 999,
            position=0,
        )

        url = reverse('track-detail', kwargs={
            'playlist_id': other_playlist.id,
            'track_id': track.id,
        })
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestTrackReorderRemoveView:
    """Test track reorder-remove endpoint."""

    def _two_tracks(self, playlist, authenticated_user, test_song):
        """Create two tracks using two different songs (unique constraint)."""
        song2 = _make_song('reorder')
        t1 = Track.objects.create(
            playlist=playlist, song=test_song,
            added_by_id=authenticated_user, position=0,
        )
        t2 = Track.objects.create(
            playlist=playlist, song=song2,
            added_by_id=authenticated_user, position=1,
        )
        return t1, t2

    def test_reorder_tracks(self, api_client, authenticated_user, test_playlist, test_song):
        """Test reordering tracks updates positions."""
        track1, track2 = self._two_tracks(test_playlist, authenticated_user, test_song)

        url = reverse('track-reorder', kwargs={'playlist_id': test_playlist.id})
        response = api_client.put(url, {'track_ids': [track2.id, track1.id]}, format='json')

        assert response.status_code == status.HTTP_200_OK
        track1.refresh_from_db()
        track2.refresh_from_db()
        assert track2.position == 0
        assert track1.position == 1

    def test_reorder_remove_tracks(self, api_client, authenticated_user, test_playlist, test_song):
        """Test omitting a track from track_ids removes it."""
        track1, track2 = self._two_tracks(test_playlist, authenticated_user, test_song)

        url = reverse('track-reorder', kwargs={'playlist_id': test_playlist.id})
        response = api_client.put(url, {'track_ids': [track1.id]}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert not Track.objects.filter(id=track2.id).exists()
        track1.refresh_from_db()
        assert track1.position == 0

    def test_reorder_missing_track_ids_key(self, api_client, authenticated_user, test_playlist):
        """Test PUT without track_ids key returns 400."""
        url = reverse('track-reorder', kwargs={'playlist_id': test_playlist.id})
        response = api_client.put(url, {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reorder_track_ids_not_list(self, api_client, authenticated_user, test_playlist):
        """Test track_ids that is not a list returns 400."""
        url = reverse('track-reorder', kwargs={'playlist_id': test_playlist.id})
        response = api_client.put(url, {'track_ids': 'not-a-list'}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reorder_duplicate_ids(self, api_client, authenticated_user, test_playlist, test_song):
        """Test duplicate IDs in track_ids returns 400."""
        track = Track.objects.create(
            playlist=test_playlist, song=test_song,
            added_by_id=authenticated_user, position=0,
        )

        url = reverse('track-reorder', kwargs={'playlist_id': test_playlist.id})
        response = api_client.put(url, {'track_ids': [track.id, track.id]}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reorder_foreign_track_id_rejected(self, api_client, authenticated_user, test_playlist, test_song):
        """Test a track ID from another playlist is rejected."""
        from playlistapp.models import Playlist
        other_playlist = Playlist.objects.create(
            owner_id=authenticated_user,
            name='Other Playlist',
        )
        song2 = _make_song('foreign')
        foreign_track = Track.objects.create(
            playlist=other_playlist, song=song2,
            added_by_id=authenticated_user, position=0,
        )

        url = reverse('track-reorder', kwargs={'playlist_id': test_playlist.id})
        response = api_client.put(
            url, {'track_ids': [foreign_track.id]}, format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reorder_playlist_not_found(self, api_client, authenticated_user):
        """Test reordering on non-existent playlist returns 404."""
        url = reverse('track-reorder', kwargs={'playlist_id': 999999})
        response = api_client.put(url, {'track_ids': []}, format='json')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_reorder_non_owner_forbidden(self, api_client, authenticated_user, test_song):
        """Test reordering another user's playlist returns 403."""
        from playlistapp.models import Playlist
        other_playlist = Playlist.objects.create(
            owner_id=authenticated_user + 999,
            name='Other Playlist',
        )

        url = reverse('track-reorder', kwargs={'playlist_id': other_playlist.id})
        response = api_client.put(url, {'track_ids': []}, format='json')

        # Collaborator check may raise 503 if service client is unavailable; accept 403 or 503.
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    def test_reorder_requires_auth(self, api_client, test_playlist):
        """Test reorder endpoint requires authentication."""
        url = reverse('track-reorder', kwargs={'playlist_id': test_playlist.id})
        response = api_client.put(url, {'track_ids': []}, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTrackRemoveView:
    """Test batch track removal endpoint."""

    def test_batch_remove_tracks(self, api_client, authenticated_user, test_playlist, test_song):
        """Test removing multiple tracks at once."""
        song2 = _make_song('remove')
        track1 = Track.objects.create(
            playlist=test_playlist, song=test_song,
            added_by_id=authenticated_user, position=0,
        )
        track2 = Track.objects.create(
            playlist=test_playlist, song=song2,
            added_by_id=authenticated_user, position=1,
        )

        url = reverse('track-remove', kwargs={'playlist_id': test_playlist.id})
        response = api_client.delete(url, {'track_ids': [track1.id, track2.id]}, format='json')

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Track.objects.filter(id=track1.id).exists()
        assert not Track.objects.filter(id=track2.id).exists()

    def test_batch_remove_non_owner_forbidden(self, api_client, authenticated_user, test_song):
        """Test batch remove on another user's playlist returns 403."""
        from playlistapp.models import Playlist
        other_playlist = Playlist.objects.create(
            owner_id=authenticated_user + 999,
            name='Other Playlist',
        )

        url = reverse('track-remove', kwargs={'playlist_id': other_playlist.id})
        response = api_client.delete(url, {'track_ids': []}, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestTrackHideView:
    """Test track hide/unhide endpoints."""

    def test_hide_track(self, api_client, authenticated_user, test_playlist, test_song):
        """Test hiding a track from the current user's view."""
        track = Track.objects.create(
            playlist=test_playlist, song=test_song,
            added_by_id=authenticated_user, position=0,
        )

        url = reverse('track-hide', kwargs={
            'playlist_id': test_playlist.id,
            'track_id': track.id,
        })
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK

        from trackapp.models import UserTrackHide
        assert UserTrackHide.objects.filter(
            user_id=authenticated_user, track=track
        ).exists()

    def test_unhide_track(self, api_client, authenticated_user, test_playlist, test_song):
        """Test unhiding a track restores its visibility."""
        track = Track.objects.create(
            playlist=test_playlist, song=test_song,
            added_by_id=authenticated_user, position=0,
        )

        from trackapp.models import UserTrackHide
        UserTrackHide.objects.create(user_id=authenticated_user, track=track)

        url = reverse('track-hide', kwargs={
            'playlist_id': test_playlist.id,
            'track_id': track.id,
        })
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not UserTrackHide.objects.filter(
            user_id=authenticated_user, track=track
        ).exists()

    def test_hidden_track_excluded_from_list(self, api_client, authenticated_user, test_playlist, test_song):
        """Test hidden tracks are excluded from GET track list."""
        track = Track.objects.create(
            playlist=test_playlist, song=test_song,
            added_by_id=authenticated_user, position=0,
        )

        from trackapp.models import UserTrackHide
        UserTrackHide.objects.create(user_id=authenticated_user, track=track)

        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        track_ids = [t['id'] for t in response.data['data']]
        assert track.id not in track_ids

    def test_hide_nonexistent_track(self, api_client, authenticated_user, test_playlist):
        """Test hiding a non-existent track returns 404."""
        url = reverse('track-hide', kwargs={
            'playlist_id': test_playlist.id,
            'track_id': 999999,
        })
        response = api_client.post(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
