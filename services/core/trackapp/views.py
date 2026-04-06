from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from utils.responses import (
    SuccessResponse,
    ErrorResponse,
    NotFoundResponse,
    ForbiddenResponse,
    ValidationErrorResponse,
    ConflictResponse,
    ServiceUnavailableResponse,
    NoContentResponse,
)
from django.db import connection, transaction, IntegrityError
from playlistapp.models import Playlist, UserPlaylistArchive
from searchapp.models import Song
from .models import Track, UserTrackHide
from .serializers import TrackSerializer


def _require_playlist_owner(playlist_id, user_id):
    """Returns (playlist, None) if user owns the playlist, or (None, Response) otherwise."""
    try:
        playlist = Playlist.objects.get(id=playlist_id)
    except Playlist.DoesNotExist:
        return None, NotFoundResponse(message='Playlist not found')
    if playlist.owner_id != user_id:
        return None, ForbiddenResponse(message='Not authorized')
    return playlist, None


def _can_edit_playlist(playlist_id, user_id, request=None):
    """
    Check if user can edit playlist (owner or collaborator).
    Returns (playlist, None) if authorized, or (None, Response) otherwise.
    """
    try:
        playlist = Playlist.objects.get(id=playlist_id)
    except Playlist.DoesNotExist:
        return None, NotFoundResponse(message='Playlist not found')

    # Owner can always edit
    if playlist.owner_id == user_id:
        return playlist, None

    # Check if user is a collaborator via service client
    try:
        from utils.service_clients import CollaborationServiceClient
        auth_token = request.headers.get('Authorization', '') if request else None

        is_collab = CollaborationServiceClient.is_collaborator(
            playlist_id,
            user_id,
            auth_token
        )

        if is_collab:
            return playlist, None
        else:
            return None, ForbiddenResponse(message='Not authorized')
    except Exception as e:
        return None, ServiceUnavailableResponse(
            message=f'Failed to verify collaborator status: {str(e)}'
        )


TRACK_SORT_MAP = {
    'custom': 'position',
    'title': 'song__title',
    'artist': 'song__artist__name',
    'album': 'song__album__name',
    'genre': 'song__genre',
    'duration': 'song__duration_seconds',
    'year': 'song__release_year',
    'added_at': 'added_at',
}


class TrackListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Tracks"],
        summary="List tracks in playlist",
        description="Returns all tracks in a playlist, excluding tracks you've hidden. Supports sorting by position, title, artist, album, genre, duration, year, or date added. Custom sorting respects the manual order set by the playlist owner.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to get tracks from',
                required=True,
                example=123
            ),
            OpenApiParameter(
                name='sort',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort field: custom (manual order), title, artist, album, genre, duration, year, added_at',
                required=False,
                enum=['custom', 'title', 'artist', 'album', 'genre', 'duration', 'year', 'added_at'],
                example='custom'
            ),
            OpenApiParameter(
                name='order',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort order: asc (ascending) or desc (descending)',
                required=False,
                enum=['asc', 'desc'],
                example='asc'
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Retrieved 25 tracks'
                    },
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer', 'example': 789},
                                'playlist_id': {'type': 'integer', 'example': 123},
                                'song_id': {'type': 'integer', 'example': 456},
                                'position': {
                                    'type': 'integer',
                                    'description': 'Position in playlist (1-based)',
                                    'example': 1
                                },
                                'song': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer', 'example': 456},
                                        'title': {'type': 'string', 'example': 'Bohemian Rhapsody'},
                                        'artist': {
                                            'type': 'object',
                                            'properties': {
                                                'id': {'type': 'integer', 'example': 1},
                                                'name': {'type': 'string', 'example': 'Queen'}
                                            }
                                        },
                                        'album': {
                                            'type': 'object',
                                            'properties': {
                                                'id': {'type': 'integer', 'example': 1},
                                                'name': {'type': 'string', 'example': 'A Night at the Opera'}
                                            }
                                        },
                                        'duration_seconds': {'type': 'integer', 'example': 354},
                                        'genre': {'type': 'string', 'example': 'Rock'}
                                    }
                                },
                                'added_at': {
                                    'type': 'string',
                                    'format': 'date-time',
                                    'description': 'When track was added to playlist',
                                    'example': '2026-04-07T12:00:00Z'
                                },
                                'added_by': {
                                    'type': 'integer',
                                    'description': 'User ID who added this track',
                                    'example': 1
                                }
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Not authorized to access this playlist'
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Playlist not found'
                }
            }
        }
    )
    def get(self, request, playlist_id):
        sort = request.query_params.get('sort', 'custom')
        order = request.query_params.get('order', 'asc')
        order_field = TRACK_SORT_MAP.get(sort, 'position')
        if order == 'desc':
            order_field = '-' + order_field

        tracks = (
            Track.objects.filter(playlist_id=playlist_id)
            .exclude(hidden_by__user_id=request.user.id)
            .select_related('song', 'song__artist', 'song__album')
            .order_by(order_field)
        )
        return SuccessResponse(
            data=TrackSerializer(tracks, many=True).data,
            message=f'Retrieved {tracks.count()} tracks'
        )

    @extend_schema(
        tags=["Tracks"],
        summary="Add track to playlist",
        description="Adds a song to a playlist. Available to playlist owner and collaborators. The track will be added to the end of the playlist. Duplicate songs are not allowed.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to add the track to',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'song_id': {
                        'type': 'integer',
                        'description': 'Song ID from the search database to add to the playlist',
                        'example': 456
                    }
                },
                'required': ['song_id']
            }
        },
        examples=[
            OpenApiExample(
                'Add track to playlist',
                description='Add a song to an existing playlist',
                value={'song_id': 456}
            )
        ],
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Track added successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer', 'example': 789},
                            'playlist_id': {'type': 'integer', 'example': 123},
                            'song_id': {'type': 'integer', 'example': 456},
                            'position': {'type': 'integer', 'example': 1},
                            'added_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-07T15:30:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_song_id': {
                        'summary': 'Song ID not provided',
                        'value': {
                            'success': False,
                            'message': 'song_id required',
                            'errors': {
                                'song_id': ['This field is required']
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'User is not owner or collaborator',
                        'value': {
                            'success': False,
                            'message': 'Not authorized'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'playlist_not_found': {
                        'summary': 'Playlist does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    },
                    'song_not_found': {
                        'summary': 'Song does not exist in database',
                        'value': {
                            'success': False,
                            'message': 'Song not found'
                        }
                    }
                }
            },
            409: {
                'type': 'object',
                'examples': {
                    'duplicate_track': {
                        'summary': 'Song already in playlist',
                        'value': {
                            'success': False,
                            'message': 'Song already in playlist'
                        }
                    },
                    'playlist_limit': {
                        'summary': 'Playlist reached maximum song limit',
                        'value': {
                            'success': False,
                            'message': 'Playlist song limit reached',
                            'errors': {
                                'max_songs': [100]
                            }
                        }
                    }
                }
            }
        }
    )
    def post(self, request, playlist_id):
        song_id = request.data.get('song_id')
        if not song_id:
            return ValidationErrorResponse(
                errors={'song_id': 'This field is required'},
                message='song_id required'
            )

        try:
            song = Song.objects.get(id=song_id)
        except Song.DoesNotExist:
            return NotFoundResponse(message='Song not found')

        # Check if user can edit playlist (owner or collaborator)
        playlist, error_response = _can_edit_playlist(playlist_id, request.user.id, request)
        if error_response:
            return error_response

        # Wrap add-track in a transaction with row locking to prevent race conditions.
        # select_for_update() locks the playlist row so two concurrent requests cannot
        # both pass the exists()/count() pre-checks and then collide on the DB constraint.
        # The outer IntegrityError catch handles any remaining race that slips through.
        try:
            with transaction.atomic():
                playlist = Playlist.objects.select_for_update().get(id=playlist_id)

                if Track.objects.filter(playlist=playlist, song=song).exists():
                    return ConflictResponse(message='Song already in playlist')

                if playlist.max_songs > 0:
                    count = Track.objects.filter(playlist=playlist).count()
                    if count >= playlist.max_songs:
                        return ErrorResponse(
                            error='validation_error',
                            message='Playlist song limit reached',
                            details={'max_songs': playlist.max_songs}
                        )

                last = Track.objects.filter(playlist=playlist).order_by('-position').first()
                position = (last.position + 1) if last else 0

                track = Track.objects.create(
                    playlist=playlist,
                    song=song,
                    added_by_id=request.user.id,
                    position=position,
                )
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')
        except IntegrityError:
            # Race condition: two concurrent requests both passed the exists() check
            return ErrorResponse(
                error='validation_error',
                message='Song already in playlist'
            )

        return SuccessResponse(
            data=TrackSerializer(track).data,
            message='Track added to playlist',
            status_code=201
        )


class TrackDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Tracks"],
        summary="Delete track from playlist",
        description="Removes a specific track from a playlist. Only the playlist owner can delete tracks. The track is permanently removed and positions are automatically renumbered.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to remove track from',
                required=True,
                example=123
            ),
            OpenApiParameter(
                name='track_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Track ID to remove',
                required=True,
                example=789
            )
        ],
        responses={
            204: {
                'description': 'Track deleted successfully (no content returned)'
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_owner': {
                        'summary': 'Only owner can delete tracks',
                        'value': {
                            'success': False,
                            'message': 'Not authorized'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'track_not_found': {
                        'summary': 'Track does not exist in playlist',
                        'value': {
                            'success': False,
                            'message': 'Track not found'
                        }
                    },
                    'playlist_not_found': {
                        'summary': 'Playlist does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )
    def delete(self, request, playlist_id, track_id):
        _, err = _require_playlist_owner(playlist_id, request.user.id)
        if err:
            return err
        try:
            track = Track.objects.get(id=track_id, playlist_id=playlist_id)
            track.delete()
            return NoContentResponse()
        except Track.DoesNotExist:
            return NotFoundResponse(message='Track not found')


class TrackReorderRemoveView(APIView):
    """
    PUT /<playlist_id>/reorder/  body: {"track_ids": [id, id, ...]}

    Reorder-remove: the client sends the final desired ordered list of track IDs.
    Any tracks currently in the playlist that are absent from track_ids are deleted.
    Remaining tracks are assigned positions 0, 1, 2, ... matching the sent order.
    This handles the case where the user removes tracks while reordering and clicks save.
    Both operations happen atomically.

    Available to: Owner and collaborators
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Tracks"],
        summary="Reorder and remove tracks",
        description="""Reorders tracks and removes any tracks not in the provided list. Available to owner and collaborators.

**How it works:**
1. Send the final desired ordered list of track IDs
2. Tracks not in the list are removed from the playlist
3. Remaining tracks are renumbered to positions 0, 1, 2, ... matching the sent order

**Use case:** User reorders tracks in UI and removes some tracks, then clicks save. Both operations happen atomically in a single request.""",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to reorder',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'track_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'Final ordered list of track IDs. Any tracks in the playlist that are not in this list will be removed.',
                        'items': {
                            'type': 'integer',
                            'example': 5
                        },
                        'example': [5, 2, 8, 1, 9]
                    }
                },
                'required': ['track_ids']
            }
        },
        examples=[
            OpenApiExample(
                'Reorder only',
                description='Reorder all tracks without removing any',
                value={'track_ids': [5, 2, 8, 1, 9, 3, 7]}
            ),
            OpenApiExample(
                'Reorder and remove',
                description='Reorder tracks and remove tracks 4 and 6',
                value={'track_ids': [5, 2, 8, 1, 9, 3, 7]}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Tracks reordered successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'status': {
                                'type': 'string',
                                'example': 'reordered'
                            },
                            'tracks_updated': {
                                'type': 'integer',
                                'description': 'Number of tracks whose positions were updated',
                                'example': 7
                            },
                            'tracks_removed': {
                                'type': 'integer',
                                'description': 'Number of tracks that were removed from the playlist',
                                'example': 2
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_field': {
                        'summary': 'track_ids not provided',
                        'value': {
                            'success': False,
                            'message': 'track_ids required',
                            'errors': {
                                'track_ids': ['This field is required.']
                            }
                        }
                    },
                    'not_a_list': {
                        'summary': 'track_ids is not a list',
                        'value': {
                            'success': False,
                            'message': 'track_ids must be a list',
                            'errors': {
                                'track_ids': ['Must be a list']
                            }
                        }
                    },
                    'duplicates': {
                        'summary': 'track_ids contains duplicates',
                        'value': {
                            'success': False,
                            'message': 'track_ids must not contain duplicates',
                            'errors': {
                                'track_ids': ['Must not contain duplicates']
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Not authorized'
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Playlist not found'
                }
            }
        }
    )
    def put(self, request, playlist_id):
        if 'track_ids' not in request.data:
            return ValidationErrorResponse(
                errors={'track_ids': 'This field is required'},
                message='track_ids required'
            )
        ordered_ids = request.data.get('track_ids')
        if not isinstance(ordered_ids, list):
            return ValidationErrorResponse(
                errors={'track_ids': 'Must be a list'},
                message='track_ids must be a list'
            )
        if len(ordered_ids) != len(set(ordered_ids)):
            return ValidationErrorResponse(
                errors={'track_ids': 'Must not contain duplicates'},
                message='track_ids must not contain duplicates'
            )

        # Check authorization (owner or collaborator)
        playlist, err = _can_edit_playlist(playlist_id, request.user.id, request)
        if err:
            return err

        try:
            with transaction.atomic():
                playlist = Playlist.objects.select_for_update().get(id=playlist_id)

                existing_ids = set(
                    Track.objects.filter(playlist=playlist).values_list('id', flat=True)
                )
                for track_id in ordered_ids:
                    if track_id not in existing_ids:
                        return ErrorResponse(
                            error='validation_error',
                            message=f'Track {track_id} does not belong to this playlist'
                        )

                # Delete tracks not present in the new ordered list (reorder-remove)
                Track.objects.filter(playlist=playlist).exclude(id__in=ordered_ids).delete()
                # Reassign positions to match the submitted order
                for index, track_id in enumerate(ordered_ids):
                    Track.objects.filter(id=track_id, playlist=playlist).update(position=index)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        return SuccessResponse(
            data={'status': 'reordered'},
            message='Playlist tracks reordered successfully'
        )


class TrackRemoveView(APIView):
    """DELETE /<playlist_id>/remove/  body: {"track_ids": [1, 2, 3]}
    Removes specific tracks from a playlist without reordering remaining tracks."""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Tracks"],
        summary="Batch remove tracks",
        description="Removes multiple tracks from a playlist without reordering the remaining tracks. Available only to the playlist owner. Unlike the reorder endpoint, this operation does not change the positions of remaining tracks - gaps are left where tracks were removed. Use this for bulk deletion when maintaining order is not important.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to remove tracks from',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'required': ['track_ids'],
                'properties': {
                    'track_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'List of track IDs to remove from the playlist',
                        'minItems': 1,
                        'example': [5, 8, 12]
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Remove single track',
                description='Remove one track from the playlist',
                value={'track_ids': [5]}
            ),
            OpenApiExample(
                'Remove multiple tracks',
                description='Remove multiple tracks at once',
                value={'track_ids': [5, 8, 12, 15]}
            )
        ],
        responses={
            204: {
                'description': 'Tracks removed successfully (no content returned)'
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_track_ids': {
                        'summary': 'track_ids field not provided',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'track_ids': ['This field is required.']
                            }
                        }
                    },
                    'empty_array': {
                        'summary': 'track_ids array is empty',
                        'value': {
                            'success': False,
                            'message': 'At least one track ID must be provided'
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Not authorized'
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Playlist not found'
                }
            }
        }
    )
    def delete(self, request, playlist_id):
        _, err = _require_playlist_owner(playlist_id, request.user.id)
        if err:
            return err
        track_ids = request.data.get('track_ids', [])
        Track.objects.filter(playlist_id=playlist_id, id__in=track_ids).delete()
        return NoContentResponse()


class PlaylistArchiveView(APIView):
    """POST   /<playlist_id>/archive/  → archive playlist for requesting user
    DELETE /<playlist_id>/archive/  → unarchive playlist for requesting user"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Tracks"],
        summary="Archive playlist",
        description="Archives a playlist for the authenticated user. Archived playlists are hidden from default views and library listings but remain accessible. This is a user-specific action - archiving a playlist only affects your view, not other users or collaborators. Use this to declutter your library without losing access to playlists.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to archive',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'already_archived': {
                        'summary': 'Playlist was already archived (idempotent)',
                        'value': {
                            'success': True,
                            'message': 'Playlist archived successfully',
                            'data': {
                                'status': 'archived'
                            }
                        }
                    },
                    'newly_archived': {
                        'summary': 'Playlist newly archived',
                        'value': {
                            'success': True,
                            'message': 'Playlist archived successfully',
                            'data': {
                                'status': 'archived'
                            }
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Playlist not found'
                }
            }
        }
    )
    def post(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')
        UserPlaylistArchive.objects.get_or_create(user_id=request.user.id, playlist=playlist)
        return SuccessResponse(
            data={'status': 'archived'},
            message='Playlist archived successfully'
        )

    @extend_schema(
        tags=["Tracks"],
        summary="Unarchive playlist",
        description="Unarchives a playlist for the authenticated user, making it visible again in default views and library listings. This operation only affects your view of the playlist. If the playlist was not archived, this operation succeeds silently (idempotent).",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to unarchive',
                required=True,
                example=123
            )
        ],
        responses={
            204: {
                'description': 'Playlist unarchived successfully (no content returned). This is returned whether the playlist was archived or not (idempotent operation).'
            }
        }
    )
    def delete(self, request, playlist_id):
        UserPlaylistArchive.objects.filter(user_id=request.user.id, playlist_id=playlist_id).delete()
        return NoContentResponse()


