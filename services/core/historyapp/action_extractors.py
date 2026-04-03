"""
Extract action details from requests.
Each extractor knows how to capture before/after state for specific endpoints.

Canon Events (NOT undoable):
- Leaving a playlist (social contract)
- Transferring ownership (permanent change)
- Making/removing collaboration (permissions change)

Undoable/Redoable Actions:
- Creating/deleting playlists
- Editing playlist details
- Adding/removing/reordering tracks
- Comments (add/edit/delete)
- Visibility changes
"""
import json


class ActionExtractor:
    """Base class for action extractors"""

    def extract(self, request, response):
        """Extract action details from request/response

        Returns dict with:
        - action_type: str
        - entity_type: str
        - entity_id: int
        - before_state: dict
        - after_state: dict
        - delta: dict
        - description: str
        - is_undoable: bool (optional, defaults to True)
        """
        raise NotImplementedError


class PlaylistCreateExtractor(ActionExtractor):
    """Extract playlist creation details"""

    def extract(self, request, response):
        from playlistapp.models import Playlist

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
                'before_state': {},
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
                'is_undoable': True,
            }
        except Playlist.DoesNotExist:
            return None


class PlaylistUpdateExtractor(ActionExtractor):
    """Extract playlist update details (visibility, name, description changes)"""

    def extract(self, request, response):
        from playlistapp.models import Playlist

        parts = request.path.strip('/').split('/')
        try:
            playlist_id_index = parts.index('playlists') + 1
            playlist_id = int(parts[playlist_id_index])
        except (ValueError, IndexError):
            return None

        try:
            playlist = Playlist.objects.get(id=playlist_id)

            try:
                request_data = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, AttributeError):
                request_data = {}

            return {
                'action_type': 'playlist_update',
                'entity_type': 'playlist',
                'entity_id': playlist.id,
                'before_state': {},
                'after_state': {
                    'id': playlist.id,
                    'name': playlist.name,
                    'description': playlist.description,
                    'visibility': playlist.visibility,
                },
                'delta': request_data,
                'description': f'Updated playlist "{playlist.name}"',
                'is_undoable': True,
            }
        except Playlist.DoesNotExist:
            return None


class PlaylistDeleteExtractor(ActionExtractor):
    """Extract playlist deletion details"""

    def extract(self, request, response):
        from playlistapp.models import Playlist
        from trackapp.models import Track

        parts = request.path.strip('/').split('/')
        try:
            playlist_id_index = parts.index('playlists') + 1
            playlist_id = int(parts[playlist_id_index])
        except (ValueError, IndexError):
            return None

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
            'after_state': {},
            'delta': {
                'deleted_id': playlist_id,
            },
            'description': f'Deleted playlist "{before_state.get("name", playlist_id)}"',
            'is_undoable': True,
        }


class PlaylistFollowExtractor(ActionExtractor):
    """Extract playlist follow/unfollow actions - UNDOABLE"""

    def extract(self, request, response):
        from playlistapp.models import Playlist

        parts = request.path.strip('/').split('/')
        try:
            playlist_id_index = parts.index('playlists') + 1
            playlist_id = int(parts[playlist_id_index])
        except (ValueError, IndexError):
            return None

        try:
            playlist = Playlist.objects.get(id=playlist_id)
            action_type = 'playlist_follow' if request.method == 'POST' else 'playlist_unfollow'

            return {
                'action_type': action_type,
                'entity_type': 'playlist',
                'entity_id': playlist.id,
                'before_state': {},
                'after_state': {
                    'playlist_id': playlist.id,
                    'playlist_name': playlist.name,
                },
                'delta': {
                    'playlist_id': playlist.id,
                },
                'description': f'{"Followed" if request.method == "POST" else "Unfollowed"} playlist "{playlist.name}"',
                'is_undoable': True,
            }
        except Playlist.DoesNotExist:
            return None


