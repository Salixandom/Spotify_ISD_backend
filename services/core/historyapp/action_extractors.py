"""
Extract action details from requests.
Each extractor knows how to capture before/after state for specific endpoints.
"""
import json
from rest_framework.request import Request


class ActionExtractor:
    """Base class for action extractors"""

    def extract(self, request, response):
        """Extract action details from request/response"""
        raise NotImplementedError


class PlaylistCreateExtractor(ActionExtractor):
    """Extract playlist creation details"""

    def extract(self, request, response):
        from playlistapp.models import Playlist

        # After state from response
        try:
            response_data = json.loads(response.content.decode('utf-8'))
            if 'data' in response_data:
                playlist_id = response_data['data'].get('id')
            else:
                return None
        except (json.JSONDecodeError, KeyError):
            return None

        try:
            playlist = Playlist.objects.get(id=playlist_id)

            return {
                'action_type': 'playlist_create',
                'entity_type': 'playlist',
                'entity_id': playlist.id,
                'before_state': {},  # No before state for creation
                'after_state': {
                    'id': playlist.id,
                    'name': playlist.name,
                    'description': playlist.description,
                    'owner_id': playlist.owner_id,
                    'visibility': playlist.visibility,
                    'playlist_type': playlist.playlist_type,
                    'max_songs': playlist.max_songs,
                    'cover_url': playlist.cover_url,
                },
                'delta': {
                    'created_id': playlist.id,
                },
                'description': f'Created playlist "{playlist.name}"',
            }
        except Playlist.DoesNotExist:
            return None


class PlaylistDeleteExtractor(ActionExtractor):
    """Extract playlist deletion details"""

    def extract(self, request, response):
        from playlistapp.models import Playlist
        from trackapp.models import Track

        # Extract playlist_id from URL
        # URL pattern: /api/playlists/{id}/
        parts = request.path.strip('/').split('/')
        try:
            playlist_id_index = parts.index('playlists') + 1
            playlist_id = int(parts[playlist_id_index])
        except (ValueError, IndexError):
            return None

        # Capture before state (everything before deletion)
        try:
            playlist = Playlist.objects.get(id=playlist_id)
            tracks = Track.objects.filter(playlist=playlist).select_related('song')

            before_state = {
                'id': playlist.id,
                'name': playlist.name,
                'description': playlist.description,
                'owner_id': playlist.owner_id,
                'visibility': playlist.visibility,
                'playlist_type': playlist.playlist_type,
                'max_songs': playlist.max_songs,
                'cover_url': playlist.cover_url,
                'created_at': playlist.created_at.isoformat() if playlist.created_at else None,
                'updated_at': playlist.updated_at.isoformat() if playlist.updated_at else None,
                'tracks': [
                    {
                        'id': track.id,
                        'song_id': track.song_id,
                        'position': track.position,
                        'added_at': track.added_at.isoformat() if track.added_at else None,
                    }
                    for track in tracks.order_by('position')
                ],
            }
        except Playlist.DoesNotExist:
            before_state = {}

        return {
            'action_type': 'playlist_delete',
            'entity_type': 'playlist',
            'entity_id': playlist_id,
            'before_state': before_state,
            'after_state': {},  # No after state for deletion
            'delta': {
                'deleted_id': playlist_id,
            },
            'description': f'Deleted playlist "{before_state.get("name", playlist_id)}"',
        }


class TrackAddExtractor(ActionExtractor):
    """Extract track addition details"""

    def extract(self, request, response):
        from trackapp.models import Track

        # After state from response
        try:
            response_data = json.loads(response.content.decode('utf-8'))
            if 'data' in response_data:
                track_id = response_data['data'].get('id')
            else:
                return None
        except (json.JSONDecodeError, KeyError):
            return None

        try:
            track = Track.objects.get(id=track_id)
            playlist_tracks_before = Track.objects.filter(playlist_id=track.playlist_id).count() - 1

            return {
                'action_type': 'track_add',
                'entity_type': 'track',
                'entity_id': track.id,
                'before_state': {
                    'playlist_id': track.playlist_id,
                    'track_count': playlist_tracks_before,
                },
                'after_state': {
                    'id': track.id,
                    'playlist_id': track.playlist_id,
                    'song_id': track.song_id,
                    'position': track.position,
                    'added_at': track.added_at.isoformat() if track.added_at else None,
                },
                'delta': {
                    'added_track_id': track.id,
                    'song_id': track.song_id,
                    'playlist_id': track.playlist_id,
                },
                'description': f'Added track to playlist {track.playlist_id}',
            }
        except Track.DoesNotExist:
            return None


# Simplified registry for initial implementation
EXTRACTORS = {
    # Playlist operations
    ('POST', '/api/playlists/'): PlaylistCreateExtractor(),
    ('DELETE', '/api/playlists/'): PlaylistDeleteExtractor,

    # Track operations
    ('POST', '/api/tracks/'): TrackAddExtractor,

    # More extractors can be added as needed
}


def get_action_extractor(path, method):
    """Get appropriate extractor for path and method"""
    # Remove query parameters for matching
    path_without_query = path.split('?')[0]

    # Normalize path (remove trailing slash for consistency)
    normalized_path = path_without_query.rstrip('/')

    for (extractor_method, extractor_path), extractor in EXTRACTORS.items():
        if method == extractor_method and normalized_path.startswith(extractor_path.rstrip('/')):
            return extractor

    return None
