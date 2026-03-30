"""
Integration tests for Track API endpoints.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from trackapp.models import Track


@pytest.mark.django_db
class TestTrackListView:
    """Test track list and add endpoints."""

    def test_list_tracks(self, api_client, authenticated_user, test_playlist, test_song):
        """Test listing tracks in a playlist."""
        Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0
        )

        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_add_track_to_playlist(self, api_client, authenticated_user, test_playlist, test_song):
        """Test adding a track to a playlist."""
        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        data = {'song_id': test_song.id}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['song']['id'] == test_song.id

    def test_add_duplicate_track_fails(self, api_client, authenticated_user, test_playlist, test_song):
        """Test adding duplicate track fails with conflict."""
        Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0
        )

        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        data = {'song_id': test_song.id}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_add_track_requires_song_id(self, api_client, authenticated_user, test_playlist):
        """Test adding track requires song_id."""
        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})
        data = {}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTrackDetailView:
    """Test track detail and delete endpoints."""

    def test_delete_track(self, api_client, authenticated_user, test_playlist, test_song):
        """Test deleting a track from playlist."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0
        )

        url = reverse('track-detail', kwargs={'playlist_id': test_playlist.id, 'track_id': track.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify track is deleted
        assert not Track.objects.filter(id=track.id).exists()


@pytest.mark.django_db
class TestTrackReorderView:
    """Test track reordering endpoint."""

    def test_reorder_tracks(self, api_client, authenticated_user, test_playlist, test_song):
        """Test reordering tracks in a playlist."""
        # Create multiple tracks
        track1 = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0
        )
        track2 = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=1
        )

        url = reverse('track-reorder', kwargs={'playlist_id': test_playlist.id})
        data = {'track_ids': [track2.id, track1.id]}  # Reverse order
        response = api_client.put(url, data)

        assert response.status_code == status.HTTP_200_OK

        # Verify positions are updated
        track1.refresh_from_db()
        track2.refresh_from_db()
        assert track2.position == 0
        assert track1.position == 1

    def test_reorder_remove_tracks(self, api_client, authenticated_user, test_playlist, test_song):
        """Test reordering with removal (tracks not in list are deleted)."""
        track1 = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0
        )
        track2 = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=1
        )

        url = reverse('track-reorder', kwargs={'playlist_id': test_playlist.id})
        data = {'track_ids': [track1.id]}  # track2 not included, should be removed
        response = api_client.put(url, data)

        assert response.status_code == status.HTTP_200_OK

        # Verify track2 is deleted
        assert not Track.objects.filter(id=track2.id).exists()


@pytest.mark.django_db
class TestBatchRemoveView:
    """Test batch track removal endpoint."""

    def test_batch_remove_tracks(self, api_client, authenticated_user, test_playlist, test_song):
        """Test removing multiple tracks at once."""
        track1 = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0
        )
        track2 = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=1
        )

        url = reverse('track-remove', kwargs={'playlist_id': test_playlist.id})
        data = {'track_ids': [track1.id, track2.id]}
        response = api_client.delete(url, data)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify both tracks are deleted
        assert not Track.objects.filter(id=track1.id).exists()
        assert not Track.objects.filter(id=track2.id).exists()


@pytest.mark.django_db
class TestTrackHideView:
    """Test track hide/unhide endpoints."""

    def test_hide_track(self, api_client, authenticated_user, test_playlist, test_song):
        """Test hiding a track."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0
        )

        url = reverse('track-hide', kwargs={'playlist_id': test_playlist.id, 'track_id': track.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK

        # Verify track is hidden
        from trackapp.models import UserTrackHide
        assert UserTrackHide.objects.filter(
            user_id=authenticated_user,
            track=track
        ).exists()

    def test_unhide_track(self, api_client, authenticated_user, test_playlist, test_song):
        """Test unhiding a track."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0
        )

        # First hide the track
        from trackapp.models import UserTrackHide
        UserTrackHide.objects.create(user_id=authenticated_user, track=track)

        # Then unhide
        url = reverse('track-hide', kwargs={'playlist_id': test_playlist.id, 'track_id': track.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify track is unhidden
        assert not UserTrackHide.objects.filter(
            user_id=authenticated_user,
            track=track
        ).exists()
