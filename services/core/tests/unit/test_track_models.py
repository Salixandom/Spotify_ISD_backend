"""
Unit tests for Track models.
"""
import pytest
from trackapp.models import Track, UserTrackHide
from playlistapp.models import Playlist
from searchapp.models import Song, Artist, Album


@pytest.mark.django_db
class TestTrackModel:
    """Test Track model functionality."""

    def test_create_track(self, test_playlist, test_song):
        """Test creating a new track."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=1,
            position=0
        )

        assert track.id is not None
        assert track.playlist == test_playlist
        assert track.song == test_song
        assert track.position == 0

    def test_track_default_position(self, test_playlist, test_song):
        """Test default position is 0."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=1
        )

        assert track.position == 0

    def test_unique_song_per_playlist(self, test_playlist, test_song):
        """Test that a song can only appear once in a playlist."""
        Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=1,
            position=0
        )

        # Attempting to add the same song again should raise IntegrityError
        with pytest.raises(Exception):  # IntegrityError
            Track.objects.create(
                playlist=test_playlist,
                song=test_song,
                added_by_id=1,
                position=1
            )

    def test_track_str_method(self, test_playlist, test_song):
        """Test string representation of track."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=1,
            position=0
        )

        expected = f"{test_song.title} in {test_playlist.name} @ pos 0"
        assert str(track) == expected

    def test_track_ordering(self, test_playlist, test_song):
        """Test tracks are ordered by position by default."""
        track1 = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=1,
            position=1
        )

        # Use a different song to avoid unique constraint
        from searchapp.models import Artist, Album, Song
        artist2 = Artist.objects.create(name='Artist 2')
        album2 = Album.objects.create(name='Album 2', artist=artist2)
        song2 = Song.objects.create(
            title='Song 2',
            artist=artist2,
            album=album2
        )

        track2 = Track.objects.create(
            playlist=test_playlist,
            song=song2,
            added_by_id=1,
            position=0
        )

        tracks = list(Track.objects.filter(playlist=test_playlist))
        assert tracks[0].position == 0
        assert tracks[1].position == 1


@pytest.mark.django_db
class TestUserTrackHide:
    """Test UserTrackHide model."""

    def test_hide_track(self, test_playlist, test_song):
        """Test hiding a track for a user."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=1,
            position=0
        )

        hide = UserTrackHide.objects.create(
            user_id=2,
            track=track
        )

        assert hide.id is not None
        assert hide.user_id == 2
        assert hide.track == track

    def test_unique_hide_constraint(self, test_playlist, test_song):
        """Test that a user can only hide a track once."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=1,
            position=0
        )

        UserTrackHide.objects.create(
            user_id=2,
            track=track
        )

        # Attempting to hide again should raise IntegrityError
        with pytest.raises(Exception):  # IntegrityError
            UserTrackHide.objects.create(
                user_id=2,
                track=track
            )
