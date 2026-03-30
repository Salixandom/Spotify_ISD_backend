"""
Handlers for undoing and redoing specific action types.
Each handler knows how to reverse its specific action.
"""
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class UndoHandler:
    """Base class for undo handlers"""

    @staticmethod
    def undo(action):
        """Undo the action"""
        raise NotImplementedError


class RedoHandler:
    """Base class for redo handlers"""

    @staticmethod
    def redo(action):
        """Redo the action"""
        raise NotImplementedError


class PlaylistCreateUndoHandler(UndoHandler):
    """Undo playlist creation = delete playlist"""

    @staticmethod
    def undo(action):
        from playlistapp.models import Playlist
        from trackapp.models import Track

        playlist_id = action.entity_id

        # Delete all tracks first
        Track.objects.filter(playlist_id=playlist_id).delete()

        # Delete playlist
        Playlist.objects.filter(id=playlist_id).delete()

        return {
            'new_state': {},
            'message': f'Deleted playlist {playlist_id}'
        }


class PlaylistDeleteUndoHandler(UndoHandler):
    """Undo playlist deletion = restore playlist + all tracks"""

    @staticmethod
    @transaction.atomic
    def undo(action):
        from playlistapp.models import Playlist
        from trackapp.models import Track

        before_state = action.before_state

        if not before_state or 'id' not in before_state:
            raise ValueError("Cannot undo: missing before_state")

        # Restore playlist
        from datetime import datetime
        playlist = Playlist.objects.create(
            id=before_state['id'],
            name=before_state['name'],
            description=before_state.get('description', ''),
            owner_id=before_state['owner_id'],
            visibility=before_state.get('visibility', 'private'),
            playlist_type=before_state.get('playlist_type', 'solo'),
            max_songs=before_state.get('max_songs', 0),
            cover_url=before_state.get('cover_url', ''),
        )

        # Restore created_at/updated_at if available
        if before_state.get('created_at'):
            try:
                playlist.created_at = datetime.fromisoformat(before_state['created_at'])
                playlist.save()
            except (ValueError, TypeError):
                pass

        # Restore tracks
        for track_data in before_state.get('tracks', []):
            try:
                added_at = None
                if track_data.get('added_at'):
                    try:
                        added_at = datetime.fromisoformat(track_data['added_at'])
                    except (ValueError, TypeError):
                        pass

                Track.objects.create(
                    id=track_data['id'],
                    playlist_id=playlist.id,
                    song_id=track_data['song_id'],
                    position=track_data['position'],
                    added_at=added_at,
                )
            except Exception as e:
                logger.warning(f"Failed to restore track {track_data.get('id')}: {e}")

        return {
            'new_state': before_state,
            'message': f'Restored playlist "{playlist.name}"'
        }


class TrackAddUndoHandler(UndoHandler):
    """Undo track addition = remove track"""

    @staticmethod
    def undo(action):
        from trackapp.models import Track

        track_id = action.entity_id

        try:
            track = Track.objects.get(id=track_id)
            playlist_id = track.playlist_id
            song_id = track.song_id

            track.delete()

            return {
                'new_state': action.before_state,
                'message': f'Removed track {track_id} from playlist {playlist_id}'
            }
        except Track.DoesNotExist:
            raise ValueError(f"Track {track_id} no longer exists")


# Redo handlers (simplified - often reuse undo logic)
class PlaylistCreateRedoHandler(RedoHandler):
    """Redo playlist creation = create again"""

    @staticmethod
    def redo(action):
        # This would typically be handled by re-executing the original request
        # For now, we'll raise NotImplementedError
        raise NotImplementedError("Redo not implemented for playlist_create")


# Handler factories
class UndoHandlerFactory:
    """Factory for getting appropriate undo handler"""

    HANDLERS = {
        'playlist_create': PlaylistCreateUndoHandler,
        'playlist_delete': PlaylistDeleteUndoHandler,
        'track_add': TrackAddUndoHandler,
        # Add more handlers as needed
    }

    @classmethod
    def get_handler(cls, action_type):
        handler_class = cls.HANDLERS.get(action_type)
        if handler_class:
            return handler_class()
        return None


class RedoHandlerFactory:
    """Factory for getting appropriate redo handler"""

    HANDLERS = {
        # Redo handlers are similar to undo but reverse direction
        'playlist_create': PlaylistCreateRedoHandler,
        # Add more as needed
    }

    @classmethod
    def get_handler(cls, action_type):
        handler_class = cls.HANDLERS.get(action_type)
        if handler_class:
            return handler_class()
        return None
