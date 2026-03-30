"""
Unit tests for Playlist models.
"""
import pytest
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
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

        playlist2 = Playlist.objects.create(
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