class TrackHideView(APIView):
    """POST   /<playlist_id>/<track_id>/hide/  → hide track for requesting user
    DELETE /<playlist_id>/<track_id>/hide/  → unhide track for requesting user"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Tracks"],
        summary="Hide track",
        description="Hides a specific track within a playlist for the authenticated user only. Hidden tracks are excluded from track listings and playback queues for your account, but remain visible to other users and collaborators. This is useful for skipping songs you don't want to hear without deleting them from the playlist.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID containing the track',
                required=True,
                example=123
            ),
            OpenApiParameter(
                name='track_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Track ID to hide',
                required=True,
                example=456
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'already_hidden': {
                        'summary': 'Track was already hidden (idempotent)',
                        'value': {
                            'success': True,
                            'message': 'Track hidden successfully',
                            'data': {
                                'status': 'hidden'
                            }
                        }
                    },
                    'newly_hidden': {
                        'summary': 'Track newly hidden',
                        'value': {
                            'success': True,
                            'message': 'Track hidden successfully',
                            'data': {
                                'status': 'hidden'
                            }
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'track_not_found': {
                        'summary': 'Track does not exist in this playlist',
                        'value': {
                            'success': False,
                            'message': 'Track not found'
                        }
                    },
                    'playlist_not_found': {
                        'summary': 'Playlist does not exist',
                        'value': {
                            'success': False,
                            'message': 'Track not found'
                        }
                    }
                }
            }
        }
    )
    def post(self, request, playlist_id, track_id):
        try:
            track = Track.objects.get(id=track_id, playlist_id=playlist_id)
        except Track.DoesNotExist:
            return NotFoundResponse(message='Track not found')
        UserTrackHide.objects.get_or_create(user_id=request.user.id, track=track)
        return SuccessResponse(
            data={'status': 'hidden'},
            message='Track hidden successfully'
        )

    @extend_schema(
        tags=["Tracks"],
        summary="Unhide track",
        description="Unhides a previously hidden track, making it visible again in track listings and playback queues for your account. Only affects your view of the track - other users are unaffected. This operation is idempotent and succeeds even if the track was not hidden.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID containing the track',
                required=True,
                example=123
            ),
            OpenApiParameter(
                name='track_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Track ID to unhide',
                required=True,
                example=456
            )
        ],
        responses={
            204: {
                'description': 'Track unhidden successfully (no content returned). This is returned whether the track was hidden or not (idempotent operation).'
            }
        }
    )
    def delete(self, request, playlist_id, track_id):
        UserTrackHide.objects.filter(
            user_id=request.user.id,
            track_id=track_id,
            track__playlist_id=playlist_id,
        ).delete()
        return NoContentResponse()


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@extend_schema(
    tags=["Health"],
    summary="Track service health check",
    description="Check if the track service and database are healthy",
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'},
                'data': {
                    'type': 'object',
                    'properties': {
                        'status': {'type': 'string'},
                        'service': {'type': 'string'},
                        'database': {'type': 'string'}
                    }
                }
            }
        },
        503: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'}
            }
        }
    }
)
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return SuccessResponse(
            data={'status': 'healthy', 'service': 'track', 'database': 'connected'},
            message='Service is healthy'
        )
    except Exception as e:
        return ServiceUnavailableResponse(
            message=f'Database connection failed: {str(e)}'
        )


class TrackSortView(APIView):
    """
    PUT /<playlist_id>/sort/

    Sorts all tracks in a playlist by a specified field and persists the order.
    This updates the position field for all tracks based on the sort criteria.

    Available to: Owner and collaborators

    Request body:
    {
        "sort_by": "title|artist|album|genre|duration|year|added_at",
        "order": "asc|desc"
    }

    Response: List of tracks with updated positions
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Tracks"],
        summary="Sort playlist tracks",
        description="Sorts all tracks in a playlist by a specified field and persists the new order by updating the position field for all tracks. This is a permanent sort - the positions are saved to the database. Available to both owner and collaborators. **Note:** After sorting, tracks will remain in this order until manually reordered or sorted again.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to sort tracks for',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'required': ['sort_by', 'order'],
                'properties': {
                    'sort_by': {
                        'type': 'string',
                        'enum': ['title', 'artist', 'album', 'genre', 'duration', 'year', 'added_at'],
                        'description': 'Field to sort tracks by. Each field sorts alphabetically (strings) or numerically (numbers/integers).',
                        'example': 'title'
                    },
                    'order': {
                        'type': 'string',
                        'enum': ['asc', 'desc'],
                        'description': 'Sort order: asc (ascending) or desc (descending)',
                        'example': 'asc'
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Sort by title ascending',
                description='Sort tracks alphabetically by song title A-Z',
                value={
                    'sort_by': 'title',
                    'order': 'asc'
                }
            ),
            OpenApiExample(
                'Sort by artist descending',
                description='Sort tracks alphabetically by artist name Z-A',
                value={
                    'sort_by': 'artist',
                    'order': 'desc'
                }
            ),
            OpenApiExample(
                'Sort by duration descending',
                description='Sort tracks by length, longest first',
                value={
                    'sort_by': 'duration',
                    'order': 'desc'
                }
            ),
            OpenApiExample(
                'Sort by added date descending',
                description='Sort tracks by when they were added, newest first',
                value={
                    'sort_by': 'added_at',
                    'order': 'desc'
                }
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Tracks sorted successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'sort_by': {
                                'type': 'string',
                                'description': 'The field that was used for sorting',
                                'example': 'title'
                            },
                            'order': {
                                'type': 'string',
                                'description': 'The sort order that was applied',
                                'example': 'asc'
                            },
                            'tracks_updated': {
                                'type': 'integer',
                                'description': 'Number of tracks that were repositioned',
                                'example': 25
                            },
                            'tracks': {
                                'type': 'array',
                                'description': 'Array of tracks with updated positions',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer'},
                                        'position': {'type': 'integer'},
                                        'song': {
                                            'type': 'object',
                                            'properties': {
                                                'id': {'type': 'integer'},
                                                'title': {'type': 'string'},
                                                'artist': {'type': 'string'},
                                                'album': {'type': 'string'},
                                                'genre': {'type': 'string'},
                                                'duration': {'type': 'integer'},
                                                'year': {'type': 'integer'}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_sort_by': {
                        'summary': 'sort_by field not provided',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'sort_by': ['This field is required.']
                            }
                        }
                    },
                    'missing_order': {
                        'summary': 'order field not provided',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'order': ['This field is required.']
                            }
                        }
                    },
                    'invalid_sort_by': {
                        'summary': 'Invalid sort_by value',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'sort_by': ['"invalid" is not a valid choice. Choose from: title, artist, album, genre, duration, year, added_at']
                            }
                        }
                    },
                    'invalid_order': {
                        'summary': 'Invalid order value',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'order': ['"invalid" is not a valid choice. Choose from: asc, desc']
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Not authorized'
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Playlist not found'
                }
            }
        }
    )
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def put(self, request, playlist_id):
        sort_by = request.data.get('sort_by', 'custom')
        order = request.data.get('order', 'asc')

        if sort_by not in TRACK_SORT_MAP:
            return ValidationErrorResponse(
                errors={'sort_by': f'Must be one of: {", ".join(TRACK_SORT_MAP.keys())}'},
                message='Invalid sort field'
            )

        if order not in ['asc', 'desc']:
            return ValidationErrorResponse(
                errors={'order': 'Must be asc or desc'},
                message='Invalid order'
            )

        # Check authorization (owner or collaborator)
        playlist, err = _can_edit_playlist(playlist_id, request.user.id, request)
        if err:
            return err

        try:
            with transaction.atomic():
                # Get all tracks with related data
                tracks = Track.objects.filter(playlist=playlist).select_related(
                    'song', 'song__artist', 'song__album'
                )

                # Determine sort field
                order_field = TRACK_SORT_MAP[sort_by]
                if order == 'desc':
                    order_field = '-' + order_field

                # Sort tracks in Python (since we need to update positions)
                # For custom/position sort, we just use current order
                if sort_by == 'custom':
                    sorted_tracks = list(tracks.order_by('position'))
                else:
                    # Sort using Django's ordering, then convert to list
                    sorted_tracks = list(tracks.order_by(order_field))

                # Update positions to match new order
                track_updates = []
                for index, track in enumerate(sorted_tracks):
                    track.position = index
                    track_updates.append(track)

                # Bulk update positions
                Track.objects.bulk_update(track_updates, ['position'])

                return SuccessResponse(
                    data={
                        'sort_by': sort_by,
                        'order': order,
                        'tracks_updated': len(sorted_tracks),
                        'tracks': TrackSerializer(sorted_tracks, many=True).data
                    },
                    message=f'Playlist sorted by {sort_by} ({order})'
                )

        except Exception as e:
            return ErrorResponse(
                error='sort_failed',
                message=str(e),
                status_code=500
            )
