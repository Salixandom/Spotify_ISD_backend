"""
Unit tests for History app models.
"""
import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from historyapp.models import Play, UserAction, UndoRedoConfiguration
from playlistapp.models import Playlist
from searchapp.models import Song, Artist, Album


@pytest.mark.django_db
class TestPlayModel:
    """Test Play model functionality."""

    def test_record_play(self, test_song):
        """Test recording a song play."""
        play = Play.objects.create(
            user_id=1,
            song=test_song
        )

        assert play.id is not None
        assert play.user_id == 1
        assert play.song == test_song
        assert play.played_at is not None

    def test_play_ordering(self, test_song):
        """Test plays are ordered by played_at descending (most recent first)."""
        from django.utils import timezone

        # Create older play
        play1 = Play.objects.create(user_id=1, song=test_song)
        play1.played_at = timezone.now() - timezone.timedelta(seconds=10)
        play1.save()

        # Create newer play
        play2 = Play.objects.create(user_id=1, song=test_song)

        # Explicitly query with ordering
        plays = list(Play.objects.all().order_by('-played_at'))

        # Most recent should be first
        assert len(plays) == 2
        assert plays[0].id == play2.id  # More recent
        assert plays[1].id == play1.id  # Older


@pytest.mark.django_db
class TestUserActionModel:
    """Test UserAction model functionality."""

    def test_create_action(self, test_playlist):
        """Test creating a user action."""
        action = UserAction.objects.create(
            user_id=1,
            action_type='playlist_create',
            entity_type='playlist',
            entity_id=test_playlist.id,
            before_state={},
            after_state={'name': test_playlist.name},
            delta={'created': True}
        )

        assert action.id is not None
        assert action.user_id == 1
        assert action.action_type == 'playlist_create'
        assert action.entity_type == 'playlist'
        assert action.is_undoable is True
        assert action.is_undone is False

    def test_action_defaults(self):
        """Test default values for action fields."""
        action = UserAction.objects.create(
            user_id=1,
            action_type='playlist_create',
            entity_type='playlist',
            entity_id=1
        )

        assert action.before_state == {}
        assert action.after_state == {}
        assert action.delta == {}
        assert action.is_undoable is True
        assert action.is_undone is False
        assert action.undo_deadline is None

    def test_can_undo_when_undoable(self):
        """Test can_undo returns True for undoable actions."""
        action = UserAction.objects.create(
            user_id=1,
            action_type='playlist_create',
            entity_type='playlist',
            entity_id=1,
            undo_deadline=timezone.now() + timedelta(hours=24)
        )

        assert action.can_undo() is True

    def test_cannot_undo_when_undone(self):
        """Test can_undo returns False for already undone actions."""
        action = UserAction.objects.create(
            user_id=1,
            action_type='playlist_create',
            entity_type='playlist',
            entity_id=1,
            is_undone=True
        )

        assert action.can_undo() is False

    def test_cannot_undo_when_expired(self):
        """Test can_undo returns False when undo deadline has passed."""
        past_deadline = timezone.now() - timedelta(hours=1)

        action = UserAction.objects.create(
            user_id=1,
            action_type='playlist_create',
            entity_type='playlist',
            entity_id=1,
            undo_deadline=past_deadline
        )

        assert action.can_undo() is False

    def test_cannot_undo_when_flagged_non_undoable(self):
        """Test can_undo returns False when is_undoable is False."""
        action = UserAction.objects.create(
            user_id=1,
            action_type='playlist_create',
            entity_type='playlist',
            entity_id=1,
            is_undoable=False
        )

        assert action.can_undo() is False


@pytest.mark.django_db
class TestUndoRedoConfiguration:
    """Test UndoRedoConfiguration model functionality."""

    def test_create_configuration(self):
        """Test creating undo/redo configuration."""
        config = UndoRedoConfiguration.objects.create(
            user_id=1,
            undo_window_hours=48,
            max_actions=2000,
            auto_cleanup=False,
            disabled_action_types=['playlist_delete']
        )

        assert config.id is not None
        assert config.user_id == 1
        assert config.undo_window_hours == 48
        assert config.max_actions == 2000
        assert config.auto_cleanup is False
        assert 'playlist_delete' in config.disabled_action_types

    def test_configuration_defaults(self):
        """Test default values for configuration."""
        config = UndoRedoConfiguration.objects.create(user_id=1)

        assert config.undo_window_hours == 24
        assert config.max_actions == 1000
        assert config.auto_cleanup is True
        assert config.disabled_action_types == []

    def test_unique_user_configuration(self):
        """Test that each user can have only one configuration."""
        UndoRedoConfiguration.objects.create(user_id=1)

        # Attempting to create again should raise IntegrityError
        with pytest.raises(Exception):  # IntegrityError
            UndoRedoConfiguration.objects.create(user_id=1)
