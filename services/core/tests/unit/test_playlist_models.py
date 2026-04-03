"""
Unit tests for Playlist models.
"""
import pytest
from django.db import IntegrityError, transaction
from playlistapp.models import Playlist, UserPlaylistFollow, UserPlaylistLike, PlaylistSnapshot


@pytest.mark.django_db
class TestPlaylistModel:
    """Test Playlist model functionality."""

    def test_create_playlist(self):
        """Test creating a new playlist."""
        playlist = Playlist.objects.create(
            owner_id=1,
            name='My Playlist',
            description='My favorite songs',
            visibility='public',
            playlist_type='solo',
            max_songs=100
        )

        assert playlist.id is not None
        assert playlist.name == 'My Playlist'
        assert playlist.owner_id == 1
        assert playlist.visibility == 'public'
        assert playlist.playlist_type == 'solo'
        assert playlist.max_songs == 100

    def test_playlist_defaults(self):
        """Test default values for playlist fields."""
        playlist = Playlist.objects.create(
            owner_id=1,
            name='Test Playlist'
        )

        assert playlist.visibility == 'public'
        assert playlist.playlist_type == 'solo'
        assert playlist.max_songs == 0
        assert playlist.description == ''
        assert playlist.cover_url == ''

    def test_playlist_str_method(self):
        """Test string representation of playlist."""
        playlist = Playlist.objects.create(
            owner_id=1,
            name='Test Playlist'
        )

        assert str(playlist) == 'Test Playlist'

    def test_playlist_ordering(self):
        """Test playlists are ordered by updated_at by default."""
        playlist1 = Playlist.objects.create(
            owner_id=1,
            name='Playlist 1'
        )

        # Update playlist1 to make it newer
        playlist1.save()

        Playlist.objects.create(
            owner_id=1,
            name='Playlist 2'
        )

        playlists = list(Playlist.objects.all())
        assert playlists[0].name == 'Playlist 1'  # Most recently updated


@pytest.mark.django_db
class TestUserPlaylistFollow:
    """Test UserPlaylistFollow model."""

    def test_follow_playlist(self):
        """Test following a playlist."""
        playlist = Playlist.objects.create(owner_id=1, name='Test Playlist')

        follow = UserPlaylistFollow.objects.create(
            user_id=2,
            playlist=playlist
        )

        assert follow.id is not None
        assert follow.user_id == 2
        assert follow.playlist == playlist

    def test_unique_follow_constraint(self):
        """Test that a user can only follow a playlist once."""
        playlist = Playlist.objects.create(owner_id=1, name='Test Playlist')

        UserPlaylistFollow.objects.create(
            user_id=2,
            playlist=playlist
        )

        # Attempting to follow again should raise IntegrityError
        with pytest.raises(Exception):  # IntegrityError
            UserPlaylistFollow.objects.create(
                user_id=2,
                playlist=playlist
            )


@pytest.mark.django_db
class TestUserPlaylistLike:
    """Test UserPlaylistLike model."""

    def test_like_playlist(self):
        """Test liking a playlist."""
        playlist = Playlist.objects.create(owner_id=1, name='Test Playlist')

        like = UserPlaylistLike.objects.create(
            user_id=2,
            playlist=playlist
        )

        assert like.id is not None
        assert like.user_id == 2
        assert like.playlist == playlist

    def test_unique_like_constraint(self):
        """Test that a user can only like a playlist once."""
        playlist = Playlist.objects.create(owner_id=1, name='Test Playlist')

        UserPlaylistLike.objects.create(
            user_id=2,
            playlist=playlist
        )

        # Attempting to like again should raise IntegrityError
        with pytest.raises(Exception):  # IntegrityError
            UserPlaylistLike.objects.create(
                user_id=2,
                playlist=playlist
            )


@pytest.mark.django_db
class TestPlaylistSnapshot:
    """Test PlaylistSnapshot model."""

    def test_create_snapshot(self):
        """Test creating a playlist snapshot."""
        playlist = Playlist.objects.create(owner_id=1, name='Test Playlist')

        snapshot = PlaylistSnapshot.objects.create(
            playlist=playlist,
            snapshot_data={'name': 'Snapshot 1', 'tracks': []},
            created_by=1,
            change_reason='Manual snapshot',
            track_count=0
        )

        assert snapshot.id is not None
        assert snapshot.playlist == playlist
        assert snapshot.change_reason == 'Manual snapshot'
        assert snapshot.track_count == 0

    def test_snapshot_ordering(self):
        """Test snapshots are ordered by created_at descending (newest first)."""
        playlist = Playlist.objects.create(owner_id=1, name='Test Playlist')

        snapshot1 = PlaylistSnapshot.objects.create(
            playlist=playlist,
            snapshot_data={},
            created_by=1
        )

        snapshot2 = PlaylistSnapshot.objects.create(
            playlist=playlist,
            snapshot_data={},
            created_by=1
        )

        snapshots = list(playlist.snapshots.all())
        assert snapshots[0].id == snapshot2.id  # Most recent first
        assert snapshots[1].id == snapshot1.id


@pytest.mark.django_db
class TestPostgreSQLConstraints:
    """PostgreSQL-specific constraint tests.

    These tests exercise behaviours that SQLite either ignores or does not
    enforce at the database level:
      - PositiveIntegerField maps to an integer column with a CHECK (value >= 0)
        constraint in PostgreSQL.  QuerySet.update() bypasses ORM validators so
        the constraint must be caught by the database itself.
      - SELECT FOR UPDATE is a no-op in SQLite but works correctly in PostgreSQL;
        we verify it does not raise here.
      - unique_together violations should raise django.db.IntegrityError, not a
        generic Exception.
    """

    def test_max_songs_rejects_negative_value(self):
        """PositiveIntegerField CHECK constraint fires when bypassing ORM validation."""
        playlist = Playlist.objects.create(owner_id=1, name='Constraint Test')
        with pytest.raises(IntegrityError):
            # .update() skips Python-level field validation — only the DB CHECK
            # constraint stands between us and a negative value.
            Playlist.objects.filter(id=playlist.id).update(max_songs=-1)

    @pytest.mark.django_db(transaction=True)
    def test_select_for_update_acquires_lock(self):
        """select_for_update() must work without error — PostgreSQL supports row locking."""
        playlist = Playlist.objects.create(owner_id=1, name='Lock Test')
        with transaction.atomic():
            locked = Playlist.objects.select_for_update().get(id=playlist.id)
            assert locked.id == playlist.id

    def test_unique_follow_raises_integrity_error(self):
        """unique_together on UserPlaylistFollow raises IntegrityError, not a generic error."""
        playlist = Playlist.objects.create(owner_id=1, name='Follow Test')
        UserPlaylistFollow.objects.create(user_id=5, playlist=playlist)
        with pytest.raises(IntegrityError):
            UserPlaylistFollow.objects.create(user_id=5, playlist=playlist)

    def test_unique_like_raises_integrity_error(self):
        """unique_together on UserPlaylistLike raises IntegrityError, not a generic error."""
        playlist = Playlist.objects.create(owner_id=1, name='Like Test')
        UserPlaylistLike.objects.create(user_id=5, playlist=playlist)
        with pytest.raises(IntegrityError):
            UserPlaylistLike.objects.create(user_id=5, playlist=playlist)