class PlaylistLikeExtractor(ActionExtractor):
    """Extract playlist like/unlike actions - UNDOABLE"""

    def extract(self, request, response):
        from playlistapp.models import Playlist

        parts = request.path.strip('/').split('/')
        try:
            playlist_id_index = parts.index('playlists') + 1
            playlist_id = int(parts[playlist_id_index])
        except (ValueError, IndexError):
            return None

        try:
            playlist = Playlist.objects.get(id=playlist_id)
            action_type = 'playlist_like' if request.method == 'POST' else 'playlist_unlike'

            return {
                'action_type': action_type,
                'entity_type': 'playlist',
                'entity_id': playlist.id,
                'before_state': {},
                'after_state': {
                    'playlist_id': playlist.id,
                    'playlist_name': playlist.name,
                },
                'delta': {
                    'playlist_id': playlist.id,
                },
                'description': f'{"Liked" if request.method == "POST" else "Unliked"} playlist "{playlist.name}"',
                'is_undoable': True,
            }
        except Playlist.DoesNotExist:
            return None


class PlaylistMakeCollaborativeExtractor(ActionExtractor):
    """Extract playlist make collaborative action - CANON EVENT (NOT undoable)"""

    def extract(self, request, response):
        from playlistapp.models import Playlist

        parts = request.path.strip('/').split('/')
        try:
            playlist_id_index = parts.index('playlists') + 1
            playlist_id = int(parts[playlist_id_index])
        except (ValueError, IndexError):
            return None

        try:
            playlist = Playlist.objects.get(id=playlist_id)

            return {
                'action_type': 'playlist_make_collaborative',
                'entity_type': 'playlist',
                'entity_id': playlist.id,
                'before_state': {},
                'after_state': {
                    'playlist_id': playlist.id,
                    'playlist_name': playlist.name,
                    'playlist_type': playlist.playlist_type,
                },
                'delta': {
                    'playlist_id': playlist.id,
                    'new_type': 'collaborative',
                },
                'description': f'Made playlist "{playlist.name}" collaborative (CANON EVENT)',
                'is_undoable': False,  # Canon event - not undoable
            }
        except Playlist.DoesNotExist:
            return None


class TrackAddExtractor(ActionExtractor):
    """Extract track addition details"""

    def extract(self, request, response):
        from trackapp.models import Track

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
                'is_undoable': True,
            }
        except Track.DoesNotExist:
            return None


class TrackRemoveExtractor(ActionExtractor):
    """Extract track removal details"""

    def extract(self, request, response):
        from trackapp.models import Track
        from searchapp.models import Song

        parts = request.path.strip('/').split('/')
        try:
            track_id_index = parts.index('tracks') + 1
            track_id = int(parts[track_id_index])
        except (ValueError, IndexError):
            return None

        try:
            track = Track.objects.get(id=track_id)
            song = Song.objects.get(id=track.song_id)

            return {
                'action_type': 'track_remove',
                'entity_type': 'track',
                'entity_id': track_id,
                'before_state': {
                    'id': track.id,
                    'playlist_id': track.playlist_id,
                    'song_id': track.song_id,
                    'song_title': song.title,
                    'position': track.position,
                },
                'after_state': {},
                'delta': {
                    'removed_track_id': track_id,
                    'playlist_id': track.playlist_id,
                    'song_id': track.song_id,
                },
                'description': f'Removed track from playlist {track.playlist_id}',
                'is_undoable': True,
            }
        except (Track.DoesNotExist, Song.DoesNotExist):
            return None


class CommentAddExtractor(ActionExtractor):
    """Extract comment addition details"""

    def extract(self, request, response):
        from playlistapp.models import PlaylistComment

        try:
            response_data = json.loads(response.content.decode('utf-8'))
            if 'data' in response_data:
                comment_id = response_data['data'].get('id')
            else:
                return None
        except (json.JSONDecodeError, KeyError):
            return None

        try:
            comment = PlaylistComment.objects.get(id=comment_id)
            playlist = comment.playlist

            return {
                'action_type': 'comment_add',
                'entity_type': 'comment',
                'entity_id': comment.id,
                'before_state': {},
                'after_state': {
                    'id': comment.id,
                    'playlist_id': comment.playlist_id,
                    'content': comment.content[:100] + '...' if len(comment.content) > 100 else comment.content,
                },
                'delta': {
                    'comment_id': comment.id,
                    'playlist_id': comment.playlist_id,
                },
                'description': f'Added comment to playlist "{playlist.name}"',
                'is_undoable': True,
            }
        except PlaylistComment.DoesNotExist:
            return None


