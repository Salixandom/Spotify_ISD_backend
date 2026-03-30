"""
Integration tests for History API endpoints (Undo/Redo).
"""
import pytest
from django.urls import reverse
from rest_framework import status
from historyapp.models import Play, UserAction, UndoRedoConfiguration
from playlistapp.models import Playlist


@pytest.mark.django_db
class TestPlayRecording:
    """Test play recording endpoints."""

    def test_record_play(self, api_client, authenticated_user, test_song):
        """Test recording a song play."""
        url = reverse('record-play')
        data = {'song_id': test_song.id}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] == 'recorded'

        # Verify play was recorded
        play = Play.objects.filter(user_id=authenticated_user, song=test_song).first()
        assert play is not None

    def test_record_play_requires_song_id(self, api_client, authenticated_user):
        """Test recording play requires song_id."""
        url = reverse('record-play')
        data = {}
        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_recent_plays(self, api_client, authenticated_user, test_song):
        """Test retrieving recently played songs."""
        # Record some plays
        Play.objects.create(user_id=authenticated_user, song=test_song)

        url = reverse('recent-plays')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1


@pytest.mark.django_db
class TestUndoRedo:
    """Test undo/redo endpoints."""

    def test_undo_action(self, api_client, authenticated_user, test_playlist):
        """Test undoing an action."""
        # Create an action to undo
        action = UserAction.objects.create(
            user_id=authenticated_user,
            action_type='playlist_create',
            entity_type='playlist',
            entity_id=test_playlist.id,
            before_state={},
            after_state={'name': test_playlist.name},
            delta={'created': True}
        )

        url = reverse('undo-action', kwargs={'action_id': action.action_id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

        # Verify action is marked as undone
        action.refresh_from_db()
        assert action.is_undone is True

    def test_undo_nonexistent_action(self, api_client, authenticated_user):
        """Test undoing non-existent action."""
        import uuid
        url = reverse('undo-action', kwargs={'action_id': uuid.uuid4()})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_redo_action(self, api_client, authenticated_user, test_playlist):
        """Test redoing an undone action."""
        # Create and undo an action
        action = UserAction.objects.create(
            user_id=authenticated_user,
            action_type='playlist_create',
            entity_type='playlist',
            entity_id=test_playlist.id,
            is_undone=True
        )

        url = reverse('redo-action', kwargs={'action_id': action.action_id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

        # Verify action is marked as redone
        action.refresh_from_db()
        assert action.is_redone is True


@pytest.mark.django_db
class TestUserActionsView:
    """Test user actions listing endpoint."""

    def test_list_user_actions(self, api_client, authenticated_user):
        """Test listing user's actions."""
        # Create some actions
        UserAction.objects.create(
            user_id=authenticated_user,
            action_type='playlist_create',
            entity_type='playlist',
            entity_id=1
        )
        UserAction.objects.create(
            user_id=authenticated_user,
            action_type='song_add',
            entity_type='track',
            entity_id=1
        )

        url = reverse('user-actions')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'actions' in response.data
        assert 'total' in response.data

    def test_limit_actions(self, api_client, authenticated_user):
        """Test limiting number of actions returned."""
        # Create multiple actions
        for i in range(10):
            UserAction.objects.create(
                user_id=authenticated_user,
                action_type='test_action',
                entity_type='test',
                entity_id=i
            )

        url = reverse('user-actions')
        response = api_client.get(url, {'limit': 5})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['actions']) <= 5


@pytest.mark.django_db
class TestUndoableActionsView:
    """Test undoable actions endpoint."""

    def test_list_undoable_actions(self, api_client, authenticated_user):
        """Test listing actions that can be undone."""
        # Create mix of undoable and undone actions
        UserAction.objects.create(
            user_id=authenticated_user,
            action_type='playlist_create',
            entity_type='playlist',
            entity_id=1,
            is_undoable=True,
            is_undone=False
        )
        UserAction.objects.create(
            user_id=authenticated_user,
            action_type='playlist_delete',
            entity_type='playlist',
            entity_id=2,
            is_undoable=True,
            is_undone=True  # Already undone
        )

        url = reverse('undoable-actions')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'undoable_actions' in response.data

        # Should only return undoable, not undone actions
        assert all(a['is_undoable'] and not a['is_undone'] for a in response.data['undoable_actions'])


@pytest.mark.django_db
class TestUndoRedoConfig:
    """Test undo/redo configuration endpoint."""

    def test_get_config(self, api_client, authenticated_user):
        """Test getting undo/redo configuration."""
        url = reverse('undo-config')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'undo_window_hours' in response.data
        assert 'max_actions' in response.data

    def test_update_config(self, api_client, authenticated_user):
        """Test updating undo/redo configuration."""
        url = reverse('undo-config')
        data = {
            'undo_window_hours': 48,
            'max_actions': 2000,
            'auto_cleanup': False
        }
        response = api_client.put(url, data)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['undo_window_hours'] == 48
        assert response.data['max_actions'] == 2000
        assert response.data['auto_cleanup'] is False

        # Verify config is persisted
        config = UndoRedoConfiguration.objects.get(user_id=authenticated_user)
        assert config.undo_window_hours == 48
        assert config.max_actions == 2000
