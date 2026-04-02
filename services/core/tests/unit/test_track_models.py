"""
Unit tests for Track models.
"""
import pytest
from django.db import IntegrityError
from trackapp.models import Track, UserTrackHide


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
        Track.objects.create(
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

        Track.objects.create(
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


@pytest.mark.django_db
class TestPostgreSQLConstraints:
    """PostgreSQL-specific constraint tests for Track models.

    Verifies that unique_together constraints raise django.db.IntegrityError
    (the specific exception, not just a generic Exception), and that
    SELECT FOR UPDATE locking works at the database level.
    """

    def test_unique_song_per_playlist_raises_integrity_error(self, test_playlist, test_song):
        """unique_together on (playlist, song) raises IntegrityError specifically."""
        Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=1,
            position=0,
        )
        with pytest.raises(IntegrityError):
            Track.objects.create(
                playlist=test_playlist,
                song=test_song,
                added_by_id=1,
                position=1,
            )

    def test_unique_hide_raises_integrity_error(self, test_playlist, test_song):
        """unique_together on (user_id, track) for UserTrackHide raises IntegrityError."""
        track = Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=1,
            position=0,
        )
        UserTrackHide.objects.create(user_id=3, track=track)
        with pytest.raises(IntegrityError):
            UserTrackHide.objects.create(user_id=3, track=track)

    @pytest.mark.django_db(transaction=True)
    def test_select_for_update_on_playlist_works(self, test_playlist):
        """select_for_update() on Playlist must not raise — PostgreSQL supports it."""
        from django.db import transaction
        from playlistapp.models import Playlist
        with transaction.atomic():
            locked = Playlist.objects.select_for_update().get(id=test_playlist.id)
            assert locked.id == test_playlist.id