class CommentEditExtractor(ActionExtractor):
    """Extract comment edit details"""

    def extract(self, request, response):
        from playlistapp.models import PlaylistComment

        parts = request.path.strip('/').split('/')
        try:
            comment_id_index = parts.index('comments') + 1
            comment_id = int(parts[comment_id_index])
        except (ValueError, IndexError):
            return None

        try:
            comment = PlaylistComment.objects.get(id=comment_id)

            # Get request data for new content
            try:
                request_data = json.loads(request.body.decode('utf-8'))
                new_content = request_data.get('content', '')
            except (json.JSONDecodeError, AttributeError):
                new_content = comment.content

            return {
                'action_type': 'comment_edit',
                'entity_type': 'comment',
                'entity_id': comment.id,
                'before_state': {
                    'id': comment.id,
                    'content': comment.content,
                },
                'after_state': {
                    'id': comment.id,
                    'content': new_content[:100] + '...' if len(new_content) > 100 else new_content,
                },
                'delta': {
                    'comment_id': comment.id,
                    'old_content': comment.content,
                    'new_content': new_content,
                },
                'description': f'Edited comment',
                'is_undoable': True,
            }
        except PlaylistComment.DoesNotExist:
            return None


class CommentLikeExtractor(ActionExtractor):
    """Extract comment like/remove like actions - UNDOABLE"""

    def extract(self, request, response):
        from playlistapp.models import PlaylistComment, PlaylistCommentLike

        parts = request.path.strip('/').split('/')
        try:
            comment_id_index = parts.index('comments') + 1
            comment_id = int(parts[comment_id_index])
        except (ValueError, IndexError):
            return None

        try:
            comment = PlaylistComment.objects.get(id=comment_id)
            action_type = 'comment_like' if request.method == 'POST' else 'comment_remove_like'

            return {
                'action_type': action_type,
                'entity_type': 'comment_like',
                'entity_id': comment.id,
                'before_state': {},
                'after_state': {
                    'comment_id': comment.id,
                    'playlist_id': comment.playlist_id,
                },
                'delta': {
                    'comment_id': comment.id,
                },
                'description': f'{"Liked" if request.method == "POST" else "Removed like from"} comment',
                'is_undoable': True,
            }
        except PlaylistComment.DoesNotExist:
            return None


class CommentReplyExtractor(ActionExtractor):
    """Extract comment reply actions - UNDOABLE"""

    def extract(self, request, response):
        from playlistapp.models import PlaylistComment

        try:
            response_data = json.loads(response.content.decode('utf-8'))
            if 'data' in response_data:
                reply_id = response_data['data'].get('id')
            else:
                return None
        except (json.JSONDecodeError, KeyError):
            return None

        try:
            reply = PlaylistComment.objects.get(id=reply_id)
            parent_comment = PlaylistComment.objects.get(id=reply.parent_id) if reply.parent_id else None

            return {
                'action_type': 'comment_reply',
                'entity_type': 'comment',
                'entity_id': reply.id,
                'before_state': {},
                'after_state': {
                    'id': reply.id,
                    'playlist_id': reply.playlist_id,
                    'parent_comment_id': reply.parent_id,
                    'content': reply.content[:100] + '...' if len(reply.content) > 100 else reply.content,
                },
                'delta': {
                    'reply_id': reply.id,
                    'parent_comment_id': reply.parent_id,
                },
                'description': f'Replied to comment' + (f' (parent: #{reply.parent_id})' if reply.parent_id else ''),
                'is_undoable': True,
            }
        except PlaylistComment.DoesNotExist:
            return None


class LikedSongsAddExtractor(ActionExtractor):
    """Extract add to liked songs - UNDOABLE"""

    def extract(self, request, response):
        parts = request.path.strip('/').split('/')
        try:
            track_id_index = parts.index('tracks') + 1
            track_id = int(parts[track_id_index])
        except (ValueError, IndexError):
            return None

        # URL pattern: /api/tracks/{id}/like/ or similar
        if 'like' in parts:
            try:
                from trackapp.models import Track
                from searchapp.models import Song

                track = Track.objects.get(id=track_id)
                song = Song.objects.get(id=track.song_id)

                return {
                    'action_type': 'liked_songs_add',
                    'entity_type': 'track',
                    'entity_id': track.id,
                    'before_state': {},
                    'after_state': {
                        'track_id': track.id,
                        'song_id': song.id,
                        'song_title': song.title,
                        'playlist_id': track.playlist_id,
                    },
                    'delta': {
                        'track_id': track.id,
                        'song_id': song.id,
                    },
                    'description': f'Added "{song.title}" to Liked Songs',
                    'is_undoable': True,
                }
            except (Track.DoesNotExist, Song.DoesNotExist):
                return None

        return None


class LikedSongsRemoveExtractor(ActionExtractor):
    """Extract remove from liked songs - UNDOABLE"""

    def extract(self, request, response):
        parts = request.path.strip('/').split('/')
        try:
            track_id_index = parts.index('tracks') + 1
            track_id = int(parts[track_id_index])
        except (ValueError, IndexError):
            return None

        # URL pattern: /api/tracks/{id}/unlike/ or similar
        if 'unlike' in parts or request.method == 'DELETE':
            try:
                from trackapp.models import Track
                from searchapp.models import Song

                track = Track.objects.get(id=track_id)
                song = Song.objects.get(id=track.song_id)

                return {
                    'action_type': 'liked_songs_remove',
                    'entity_type': 'track',
                    'entity_id': track.id,
                    'before_state': {
                        'track_id': track.id,
                        'song_id': song.id,
                        'song_title': song.title,
                        'playlist_id': track.playlist_id,
                    },
                    'after_state': {},
                    'delta': {
                        'track_id': track.id,
                        'song_id': song.id,
                    },
                    'description': f'Removed "{song.title}" from Liked Songs',
                    'is_undoable': True,
                }
            except (Track.DoesNotExist, Song.DoesNotExist):
                return None

        return None


class CommentDeleteExtractor(ActionExtractor):
    """Extract comment deletion details"""

    def extract(self, request, response):
        from playlistapp.models import PlaylistComment

        parts = request.path.strip('/').split('/')
        try:
            comment_id_index = parts.index('comments') + 1
            comment_id = int(parts[comment_id_index])
        except (ValueError, IndexError):
            return None

        try:
            comment = PlaylistComment.objects.get(id=comment_id)
            playlist = comment.playlist

            return {
                'action_type': 'comment_delete',
                'entity_type': 'comment',
                'entity_id': comment_id,
                'before_state': {
                    'id': comment.id,
                    'playlist_id': comment.playlist_id,
                    'content': comment.content,
                },
                'after_state': {},
                'delta': {
                    'deleted_comment_id': comment_id,
                    'playlist_id': comment.playlist_id,
                },
                'description': f'Deleted comment from playlist "{playlist.name}"',
                'is_undoable': True,
            }
        except PlaylistComment.DoesNotExist:
            return None


class CollaboratorAddExtractor(ActionExtractor):
    """Extract collaborator addition - CANON EVENT (NOT undoable)"""

    def extract(self, request, response):
        parts = request.path.strip('/').split('/')
        try:
            playlist_id_index = parts.index('playlists') + 1
            playlist_id = int(parts[playlist_id_index])
        except (ValueError, IndexError):
            return None

        try:
            from playlistapp.models import Playlist
            playlist = Playlist.objects.get(id=playlist_id)

            # Try to get user_id from request
            try:
                request_data = json.loads(request.body.decode('utf-8'))
                user_id = request_data.get('user_id', 'unknown')
            except (json.JSONDecodeError, AttributeError):
                user_id = 'unknown'

            return {
                'action_type': 'collaborator_add',
                'entity_type': 'playlist',
                'entity_id': playlist.id,
                'before_state': {},
                'after_state': {
                    'playlist_id': playlist.id,
                    'playlist_name': playlist.name,
                    'added_user_id': user_id,
                },
                'delta': {
                    'playlist_id': playlist.id,
                    'added_user_id': user_id,
                },
                'description': f'Added collaborator to playlist "{playlist.name}" (CANON EVENT)',
                'is_undoable': False,  # Canon event - not undoable
            }
        except Playlist.DoesNotExist:
            return None


class CollaboratorRemoveExtractor(ActionExtractor):
    """Extract collaborator removal - CANON EVENT (NOT undoable)"""

    def extract(self, request, response):
        parts = request.path.strip('/').split('/')
        try:
            playlist_id_index = parts.index('playlists') + 1
            playlist_id = int(parts[playlist_id_index])
        except (ValueError, IndexError):
            return None

        try:
            from playlistapp.models import Playlist
            playlist = Playlist.objects.get(id=playlist_id)

            # Try to get user_id from URL or request
            user_id = 'unknown'
            # URL pattern: /api/playlists/{id}/collaborators/{user_id}
            if 'collaborators' in parts:
                try:
                    collab_index = parts.index('collaborators') + 1
                    user_id = int(parts[collab_index])
                except (ValueError, IndexError):
                    pass

            return {
                'action_type': 'collaborator_remove',
                'entity_type': 'playlist',
                'entity_id': playlist.id,
                'before_state': {},
                'after_state': {
                    'playlist_id': playlist.id,
                    'playlist_name': playlist.name,
                    'removed_user_id': user_id,
                },
                'delta': {
                    'playlist_id': playlist.id,
                    'removed_user_id': user_id,
                },
                'description': f'Removed collaborator from playlist "{playlist.name}" (CANON EVENT)',
                'is_undoable': False,  # Canon event - not undoable
            }
        except Playlist.DoesNotExist:
            return None


# Registry of extractors
# Maps (method, path_prefix) to extractor instance
EXTRACTORS = {
    # Playlist operations
    ('POST', '/api/playlists/'): PlaylistCreateExtractor(),
    ('PATCH', '/api/playlists/'): PlaylistUpdateExtractor(),
    ('PUT', '/api/playlists/'): PlaylistUpdateExtractor(),
    ('DELETE', '/api/playlists/'): PlaylistDeleteExtractor(),

    # Track operations
    ('POST', '/api/tracks/'): TrackAddExtractor(),
    ('DELETE', '/api/tracks/'): TrackRemoveExtractor(),

    # Comment operations
    ('PATCH', '/api/comments/'): CommentEditExtractor(),
    ('PUT', '/api/comments/'): CommentEditExtractor(),
    ('DELETE', '/api/comments/'): CommentDeleteExtractor(),

    # Liked songs
    ('POST', '/api/tracks/'): LikedSongsAddExtractor(),
    ('DELETE', '/api/tracks/'): LikedSongsRemoveExtractor(),
}


def get_action_extractor(path, method):
    """Get appropriate extractor for path and method"""
    path_without_query = path.split('?')[0]
    normalized_path = path_without_query.rstrip('/')

    # Special handling for sub-resources

    # Comments: /api/playlists/{id}/comments/
    if '/comments/' in normalized_path and method == 'POST':
        # Check if it's a reply: /api/comments/{id}/replies/
        if '/replies' in normalized_path:
            return CommentReplyExtractor()
        return CommentAddExtractor()

    # Comment likes: /api/comments/{id}/like/
    if normalized_path.endswith('/like') and '/comments/' in normalized_path and method in ['POST', 'DELETE']:
        return CommentLikeExtractor()

    # Social features: /api/playlists/{id}/follow/
    if normalized_path.endswith('/follow') and method in ['POST', 'DELETE']:
        return PlaylistFollowExtractor()

    # Social features: /api/playlists/{id}/like/
    if normalized_path.endswith('/like') and method in ['POST', 'DELETE']:
        return PlaylistLikeExtractor()

    # Liked songs: /api/tracks/{id}/like/ or /api/tracks/{id}/unlike/
    if normalized_path.endswith('/like') and method == 'POST':
        return LikedSongsAddExtractor()
    if normalized_path.endswith('/unlike') and method in ['POST', 'DELETE']:
        return LikedSongsRemoveExtractor()

    # Collaborators: /api/playlists/{id}/collaborators/ (CANON EVENTS)
    if '/collaborators/' in normalized_path and method == 'POST':
        return CollaboratorAddExtractor()
    if '/collaborators/' in normalized_path and method in ['DELETE', 'PATCH']:
        return CollaboratorRemoveExtractor()

    # Standard path matching
    for (extractor_method, extractor_path), extractor in EXTRACTORS.items():
        if method == extractor_method and normalized_path.startswith(extractor_path.rstrip('/')):
            # For playlist operations, make sure we're not matching sub-resources incorrectly
            if extractor_path == '/api/playlists/':
                # Check if it's a sub-resource (follow, like, comments, collaborators)
                if any(x in normalized_path for x in ['/follow', '/like', '/comments', '/collaborators']):
                    continue

            # For track operations, check for like/unlike sub-resources
            if extractor_path == '/api/tracks/':
                if '/like' in normalized_path or '/unlike' in normalized_path:
                    continue

            return extractor

    return None
