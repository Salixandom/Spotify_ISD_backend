from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from django.db import connection
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from utils.responses import (
    SuccessResponse,
    ErrorResponse,
    ValidationErrorResponse,
    NotFoundResponse,
    ForbiddenResponse,
    ServiceUnavailableResponse,
)
from django.db.models import Q, Count, Sum
from django.utils import timezone
from .models import Playlist, UserPlaylistFollow, UserPlaylistLike, PlaylistSnapshot, PlaylistComment, PlaylistCommentLike
from utils.service_clients import CollaborationServiceClient
from .serializers import PlaylistSerializer, PlaylistSnapshotSerializer, PlaylistCommentSerializer, PlaylistCommentLikeSerializer
from trackapp.models import Track

PLAYLIST_SORT_MAP = {
    'name':        'name',
    'created_at':  'created_at',
    'updated_at':  'updated_at',
    'track_count': 'track_count',
}


def user_can_moderate_comment(playlist, comment, user_id, auth_header=''):
    """
    Check if a user can moderate (edit/delete) a comment.
    Returns True if user is:
    - The comment author
    - The playlist owner (can moderate any comment including their own)
    - A collaborator (can moderate comments from non-owners, but NOT owner's comments)
    """
    # Comment author can always moderate their own comment
    if comment.user_id == user_id:
        return True

    # Playlist owner can moderate any comment
    if playlist.owner_id == user_id:
        return True

    # Collaborators can moderate comments from non-owners
    try:
        collaborative_playlist_ids = CollaborationServiceClient.get_user_collaborations(user_id, auth_header)
        if playlist.id in collaborative_playlist_ids:
            # Collaborators CANNOT moderate owner's comments
            if comment.user_id != playlist.owner_id:
                return True
    except Exception:
        pass

    return False


def user_can_access_playlist(playlist, user_id, auth_header=''):
    """
    Check if a user can access a playlist.
    Returns True if user is:
    - The owner of the playlist
    - A collaborator on the playlist
    - The playlist is public
    """
    # Check if user is owner
    if playlist.owner_id == user_id:
        return True

    # Check if playlist is public
    if playlist.visibility == 'public':
        return True

    # Check if user is a collaborator
    try:
        collaborative_playlist_ids = CollaborationServiceClient.get_user_collaborations(user_id, auth_header)
        logger = __import__('logging').getLogger(__name__)
        logger.error(f"DEBUG: User {user_id} collaborations: {collaborative_playlist_ids}, playlist {playlist.id}")
        if playlist.id in collaborative_playlist_ids:
            return True
    except Exception as e:
        logger = __import__('logging').getLogger(__name__)
        logger.error(f"DEBUG: Collaboration check failed for user {user_id}, playlist {playlist.id}: {e}")
        pass  # If service call fails, deny access

    return False


class PlaylistViewSet(viewsets.ModelViewSet):
    serializer_class = PlaylistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Enhanced filtering for playlist list:
        - visibility: public|private
        - type: solo|collaborative
        - is_system_generated: true|false (filter by system-generated vs user-created)
        - q: search in name/description
        - min_tracks, max_tracks: track count range
        - created_after, created_before: date range
        - sort: name|created_at|updated_at|track_count
        - order: asc|desc
        - include_archived: true (default: excluded)
        - include_followed: true (default: excluded)
        - filter: followed|liked (special filters)
        """
        # Special filters - handle BEFORE base queryset to avoid restricting results
        filter_type = self.request.query_params.get('filter')
        if filter_type == 'followed':
            # Get ALL playlists the user follows, not just owned/collaborated ones
            followed_playlist_ids = UserPlaylistFollow.objects.filter(
                user_id=self.request.user.id
            ).values_list('playlist_id', flat=True)
            return Playlist.objects.filter(id__in=followed_playlist_ids)
        elif filter_type == 'liked':
            # Get ALL playlists the user likes, not just owned/collaborated ones
            liked_playlist_ids = UserPlaylistLike.objects.filter(
                user_id=self.request.user.id
            ).values_list('playlist_id', flat=True)
            return Playlist.objects.filter(id__in=liked_playlist_ids)

        # Default behavior: Get playlists owned by user OR playlists where user is a collaborator
        owned_playlists = Playlist.objects.filter(owner_id=self.request.user.id)

        # Get collaborative playlists via service call
        try:
            auth_header = self.request.META.get('HTTP_AUTHORIZATION', '')
            collaborative_playlist_ids = CollaborationServiceClient.get_user_collaborations(
                self.request.user.id,
                auth_header
            )
            collaborated_playlists = Playlist.objects.filter(id__in=collaborative_playlist_ids)
        except Exception:
            # If collaboration service fails, just use owned playlists
            collaborated_playlists = Playlist.objects.none()

        # Combine both querysets and remove duplicates
        qs = owned_playlists | collaborated_playlists

        # Enhanced filtering
        visibility = self.request.query_params.get('visibility')
        if visibility in ['public', 'private']:
            qs = qs.filter(visibility=visibility)

        playlist_type = self.request.query_params.get('type')
        if playlist_type in ['solo', 'collaborative']:
            qs = qs.filter(playlist_type=playlist_type)

        # Filter by system-generated vs user-created
        is_system_generated = self.request.query_params.get('is_system_generated')
        if is_system_generated in ['true', 'false']:
            qs = qs.filter(is_system_generated=(is_system_generated == 'true'))

        # Search in name and description
        query = self.request.query_params.get('q')
        if query:
            qs = qs.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )

        # Date range filters
        created_after = self.request.query_params.get('created_after')
        if created_after:
            try:
                qs = qs.filter(created_at__gte=created_after)
            except ValueError:
                pass  # Invalid date format, ignore filter

        created_before = self.request.query_params.get('created_before')
        if created_before:
            try:
                qs = qs.filter(created_at__lte=created_before)
            except ValueError:
                pass  # Invalid date format, ignore filter

        # Exclude archived by default
        if self.request.query_params.get('include_archived') != 'true':
            qs = qs.exclude(archived_by__user_id=self.request.user.id)

        # Sorting
        sort = self.request.query_params.get('sort', 'updated_at')
        order = self.request.query_params.get('order', 'desc')
        order_field = PLAYLIST_SORT_MAP.get(sort, 'updated_at')

        # Handle track_count sorting with annotation
        if sort == 'track_count':
            qs = qs.annotate(track_count=Count('tracks'))

        if order == 'desc':
            order_field = '-' + order_field

        qs = qs.order_by(order_field)

        # Post-filtering by track count (after annotation)
        min_tracks = self.request.query_params.get('min_tracks')
        if min_tracks:
            try:
                min_tracks_int = int(min_tracks)
                if sort == 'track_count':
                    qs = [p for p in qs if p.track_count >= min_tracks_int]
                else:
                    # Annotate track_count if not already done
                    qs = qs.annotate(track_count=Count('tracks'))
                    qs = qs.filter(track_count__gte=min_tracks_int)
            except ValueError:
                pass  # Invalid integer, ignore filter

        max_tracks = self.request.query_params.get('max_tracks')
        if max_tracks:
            try:
                max_tracks_int = int(max_tracks)
                if sort == 'track_count' and not isinstance(qs, list):
                    qs = [p for p in qs if p.track_count <= max_tracks_int]
                elif not isinstance(qs, list):
                    # Annotate track_count if not already done
                    qs = qs.annotate(track_count=Count('tracks'))
                    qs = qs.filter(track_count__lte=max_tracks_int)
            except ValueError:
                pass  # Invalid integer, ignore filter

        return qs

    def perform_create(self, serializer):
        playlist = serializer.save(owner_id=self.request.user.id)
        return playlist

    @extend_schema(
        tags=["Playlists"],
        summary="List playlists",
        description="""Returns your playlists with powerful filtering and sorting options.

**Default behavior:** Shows playlists you own + collaborative playlists
**Special filters:**
- `filter=followed` - All playlists you follow (not just owned)
- `filter=liked` - All playlists you liked

**Regular filters:** visibility (public/private), type (solo/collaborative),
is_system_generated, search in name/description, date ranges, track count ranges

**Sorting:** name, created_at, updated_at, track_count (asc/desc)

Archived playlists are excluded by default. Use `include_archived=true` to include them.""",
        parameters=[
            OpenApiParameter(
                name='filter',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Special filter: "followed" or "liked"',
                required=False,
                enum=['followed', 'liked']
            ),
            OpenApiParameter(
                name='visibility',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by visibility',
                required=False,
                enum=['public', 'private']
            ),
            OpenApiParameter(
                name='type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by playlist type',
                required=False,
                enum=['solo', 'collaborative']
            ),
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search in name and description',
                required=False
            ),
            OpenApiParameter(
                name='sort',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort field',
                required=False,
                enum=['name', 'created_at', 'updated_at', 'track_count']
            ),
            OpenApiParameter(
                name='order',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort order',
                required=False,
                enum=['asc', 'desc']
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of results to return',
                required=False
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Offset for pagination',
                required=False
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': True},
                    'message': {'type': 'string', 'example': 'Playlists retrieved successfully'},
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer', 'example': 123},
                                'name': {'type': 'string', 'example': 'Classic Rock'},
                                'description': {'type': 'string', 'example': 'Best rock songs of all time'},
                                'owner_id': {'type': 'integer', 'example': 1},
                                'visibility': {'type': 'string', 'enum': ['public', 'private', 'collaborative'], 'example': 'public'},
                                'playlist_type': {'type': 'string', 'enum': ['solo', 'collaborative'], 'example': 'solo'},
                                'track_count': {'type': 'integer', 'example': 150},
                                'created_at': {'type': 'string', 'format': 'date-time', 'example': '2026-04-01T10:00:00Z'},
                                'updated_at': {'type': 'string', 'format': 'date-time', 'example': '2026-04-07T15:30:00Z'}
                            }
                        }
                    }
                }
            }
        }
    )
    def list(self, request, *args, **kwargs):
        """Override to wrap response in SuccessResponse format"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse(data=serializer.data, message='Playlists retrieved successfully')

    def get_object(self):
        """
        Override to bypass filtered queryset for individual playlist retrieval.
        This allows us to check authorization on ALL playlists, not just
        the ones in the filtered queryset.
        """
        queryset = Playlist.objects.all()
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(
        tags=["Playlists"],
        summary="Get playlist details",
        description="Get detailed information about a specific playlist. Requires access: owner, collaborator, or public playlist. Private playlists require ownership or collaboration.",
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'public_playlist': {
                        'summary': 'Public playlist (anyone can view)',
                        'value': {
                            'success': True,
                            'message': 'Playlist retrieved successfully',
                            'data': {
                                'id': 123,
                                'name': 'Classic Rock Anthems',
                                'description': 'The greatest rock songs ever made',
                                'owner_id': 45,
                                'visibility': 'public',
                                'playlist_type': 'solo',
                                'track_count': 200,
                                'followers_count': 1234,
                                'likes_count': 567,
                                'created_at': '2026-01-15T10:00:00Z',
                                'updated_at': '2026-04-07T14:30:00Z'
                            }
                        }
                    },
                    'private_playlist': {
                        'summary': 'Your private playlist',
                        'value': {
                            'success': True,
                            'message': 'Playlist retrieved successfully',
                            'data': {
                                'id': 789,
                                'name': 'Private Study Mix',
                                'description': 'Songs for focused studying',
                                'owner_id': 1,
                                'visibility': 'private',
                                'playlist_type': 'solo',
                                'track_count': 25,
                                'followers_count': 0,
                                'likes_count': 0,
                                'created_at': '2026-03-01T08:00:00Z',
                                'updated_at': '2026-04-06T11:20:00Z'
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
    def retrieve(self, request, *args, **kwargs):
        """Override to wrap response in SuccessResponse format and check access"""
        instance = self.get_object()

        # Check if user can access this playlist (owner, collaborator, or public)
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not user_can_access_playlist(instance, request.user.id, auth_header):
            return ForbiddenResponse(message='Not authorized to access this playlist')

        serializer = self.get_serializer(instance)
        return SuccessResponse(data=serializer.data, message='Playlist retrieved successfully')

    @extend_schema(
        tags=["Playlists"],
        summary="Create playlist",
        description="Create a new playlist. You become the owner. Collaborative playlists can be shared with others for joint management.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Playlist name (max 255 characters)',
                        'maxLength': 255,
                        'example': 'My Awesome Playlist'
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Playlist description (optional, max 1000 characters)',
                        'maxLength': 1000,
                        'example': 'A collection of my favorite songs'
                    },
                    'visibility': {
                        'type': 'string',
                        'enum': ['public', 'private'],
                        'description': 'Who can view this playlist',
                        'example': 'public'
                    },
                    'playlist_type': {
                        'type': 'string',
                        'enum': ['solo', 'collaborative'],
                        'description': 'Playlist type: solo (only you) or collaborative (others can contribute)',
                        'example': 'solo'
                    },
                    'is_system_generated': {
                        'type': 'boolean',
                        'description': 'Mark as system-generated (for auto-created playlists)',
                        'example': False
                    }
                },
                'required': ['name']
            }
        },
        examples=[
            OpenApiExample(
                'Create public playlist',
                description='Create a public playlist that anyone can view',
                value={
                    'name': 'Summer Vibes 2026',
                    'description': 'Perfect songs for summer',
                    'visibility': 'public',
                    'playlist_type': 'solo'
                }
            ),
            OpenApiExample(
                'Create collaborative playlist',
                description='Create a playlist others can help manage',
                value={
                    'name': 'Team Workout Mix',
                    'description': 'Songs we can exercise to',
                    'visibility': 'private',
                    'playlist_type': 'collaborative'
                }
            )
        ],
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': True},
                    'message': {'type': 'string', 'example': 'Playlist created successfully'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer', 'example': 456},
                            'name': {'type': 'string', 'example': 'Summer Vibes 2026'},
                            'description': {'type': 'string', 'example': 'Perfect songs for summer'},
                            'owner_id': {'type': 'integer', 'example': 1},
                            'visibility': {'type': 'string', 'example': 'public', 'enum': ['public', 'private', 'collaborative']},
                            'playlist_type': {'type': 'string', 'example': 'solo', 'enum': ['solo', 'collaborative']},
                            'track_count': {'type': 'integer', 'example': 0},
                            'created_at': {'type': 'string', 'format': 'date-time', 'example': '2026-04-07T16:00:00Z'}
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_name': {
                        'summary': 'Name not provided',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {'name': ['This field is required.']}
                        }
                    },
                    'invalid_visibility': {
                        'summary': 'Invalid visibility value',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {'visibility': ['"invalid" is not a valid choice.']}
                        }
                    }
                }
            }
        }
    )
    def create(self, request, *args, **kwargs):
        """Override to wrap response in SuccessResponse format"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return SuccessResponse(data=serializer.data, message='Playlist created successfully', status_code=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Playlists"],
        summary="Update playlist",
        description="Update playlist details. Only owner can update playlist metadata. Collaborators can update tracks. All fields optional - partial updates supported.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'New name (optional)',
                        'maxLength': 255,
                        'example': 'Updated Playlist Name'
                    },
                    'description': {
                        'type': 'string',
                        'description': 'New description (optional)',
                        'maxLength': 1000,
                        'example': 'Updated description'
                    },
                    'visibility': {
                        'type': 'string',
                        'enum': ['public', 'private'],
                        'description': 'New visibility setting',
                        'example': 'public'
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Update name and visibility',
                description='Update playlist name and make it public',
                value={
                    'name': 'Renamed Playlist',
                    'visibility': 'public'
                }
            ),
            OpenApiExample(
                'Update description only',
                description='Update only the description field',
                value={
                    'description': 'New description for this playlist'
                }
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': True},
                    'message': {'type': 'string', 'example': 'Playlist updated successfully'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer', 'example': 123},
                            'name': {'type': 'string', 'example': 'Renamed Playlist'},
                            'updated_at': {'type': 'string', 'format': 'date-time', 'example': '2026-04-07T17:00:00Z'}
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'invalid_visibility': {
                        'summary': 'Invalid visibility value',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {'visibility': ['"invalid" is not a valid choice.']}
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Not authorized to update this playlist'
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
    def update(self, request, *args, **kwargs):
        playlist = self.get_object()
        if not user_can_access_playlist(playlist, request.user.id, request.META.get('HTTP_AUTHORIZATION', '')):
            return ForbiddenResponse(message='Not authorized')
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(playlist, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return SuccessResponse(data=serializer.data, message='Playlist updated successfully')

    @extend_schema(
        tags=["Playlists"],
        summary="Delete playlist",
        description="Permanently delete a playlist. Only the owner can delete. This action cannot be undone - all tracks, comments, and metadata will be permanently removed.",
        responses={
            200: {
                'type': 'object',
                'example': {
                    'success': True,
                    'message': 'Playlist deleted successfully'
                }
            },
            403: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Only the playlist owner can delete'
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
    def destroy(self, request, *args, **kwargs):
        playlist = self.get_object()
        if not user_can_access_playlist(playlist, request.user.id, request.META.get('HTTP_AUTHORIZATION', '')):
            return ForbiddenResponse(message='Not authorized')
        self.perform_destroy(playlist)
        return SuccessResponse(data=None, message='Playlist deleted successfully')


class PlaylistStatsView(APIView):
    """
    GET /api/playlists/{id}/stats/

    Returns comprehensive statistics for a playlist:
    - Track counts and durations
    - Genre breakdown
    - Artist/album uniqueness
    - Collaborator count
    - Follow/like status
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Get playlist statistics",
        description="Returns comprehensive statistics for a playlist including track counts, total duration, genre breakdown, unique artist/album counts, collaborator count, follower/like counts, and the current user's follow/like status. This endpoint is ideal for playlist overview pages, analytics dashboards, and insights features.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist to get statistics for',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'playlist_stats': {
                        'summary': 'Playlist statistics retrieved successfully',
                        'value': {
                            'success': True,
                            'message': 'Statistics retrieved successfully',
                            'data': {
                                'id': 123,
                                'name': 'My Awesome Playlist',
                                'total_tracks': 50,
                                'total_duration_seconds': 10800,
                                'total_duration_formatted': '3:00:00',
                                'genres': ['Rock', 'Pop', 'Electronic'],
                                'unique_artists': 35,
                                'unique_albums': 42,
                                'collaborator_count': 3,
                                'follower_count': 125,
                                'like_count': 89,
                                'is_followed': True,
                                'is_liked': False
                            }
                        }
                    },
                    'empty_playlist': {
                        'summary': 'Statistics for empty playlist',
                        'value': {
                            'success': True,
                            'message': 'Statistics retrieved successfully',
                            'data': {
                                'id': 456,
                                'name': 'Empty Playlist',
                                'total_tracks': 0,
                                'total_duration_seconds': 0,
                                'total_duration_formatted': '0:00:00',
                                'genres': [],
                                'unique_artists': 0,
                                'unique_albums': 0,
                                'collaborator_count': 0,
                                'follower_count': 5,
                                'like_count': 2,
                                'is_followed': False,
                                'is_liked': True
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'User does not have access to playlist',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to view this playlist'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'playlist_not_found': {
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )
    def get(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Check authorization
        if not user_can_access_playlist(playlist, request.user.id, request.META.get('HTTP_AUTHORIZATION', '')):
            return ForbiddenResponse(message='Not authorized to view this playlist')

        # Track statistics
        tracks = Track.objects.filter(playlist=playlist).select_related(
            'song__artist', 'song__album'
        )

        total_tracks = tracks.count()
        total_duration = tracks.aggregate(
            total=Sum('song__duration_seconds')
        )['total'] or 0

        # Genre breakdown
        genres = list(
            tracks.exclude(song__genre='')
            .values_list('song__genre', flat=True)
            .distinct()
        )

        # Unique artists and albums
        unique_artists = tracks.values('song__artist').distinct().count()
        unique_albums = tracks.values('song__album').distinct().count()

        # Last track added
        last_track = tracks.order_by('-added_at').first()
        last_track_added = last_track.added_at if last_track else None

        # Collaborator count from collabapp via service client
        try:
            from utils.service_clients import CollaborationServiceClient
            auth_token = request.headers.get('Authorization', '')
            collaborator_count = CollaborationServiceClient.get_collaborator_count(
                playlist.id,
                auth_token
            )
        except Exception:
            # Fallback if service communication fails
            collaborator_count = 0

        # Follow/like status
        is_followed = UserPlaylistFollow.objects.filter(
            user_id=request.user.id,
            playlist=playlist
        ).exists()

        is_liked = UserPlaylistLike.objects.filter(
            user_id=request.user.id,
            playlist=playlist
        ).exists()

        # Follower and like counts
        follower_count = UserPlaylistFollow.objects.filter(playlist=playlist).count()
        like_count = UserPlaylistLike.objects.filter(playlist=playlist).count()

        # Format duration
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        seconds = total_duration % 60
        duration_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"

        return SuccessResponse(
            data={
                'id': playlist.id,
                'name': playlist.name,
                'total_tracks': total_tracks,
                'total_duration_seconds': total_duration,
                'total_duration_formatted': duration_formatted,
                'genres': genres,
                'unique_artists': unique_artists,
                'unique_albums': unique_albums,
                'last_track_added': last_track_added,
                'collaborator_count': collaborator_count,
                'follower_count': follower_count,
                'like_count': like_count,
                'is_followed': is_followed,
                'is_liked': is_liked,
                'owner_id': playlist.owner_id,
                'cover_url': playlist.cover_url
            },
            message='Playlist statistics retrieved successfully'
        )


class FeaturedPlaylistsView(APIView):
    """
    GET /api/playlists/featured/

    Returns featured/curated playlists:
    - Public playlists only
    - Ordered by track count or creation date
    - Optional genre filter
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Get featured playlists",
        description="Returns featured and curated public playlists, ordered by track count (most tracks first). These playlists are selected based on quality, popularity, and editorial curation. Supports optional genre filtering to discover featured playlists in specific music categories. Ideal for homepage discovery, browse features, and music exploration.",
        parameters=[
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter playlists by primary genre (optional, case-insensitive)',
                required=False,
                example='Rock'
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of playlists to return (default: 20, maximum: 100)',
                required=False,
                example=20
            )
        ],
        examples=[
            OpenApiExample(
                'Get featured playlists',
                description='Retrieve all featured playlists',
                value={'limit': 20}
            ),
            OpenApiExample(
                'Featured by genre',
                description='Get featured Rock playlists',
                value={'genre': 'Rock', 'limit': 30}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'featured_playlists': {
                        'summary': 'Featured playlists retrieved successfully',
                        'value': {
                            'success': True,
                            'message': 'Found 15 featured playlists',
                            'data': [
                                {
                                    'id': 101,
                                    'name': 'Top Hits 2026',
                                    'description': 'The biggest songs of 2026',
                                    'owner_id': 1,
                                    'visibility': 'public',
                                    'playlist_type': 'solo',
                                    'track_count': 100,
                                    'cover_url': 'https://example.com/covers/top-hits.jpg'
                                },
                                {
                                    'id': 102,
                                    'name': 'Rock Classics',
                                    'description': 'Essential rock anthems',
                                    'owner_id': 5,
                                    'visibility': 'public',
                                    'playlist_type': 'solo',
                                    'track_count': 75,
                                    'cover_url': 'https://example.com/covers/rock.jpg'
                                }
                            ]
                        }
                    },
                    'no_featured': {
                        'summary': 'No featured playlists available',
                        'value': {
                            'success': True,
                            'message': 'Found 0 featured playlists',
                            'data': []
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        # For now, return public playlists ordered by track count
        # In future, can add is_featured flag to Playlist model
        qs = Playlist.objects.filter(visibility='public').annotate(
            track_count=Count('tracks')
        ).order_by('-track_count', '-created_at')

        # Optional genre filter
        genre = self.request.query_params.get('genre')
        if genre:
            # Filter playlists that have songs in this genre
            from trackapp.models import Track
            playlist_ids_with_genre = Track.objects.filter(
                song__genre=genre
            ).values_list('playlist_id', flat=True).distinct()
            qs = qs.filter(id__in=playlist_ids_with_genre)

        # Limit results
        limit = int(self.request.query_params.get('limit', 20))
        qs = qs[:limit]

        return SuccessResponse(
            data=PlaylistSerializer(qs, many=True).data,
            message='Playlists retrieved successfully'
        )


class DuplicatePlaylistView(APIView):
    """
    POST /api/playlists/{id}/duplicate/

    Duplicate a playlist with all its tracks.
    Creates a new playlist with name "{original_name} (Copy)"
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Duplicate a playlist",
        description="Creates a complete copy of a playlist with all its tracks. The duplicate is always created as a private playlist owned by the authenticated user. You can customize the name, choose whether to include tracks, and reset track positions. **Note:** You can only duplicate your own playlists or public playlists. Collaborative playlists cannot be duplicated.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist to duplicate',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Custom name for the duplicate playlist (default: "{original_name} (Copy)")',
                        'maxLength': 255,
                        'example': 'My Workout Mix 2'
                    },
                    'include_tracks': {
                        'type': 'boolean',
                        'description': 'Whether to copy all tracks from the original playlist (default: true)',
                        'default': True,
                        'example': True
                    },
                    'reset_position': {
                        'type': 'boolean',
                        'description': 'Whether to reset track positions to 0, 1, 2... instead of preserving original positions (default: false)',
                        'default': False,
                        'example': False
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Duplicate with defaults',
                description='Create a duplicate with default settings (all tracks, original positions)',
                value={}
            ),
            OpenApiExample(
                'Duplicate with custom name',
                description='Create a duplicate with a custom name',
                value={'name': 'My Summer Playlist 2026'}
            ),
            OpenApiExample(
                'Duplicate without tracks',
                description='Create an empty playlist with same metadata',
                value={'include_tracks': False}
            ),
            OpenApiExample(
                'Duplicate and reset positions',
                description='Create a duplicate with renumbered track positions',
                value={'reset_position': True}
            )
        ],
        responses={
            201: {
                'type': 'object',
                'examples': {
                    'duplicate_success': {
                        'summary': 'Playlist duplicated successfully',
                        'value': {
                            'success': True,
                            'message': 'Playlist duplicated successfully',
                            'data': {
                                'id': 456,
                                'name': 'My Awesome Playlist (Copy)',
                                'description': 'Copied from original',
                                'owner_id': 1,
                                'visibility': 'private',
                                'playlist_type': 'solo',
                                'track_count': 25,
                                'cover_url': 'https://example.com/cover.jpg'
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Cannot duplicate private playlist owned by another user',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to duplicate this playlist'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'playlist_not_found': {
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )
    def post(self, request, playlist_id):
        try:
            source = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization check - can only duplicate own playlists or public playlists
        if source.owner_id != request.user.id and source.visibility != 'public':
            return ForbiddenResponse(message='Not authorized to duplicate this playlist')

        # Get request body for optional parameters
        data = request.data
        name = data.get('name', f"{source.name} (Copy)")
        include_tracks = data.get('include_tracks', True)
        reset_position = data.get('reset_position', False)

        # Create duplicate playlist
        new_playlist = Playlist.objects.create(
            owner_id=request.user.id,
            name=name,
            description=source.description,
            visibility='private',  # Duplicates are always private
            playlist_type='solo',  # Duplicates are always solo
            max_songs=source.max_songs,
            cover_url=source.cover_url
        )

        # Copy tracks if requested
        if include_tracks:
            tracks = Track.objects.filter(playlist=source).select_related('song')
            new_tracks = []
            for index, track in enumerate(tracks):
                new_tracks.append(Track(
                    playlist=new_playlist,
                    song=track.song,
                    added_by_id=request.user.id,
                    position=index if not reset_position else track.position
                ))

            if new_tracks:
                Track.objects.bulk_create(new_tracks)

        return SuccessResponse(
            data=PlaylistSerializer(new_playlist).data,
            message='Playlist duplicated successfully',
            status_code=201
        )


class BatchDeleteView(APIView):
    """
    DELETE /api/playlists/batch-delete/

    Delete multiple playlists at once.
    Body: {"playlist_ids": [1, 2, 3]}
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Batch delete playlists",
        description="Delete multiple playlists at once in a single request. Only playlists owned by the authenticated user will be deleted - any playlist IDs owned by other users are silently ignored. Playlists are permanently deleted and cannot be recovered. Use with caution. Ideal for cleanup operations and bulk management.",
        request={
            'application/json': {
                'type': 'object',
                'required': ['playlist_ids'],
                'properties': {
                    'playlist_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'List of playlist IDs to delete. Only playlists you own will be deleted.',
                        'minItems': 1,
                        'example': [123, 456, 789]
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Delete multiple playlists',
                description='Delete multiple playlists at once',
                value={'playlist_ids': [123, 456, 789]}
            ),
            OpenApiExample(
                'Delete single playlist',
                description='Delete one playlist (alternative to DELETE /api/playlists/{id}/)',
                value={'playlist_ids': [123]}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'deletion_success': {
                        'summary': 'Playlists deleted successfully',
                        'value': {
                            'success': True,
                            'message': 'Deleted 3 playlists successfully',
                            'data': {
                                'deleted_count': 3,
                                'deleted_ids': [123, 456, 789],
                                'skipped_ids': []
                            }
                        }
                    },
                    'partial_deletion': {
                        'summary': 'Some playlists deleted, some skipped (not owned)',
                        'value': {
                            'success': True,
                            'message': 'Deleted 2 of 4 playlists',
                            'data': {
                                'deleted_count': 2,
                                'deleted_ids': [123, 456],
                                'skipped_ids': [789, 999]
                            }
                        }
                    },
                    'none_deleted': {
                        'summary': 'No playlists owned by user',
                        'value': {
                            'success': True,
                            'message': 'Deleted 0 playlists',
                            'data': {
                                'deleted_count': 0,
                                'deleted_ids': [],
                                'skipped_ids': [123, 456]
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_playlist_ids': {
                        'summary': 'playlist_ids field not provided',
                        'value': {
                            'success': False,
                            'message': 'playlist_ids required',
                            'errors': {
                                'playlist_ids': ['This field is required.']
                            }
                        }
                    },
                    'empty_array': {
                        'summary': 'playlist_ids array is empty',
                        'value': {
                            'success': False,
                            'message': 'At least one playlist ID must be provided'
                        }
                    }
                }
            }
        }
    )
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'deleted': {'type': 'integer'},
                            'not_found': {'type': 'integer'},
                            'not_authorized': {'type': 'integer'}
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'errors': {'type': 'object'}
                }
            }
        }
    )
    def delete(self, request):
        playlist_ids = request.data.get('playlist_ids', [])

        if not playlist_ids:
            return ValidationErrorResponse(
                errors={'playlist_ids': 'This field is required'},
                message='playlist_ids is required'
            )

        if not isinstance(playlist_ids, list):
            return ValidationErrorResponse(
                errors={'playlist_ids': 'Must be a list'},
                message='playlist_ids must be a list'
            )

        # Delete only user's own playlists
        deleted, not_found, not_authorized = 0, 0, 0

        for playlist_id in playlist_ids:
            try:
                playlist = Playlist.objects.get(id=playlist_id)
                if playlist.owner_id == request.user.id:
                    playlist.delete()
                    deleted += 1
                else:
                    not_authorized += 1
            except Playlist.DoesNotExist:
                not_found += 1

        status_code = status.HTTP_200_OK if deleted > 0 else status.HTTP_202_ACCEPTED
        return SuccessResponse(
            data={
                'deleted': deleted,
                'not_found': not_found,
                'not_authorized': not_authorized
            },
            message=f'Batch delete completed: {deleted} deleted',
            status_code=status_code
        )


class BatchUpdateView(APIView):
    """
    PATCH /api/playlists/batch-update/

    Update multiple playlists at once.
    Body: {"playlist_ids": [1, 2], "updates": {"visibility": "private"}}
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Batch update playlists",
        description="Update multiple playlists at once with the same field values. Only playlists owned by the authenticated user will be updated - any playlist IDs owned by other users are silently ignored. All specified playlists receive the same updates. Useful for bulk operations like making multiple playlists private or updating descriptions.",
        request={
            'application/json': {
                'type': 'object',
                'required': ['playlist_ids', 'updates'],
                'properties': {
                    'playlist_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'List of playlist IDs to update. Only playlists you own will be updated.',
                        'minItems': 1,
                        'example': [123, 456, 789]
                    },
                    'updates': {
                        'type': 'object',
                        'description': 'Field values to apply to all specified playlists. Any valid playlist field can be updated.',
                        'properties': {
                            'name': {
                                'type': 'string',
                                'description': 'New playlist name',
                                'maxLength': 255,
                                'example': 'Updated Playlist Name'
                            },
                            'description': {
                                'type': 'string',
                                'description': 'New playlist description',
                                'maxLength': 1000,
                                'example': 'Updated description'
                            },
                            'visibility': {
                                'type': 'string',
                                'enum': ['public', 'private'],
                                'description': 'New visibility level',
                                'example': 'private'
                            }
                        }
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Make playlists private',
                description='Update visibility of multiple playlists to private',
                value={
                    'playlist_ids': [123, 456, 789],
                    'updates': {'visibility': 'private'}
                }
            ),
            OpenApiExample(
                'Update descriptions',
                description='Set the same description for multiple playlists',
                value={
                    'playlist_ids': [123, 456],
                    'updates': {'description': 'My favorite songs'}
                }
            ),
            OpenApiExample(
                'Update name and visibility',
                description='Update multiple fields at once',
                value={
                    'playlist_ids': [123],
                    'updates': {
                        'name': 'New Name',
                        'visibility': 'public'
                    }
                }
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'update_success': {
                        'summary': 'Playlists updated successfully',
                        'value': {
                            'success': True,
                            'message': 'Updated 3 playlists',
                            'data': {
                                'updated': 3,
                                'not_found': 0,
                                'not_authorized': 0
                            }
                        }
                    },
                    'partial_update': {
                        'summary': 'Some playlists updated, some skipped',
                        'value': {
                            'success': True,
                            'message': 'Updated 2 of 4 playlists',
                            'data': {
                                'updated': 2,
                                'not_found': 1,
                                'not_authorized': 1
                            }
                        }
                    },
                    'none_updated': {
                        'summary': 'No playlists owned by user',
                        'value': {
                            'success': True,
                            'message': 'Updated 0 playlists',
                            'data': {
                                'updated': 0,
                                'not_found': 2,
                                'not_authorized': 2
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_playlist_ids': {
                        'summary': 'playlist_ids field not provided',
                        'value': {
                            'success': False,
                            'message': 'playlist_ids is required',
                            'errors': {
                                'playlist_ids': ['This field is required.']
                            }
                        }
                    },
                    'missing_updates': {
                        'summary': 'updates field not provided',
                        'value': {
                            'success': False,
                            'message': 'updates field is required',
                            'errors': {
                                'updates': ['This field is required.']
                            }
                        }
                    },
                    'empty_updates': {
                        'summary': 'updates object is empty',
                        'value': {
                            'success': False,
                            'message': 'updates field cannot be empty'
                        }
                    }
                }
            }
        }
    )
    def patch(self, request):
        playlist_ids = request.data.get('playlist_ids', [])
        updates = request.data.get('updates', {})

        if not playlist_ids:
            return ValidationErrorResponse(
                errors={'playlist_ids': 'This field is required'},
                message='playlist_ids is required'
            )

        if not updates:
            return ValidationErrorResponse(
                errors={'updates': 'This field is required'},
                message='updates field is required'
            )

        if not isinstance(playlist_ids, list):
            return ValidationErrorResponse(
                errors={'playlist_ids': 'Must be a list'},
                message='playlist_ids must be a list'
            )

        # Update only user's own playlists
        updated, not_found, not_authorized = 0, 0, 0

        for playlist_id in playlist_ids:
            try:
                playlist = Playlist.objects.get(id=playlist_id)
                if playlist.owner_id == request.user.id:
                    # Apply updates
                    for field, value in updates.items():
                        if hasattr(playlist, field):
                            setattr(playlist, field, value)
                    playlist.save()
                    updated += 1
                else:
                    not_authorized += 1
            except Playlist.DoesNotExist:
                not_found += 1

        status_code = status.HTTP_200_OK if updated > 0 else status.HTTP_202_ACCEPTED
        return SuccessResponse(
            data={
                'updated': updated,
                'not_found': not_found,
                'not_authorized': not_authorized
            },
            message=f'Batch update completed: {updated} updated',
            status_code=status_code
        )


class CoverUploadView(APIView):
    """
    POST /api/playlists/{id}/cover/

    Upload a cover image for a playlist.
    Currently accepts cover_url as a string (for Supabase URLs or external URLs).
    Future enhancement: Accept multipart file upload.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Upload playlist cover",
        description="Updates or sets the cover image for a playlist by providing an image URL. Only the playlist owner can change the cover image. The URL must be a valid HTTP/HTTPS URL pointing to an image. This endpoint currently accepts URLs (e.g., from Supabase storage, CDN, or external image hosting). **Note:** Cover images are displayed in playlist cards and playlist detail pages.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist to update the cover for',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'required': ['cover_url'],
                'properties': {
                    'cover_url': {
                        'type': 'string',
                        'description': 'URL of the cover image. Must start with http:// or https://',
                        'maxLength': 500,
                        'example': 'https://example.com/covers/my-playlist.jpg'
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Set cover image',
                description='Upload a cover image for the playlist',
                value={'cover_url': 'https://example.com/images/playlist-cover.jpg'}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'cover_updated': {
                        'summary': 'Cover image updated successfully',
                        'value': {
                            'success': True,
                            'message': 'Cover image updated successfully',
                            'data': {
                                'id': 123,
                                'name': 'My Playlist',
                                'description': 'Description',
                                'owner_id': 1,
                                'visibility': 'public',
                                'playlist_type': 'solo',
                                'track_count': 25,
                                'cover_url': 'https://example.com/images/playlist-cover.jpg'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_cover_url': {
                        'summary': 'cover_url field not provided',
                        'value': {
                            'success': False,
                            'message': 'cover_url is required',
                            'errors': {
                                'cover_url': ['This field is required.']
                            }
                        }
                    },
                    'invalid_url': {
                        'summary': 'URL does not start with http:// or https://',
                        'value': {
                            'success': False,
                            'message': 'Invalid URL format',
                            'errors': {
                                'cover_url': ['URL must start with http:// or https://']
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_owner': {
                        'summary': 'Only the playlist owner can change the cover',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to modify this playlist'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'playlist_not_found': {
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )
    def post(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized to modify this playlist')

        # For now, we accept cover_url in the request body
        # Future enhancement: Handle multipart file upload
        cover_url = request.data.get('cover_url')

        if not cover_url:
            return ValidationErrorResponse(
                errors={'cover_url': 'This field is required'},
                message='cover_url is required'
            )

        # Validate URL format
        if not cover_url.startswith(('http://', 'https://')):
            return ValidationErrorResponse(
                errors={'cover_url': 'Must be a valid HTTP(S) URL'},
                message='Invalid cover URL format'
            )

        # Update cover URL
        playlist.cover_url = cover_url
        playlist.save()

        return SuccessResponse(
            data=PlaylistSerializer(playlist).data,
            message='Cover image updated successfully'
        )


class CoverDeleteView(APIView):
    """
    DELETE /api/playlists/{id}/cover/

    Remove the cover image from a playlist.
    Sets cover_url back to empty string (will show gradient placeholder).
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Remove playlist cover",
        description="Removes the cover image from a playlist, setting the cover_url back to null/empty. The playlist will then display the default gradient placeholder. This operation is irreversible - you will need to re-upload the cover image if you want to restore it. Only the playlist owner can remove the cover image.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist to remove the cover from',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'cover_removed': {
                        'summary': 'Cover image removed successfully',
                        'value': {
                            'success': True,
                            'message': 'Cover image removed successfully',
                            'data': {
                                'id': 123,
                                'name': 'My Playlist',
                                'description': 'Description',
                                'owner_id': 1,
                                'visibility': 'public',
                                'playlist_type': 'solo',
                                'track_count': 25,
                                'cover_url': None
                            }
                        }
                    },
                    'no_cover_to_remove': {
                        'summary': 'Playlist had no cover image (idempotent)',
                        'value': {
                            'success': True,
                            'message': 'Cover image removed successfully',
                            'data': {
                                'id': 456,
                                'name': 'Another Playlist',
                                'cover_url': None
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_owner': {
                        'summary': 'Only the playlist owner can remove the cover',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to modify this playlist'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'playlist_not_found': {
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )
                    'message': {'type': 'string'},
                    'data': PlaylistSerializer
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def delete(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized to modify this playlist')

        # Clear cover URL
        playlist.cover_url = ''
        playlist.save()

        return SuccessResponse(
            data=PlaylistSerializer(playlist).data,
            message='Cover image updated successfully'
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@extend_schema(
    tags=["Health"],
    summary="Playlist service health check",
    description="Check if the playlist service and database are healthy",
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
            data={'status': 'healthy', 'service': 'playlist', 'database': 'connected'},
            message='Service is healthy'
        )
    except Exception as e:
        return ServiceUnavailableResponse(
            message=f'Database connection failed: {str(e)}'
        )


class UserPlaylistsView(APIView):
    """
    GET /api/users/{id}/playlists/

    Returns playlists for a specific user:
    - If requesting own playlists: shows all (public + private + collaborative)
    - If requesting others' playlists: shows only public
    - Supports all filtering parameters from PlaylistViewSet
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Get user's playlists",
        description="Returns all playlists for a specific user with privacy-aware filtering. When requesting your own playlists, returns all playlists (public, private, and collaborative). When requesting another user's playlists, only returns public playlists. Supports filtering by visibility, type, and search queries. Ideal for profile pages and user playlist browsing.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to get playlists for',
                required=True,
                example=1
            ),
            OpenApiParameter(
                name='visibility',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by visibility level (public, private, collaborative)',
                required=False,
                enum=['public', 'private', 'collaborative'],
                example='public'
            ),
            OpenApiParameter(
                name='type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by playlist type',
                required=False,
                enum=['solo', 'collaborative'],
                example='solo'
            ),
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query for name and description',
                required=False,
                example='workout'
            ),
            OpenApiParameter(
                name='sort',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort field',
                required=False,
                enum=['name', 'created_at', 'updated_at', 'track_count'],
                example='created_at'
            ),
            OpenApiParameter(
                name='order',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort order (asc or desc)',
                required=False,
                enum=['asc', 'desc'],
                example='desc'
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of results to return',
                required=False,
                example=20
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of results to skip for pagination',
                required=False,
                example=0
            )
        ],
        examples=[
            OpenApiExample(
                'Get my playlists',
                description='Retrieve all your playlists (including private)',
                value={'user_id': 1}
            ),
            OpenApiExample(
                'Get public playlists',
                description="Retrieve another user's public playlists only",
                value={'user_id': 5, 'visibility': 'public'}
            ),
            OpenApiExample(
                'Search and filter',
                description='Search playlists with filters',
                value={
                    'user_id': 1,
                    'q': 'rock',
                    'type': 'solo',
                    'sort': 'name',
                    'order': 'asc'
                }
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'own_playlists': {
                        'summary': 'Your playlists (all types)',
                        'value': {
                            'success': True,
                            'message': 'Retrieved 5 playlists',
                            'data': [
                                {
                                    'id': 101,
                                    'name': 'My Private Playlist',
                                    'description': 'Private',
                                    'owner_id': 1,
                                    'visibility': 'private',
                                    'playlist_type': 'solo',
                                    'track_count': 25
                                },
                                {
                                    'id': 102,
                                    'name': 'Team Playlist',
                                    'description': 'Collaborative',
                                    'owner_id': 1,
                                    'visibility': 'public',
                                    'playlist_type': 'collaborative',
                                    'track_count': 50
                                }
                            ]
                        }
                    },
                    'other_users_public': {
                        'summary': 'Another user\'s public playlists only',
                        'value': {
                            'success': True,
                            'message': 'Retrieved 3 playlists',
                            'data': [
                                {
                                    'id': 201,
                                    'name': 'Public Playlist',
                                    'description': 'Public',
                                    'owner_id': 5,
                                    'visibility': 'public',
                                    'playlist_type': 'solo',
                                    'track_count': 30
                                }
                            ]
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'user_not_found': {
                        'summary': 'User ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'User not found'
                        }
                    }
                }
            }
        }
    )
            OpenApiParameter(
                name='type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by playlist type',
                required=False
            ),
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search in name and description',
                required=False
            ),
            OpenApiParameter(
                name='sort',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort field',
                required=False
            ),
            OpenApiParameter(
                name='order',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort order',
                required=False
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of results',
                required=False
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Offset for pagination',
                required=False
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'user_id': {'type': 'integer'},
                            'total': {'type': 'integer'},
                            'limit': {'type': 'integer'},
                            'offset': {'type': 'integer'},
                            'playlists': {
                                'type': 'array',
                                'items': PlaylistSerializer
                            }
                        }
                    }
                }
            }
        }
    )
    def get(self, request, user_id):
        # Helper function to apply common filters to a queryset
        def apply_filters(qs):
            # Privacy check: if not requesting own playlists, only show public
            if request.user.id != user_id:
                qs = qs.filter(visibility='public')

            # Visibility filter
            visibility = request.query_params.get('visibility')
            if visibility in ['public', 'private']:
                qs = qs.filter(visibility=visibility)

            # Type filter
            playlist_type = request.query_params.get('type')
            if playlist_type in ['solo', 'collaborative']:
                qs = qs.filter(playlist_type=playlist_type)

            # Filter by system-generated vs user-created
            is_system_generated = request.query_params.get('is_system_generated')
            if is_system_generated in ['true', 'false']:
                qs = qs.filter(is_system_generated=(is_system_generated == 'true'))

            # Search
            query = request.query_params.get('q')
            if query:
                qs = qs.filter(
                    Q(name__icontains=query) |
                    Q(description__icontains=query)
                )

            # Date range filters
            created_after = request.query_params.get('created_after')
            if created_after:
                try:
                    qs = qs.filter(created_at__gte=created_after)
                except ValueError:
                    pass

            created_before = request.query_params.get('created_before')
            if created_before:
                try:
                    qs = qs.filter(created_at__lte=created_before)
                except ValueError:
                    pass

            # Exclude archived by default (apply before union!)
            if request.query_params.get('include_archived') != 'true':
                qs = qs.exclude(archived_by__user_id=request.user.id)

            return qs

        # Get playlists owned by user and apply filters
        owned_playlists = apply_filters(Playlist.objects.filter(owner_id=user_id))

        # If requesting own playlists, also include collaborative playlists
        collaborative_playlists = Playlist.objects.none()
        if request.user.id == user_id:
            try:
                # Get collaborative playlist IDs using the collaboration service
                auth_header = request.META.get('HTTP_AUTHORIZATION', '')
                collaborative_playlist_ids = CollaborationServiceClient.get_user_collaborations(user_id, auth_header)

                if collaborative_playlist_ids:
                    # Apply same filters to collaborative playlists
                    collaborative_playlists = apply_filters(
                        Playlist.objects.filter(id__in=collaborative_playlist_ids)
                    )
            except Exception as e:
                logger = __import__('logging').getLogger(__name__)
                logger.error(f"Failed to fetch collaborative playlists for user {user_id}: {str(e)}")

        # Combine owned and collaborative playlists
        # Use union() but convert to list to avoid QuerySet limitations
        owned_ids = list(owned_playlists.values_list('id', flat=True))
        collab_ids = list(collaborative_playlists.values_list('id', flat=True))
        all_ids = list(set(owned_ids + collab_ids))

        # Fetch all playlists and apply additional sorting/pagination
        qs = Playlist.objects.filter(id__in=all_ids)

        # Sorting
        sort = request.query_params.get('sort', 'updated_at')
        order = request.query_params.get('order', 'desc')
        order_field = PLAYLIST_SORT_MAP.get(sort, 'updated_at')

        if sort == 'track_count':
            qs = qs.annotate(track_count=Count('tracks'))

        if order == 'desc':
            order_field = '-' + order_field

        qs = qs.order_by(order_field)

        # Pagination limit
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))

        total = qs.count()
        playlists = qs[offset:offset + limit]

        # Add a flag to indicate which playlists are collaborative
        playlists_data = []
        for playlist in playlists:
            playlist_dict = PlaylistSerializer(playlist).data
            # Mark if this is a collaborative playlist where user is not owner
            playlist_dict['is_collaborator'] = (playlist.owner_id != user_id and playlist.playlist_type == 'collaborative')
            playlists_data.append(playlist_dict)

        return SuccessResponse(
            data={
                'user_id': user_id,
                'total': total,
                'limit': limit,
                'offset': offset,
                'playlists': playlists_data
            },
            message=f'Retrieved {len(playlists)} playlists'
        )


class PlaylistFollowView(APIView):
    """
    POST /api/playlists/{id}/follow/ - Follow a playlist
    DELETE /api/playlists/{id}/follow/ - Unfollow a playlist
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Follow a playlist",
        description="Follow a playlist to receive updates and show it in your library. Owners and collaborators can follow their own playlists. Regular users can only follow public playlists. Following is idempotent.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to follow',
                required=True,
                example=123
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
                        'example': 'Playlist followed successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'followed_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-07T14:30:00Z',
                                'description': 'ISO 8601 timestamp when playlist was followed'
                            }
                        }
                    }
                }
            },
            200: {
                'type': 'object',
                'description': 'Returned when already following (idempotent)',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Already following this playlist'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'followed_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-06T09:15:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'private_playlist': {
                        'summary': 'Cannot follow private playlist',
                        'value': {
                            'success': False,
                            'message': 'Can only follow public playlists',
                            'errors': {
                                'operation': ['Can only follow public playlists']
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

        # Check if user is owner
        is_owner = playlist.owner_id == request.user.id

        # Check if user is collaborator via service client
        is_collaborator = False
        if not is_owner:
            from utils.service_clients import CollaborationServiceClient
            auth_header = request.headers.get('Authorization', '')

            try:
                # Use the service client to check if user is collaborator
                is_collaborator = CollaborationServiceClient.is_collaborator(
                    playlist_id=playlist_id,
                    user_id=request.user.id,
                    auth_token=auth_header
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to check collaborator status: {e}")
                # If service is unavailable, allow follow attempt (backend will validate)

        # Regular users (not owners or collaborators) can only follow public playlists
        if not is_owner and not is_collaborator and playlist.visibility != 'public':
            return ValidationErrorResponse(
                errors={'operation': 'Can only follow public playlists'},
                message='Can only follow public playlists'
            )

        # Create follow relationship (idempotent)
        follow, created = UserPlaylistFollow.objects.get_or_create(
            user_id=request.user.id,
            playlist=playlist
        )

        if not created:
            return SuccessResponse(
                data={'followed_at': follow.followed_at},
                message='Already following this playlist'
            )

        return SuccessResponse(
            data={'followed_at': follow.followed_at},
            message='Playlist followed successfully',
            status_code=201
        )

    @extend_schema(
        tags=["Playlists"],
        summary="Unfollow a playlist",
        description="Stop following a playlist. The playlist will be removed from your library. Idempotent - unfollowing an already unfollowed playlist returns success without error.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to unfollow',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'success': {
                        'summary': 'Successfully unfollowed',
                        'value': {
                            'success': True,
                            'message': 'Playlist unfollowed successfully'
                        }
                    },
                    'not_following': {
                        'summary': 'Playlist was not followed (idempotent)',
                        'value': {
                            'success': True,
                            'message': 'Not following this playlist'
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
    def delete(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Delete follow relationship
        deleted_count, _ = UserPlaylistFollow.objects.filter(
            user_id=request.user.id,
            playlist=playlist
        ).delete()

        if deleted_count == 0:
            return SuccessResponse(
                message='Not following this playlist'
            )

        return SuccessResponse(
            message='Playlist unfollowed successfully'
        )


class PlaylistLikeView(APIView):
    """
    POST /api/playlists/{id}/like/ - Like a playlist
    DELETE /api/playlists/{id}/like/ - Unlike a playlist
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Like a playlist",
        description="Likes a playlist. Cannot like your own playlists, only public playlists. Liking is idempotent - liking an already-liked playlist returns success without creating a duplicate.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to like',
                required=True,
                example=123
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
                        'example': 'Playlist liked successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'liked_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-07T12:30:45Z',
                                'description': 'ISO 8601 timestamp when playlist was liked'
                            }
                        }
                    }
                }
            },
            200: {
                'type': 'object',
                'description': 'Returned when playlist was already liked (idempotent operation)',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Already liked this playlist'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'liked_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-06T10:15:30Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'own_playlist': {
                        'summary': 'Cannot like own playlist',
                        'value': {
                            'success': False,
                            'message': 'Cannot like your own playlist',
                            'errors': {
                                'operation': ['Cannot like your own playlist']
                            }
                        }
                    },
                    'private_playlist': {
                        'summary': 'Cannot like private playlist',
                        'value': {
                            'success': False,
                            'message': 'Can only like public playlists',
                            'errors': {
                                'operation': ['Can only like public playlists']
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

        # Cannot like own playlists
        if playlist.owner_id == request.user.id:
            return ValidationErrorResponse(
                errors={'operation': 'Cannot like your own playlist'},
                message='Cannot like your own playlist'
            )

        # Can only like public playlists
        if playlist.visibility != 'public':
            return ValidationErrorResponse(
                errors={'operation': 'Can only like public playlists'},
                message='Can only like public playlists'
            )

        # Create like relationship (idempotent)
        like, created = UserPlaylistLike.objects.get_or_create(
            user_id=request.user.id,
            playlist=playlist
        )

        if not created:
            return SuccessResponse(
                data={'liked_at': like.liked_at},
                message='Already liked this playlist'
            )

        return SuccessResponse(
            data={'liked_at': like.liked_at},
            message='Playlist liked successfully',
            status_code=201
        )

    @extend_schema(
        tags=["Playlists"],
        summary="Unlike a playlist",
        description="Removes a playlist from your liked playlists. Idempotent - unliking an already unliked playlist returns success without error.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to unlike',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'success': {
                        'summary': 'Successfully unliked',
                        'value': {
                            'success': True,
                            'message': 'Playlist unliked successfully'
                        }
                    },
                    'not_liked': {
                        'summary': 'Playlist was not liked (idempotent)',
                        'value': {
                            'success': True,
                            'message': 'Not liking this playlist'
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
    def delete(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Delete like relationship
        deleted_count, _ = UserPlaylistLike.objects.filter(
            user_id=request.user.id,
            playlist=playlist
        ).delete()

        if deleted_count == 0:
            return SuccessResponse(
                message='Not liking this playlist'
            )

        return SuccessResponse(
            message='Playlist unliked successfully'
        )


class RecommendedPlaylistsView(APIView):
    """
    GET /api/playlists/recommended/

    Returns personalized playlist recommendations:
    - Based on user's liked playlists' genres
    - Based on user's followed playlists' genres
    - Excludes already liked/followed playlists
    - Ranked by genre overlap score
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Get personalized playlist recommendations",
        description="Returns personalized playlist recommendations based on your music taste. Analyzes genres from your liked and followed playlists to identify preferences, then suggests public playlists with similar genres that you haven't discovered yet. Playlists are ranked by genre overlap score - more genre matches means higher recommendation. If no preference data exists, falls back to featured playlists.",
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of recommendations to return (default: 20)',
                required=False,
                example=20
            )
        ],
        examples=[
            OpenApiExample(
                'Get recommendations',
                description='Retrieve personalized playlist suggestions',
                value={'limit': 20}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'personalized': {
                        'summary': 'Personalized recommendations based on taste',
                        'value': {
                            'success': True,
                            'message': 'Found 15 recommended playlists',
                            'data': {
                                'recommendation_type': 'personalized',
                                'preferred_genres': ['Rock', 'Pop', 'Electronic'],
                                'playlists': [
                                    {
                                        'id': 301,
                                        'name': 'Rock Classics',
                                        'description': 'Essential rock songs',
                                        'owner_id': 10,
                                        'visibility': 'public',
                                        'playlist_type': 'solo',
                                        'track_count': 100,
                                        'cover_url': 'https://example.com/rock.jpg'
                                    },
                                    {
                                        'id': 302,
                                        'name': 'Pop Hits 2026',
                                        'description': 'Current pop favorites',
                                        'owner_id': 15,
                                        'visibility': 'public',
                                        'playlist_type': 'solo',
                                        'track_count': 50
                                    }
                                ]
                            }
                        }
                    },
                    'fallback_featured': {
                        'summary': 'No preference data, showing featured playlists',
                        'value': {
                            'success': True,
                            'message': 'Featured playlists returned',
                            'data': {
                                'recommendation_type': 'featured',
                                'preferred_genres': [],
                                'playlists': [
                                    {
                                        'id': 401,
                                        'name': 'Top Hits 2026',
                                        'description': 'Trending now',
                                        'owner_id': 1,
                                        'visibility': 'public',
                                        'playlist_type': 'solo',
                                        'track_count': 100
                                    }
                                ]
                            }
                        }
                    },
                    'no_recommendations': {
                        'summary': 'No matching playlists found',
                        'value': {
                            'success': True,
                            'message': 'Found 0 recommended playlists',
                            'data': {
                                'recommendation_type': 'personalized',
                                'preferred_genres': ['Jazz'],
                                'playlists': []
                            }
                        }
                    }
                }
            }
        }
    )

    def get(self, request):
        limit = int(request.query_params.get('limit', 20))

        # Get genres from user's liked playlists
        liked_playlist_ids = UserPlaylistLike.objects.filter(
            user_id=request.user.id
        ).values_list('playlist_id', flat=True)

        # Get genres from user's followed playlists
        followed_playlist_ids = UserPlaylistFollow.objects.filter(
            user_id=request.user.id
        ).values_list('playlist_id', flat=True)

        # Combine to get user's preferred genres
        preferred_playlist_ids = set(liked_playlist_ids) | set(followed_playlist_ids)

        if not preferred_playlist_ids:
            # No preferences, return featured playlists
            return SuccessResponse(
                data={
                    'recommendation_type': 'featured',
                    'playlists': FeaturedPlaylistsView.as_view()(request._request).data
                },
                message='Featured playlists returned'
            )

        # Get genres from user's preferred playlists
        from trackapp.models import Track

        preferred_genres = list(
            Track.objects.filter(
                playlist_id__in=preferred_playlist_ids
            ).exclude(
                song__genre=''
            ).values_list('song__genre', flat=True).distinct()
        )

        if not preferred_genres:
            # No genres found, return featured playlists
            return SuccessResponse(
                data={
                    'recommendation_type': 'featured',
                    'playlists': FeaturedPlaylistsView.as_view()(request._request).data
                },
                message='Featured playlists returned'
            )

        # Find playlists with similar genres (excluding user's own)

        # Find playlists with matching genres
        playlist_genre_scores = {}
        playlists_with_genres = Track.objects.filter(
            song__genre__in=preferred_genres
        ).exclude(
            playlist_id__in=Playlist.objects.filter(owner_id=request.user.id)
        ).values('playlist_id', 'song__genre')

        # Calculate genre overlap scores
        for item in playlists_with_genres:
            pid = item['playlist_id']
            genre_name = item['song__genre']

            if pid not in playlist_genre_scores:
                playlist_genre_scores[pid] = {'matches': 0, 'genres': set()}
            if genre_name in preferred_genres:
                playlist_genre_scores[pid]['matches'] += 1
                playlist_genre_scores[pid]['genres'].add(genre_name)

        # Sort by match count
        sorted_playlists = sorted(
            playlist_genre_scores.items(),
            key=lambda x: x[1]['matches'],
            reverse=True
        )

        # Get top N playlists
        top_playlist_ids = [pid for pid, _ in sorted_playlists[:limit]]

        playlists = Playlist.objects.filter(
            id__in=top_playlist_ids,
            visibility='public'
        ).annotate(
            track_count=Count('tracks')
        )

        # Maintain order by score
        playlist_dict = {p.id: p for p in playlists}
        ordered_playlists = []
        for pid in top_playlist_ids:
            if pid in playlist_dict:
                ordered_playlists.append(playlist_dict[pid])

        return SuccessResponse(
            data={
                'recommendation_type': 'genre_based',
                'preferred_genres': preferred_genres,
                'total': len(ordered_playlists),
                'playlists': PlaylistSerializer(ordered_playlists, many=True).data
            },
            message=f'Genre-based recommendations: {len(ordered_playlists)} playlists'
        )


class SimilarPlaylistsView(APIView):
    """
    GET /api/playlists/{id}/similar/

    Returns playlists similar to the given playlist:
    - Based on genre overlap
    - Based on track count similarity
    - Excludes the playlist itself
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Get similar playlists",
        description="Finds playlists similar to the specified playlist based on genre overlap using Jaccard similarity coefficient. Returns public playlists that share genres with the given playlist, ranked by similarity score. Excludes the playlist itself and the user's own playlists. Ideal for 'more like this' discovery features and playlist exploration.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist to find similar playlists for',
                required=True,
                example=123
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of similar playlists to return (default: 10)',
                required=False,
                example=10
            )
        ],
        examples=[
            OpenApiExample(
                'Find similar playlists',
                description='Get playlists similar to the specified one',
                value={'limit': 10}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'similar_found': {
                        'summary': 'Similar playlists found',
                        'value': {
                            'success': True,
                            'message': 'Found 8 similar playlists',
                            'data': {
                                'playlist_id': 123,
                                'playlist_genres': ['Rock', 'Pop'],
                                'similar_playlists': [
                                    {
                                        'id': 201,
                                        'name': 'Rock Mix',
                                        'description': 'Similar genres',
                                        'owner_id': 10,
                                        'visibility': 'public',
                                        'playlist_type': 'solo',
                                        'track_count': 45,
                                        'similarity_score': 0.75,
                                        'shared_genres': ['Rock', 'Pop']
                                    },
                                    {
                                        'id': 202,
                                        'name': 'Pop Rock Hits',
                                        'description': 'Great mix',
                                        'owner_id': 15,
                                        'visibility': 'public',
                                        'playlist_type': 'solo',
                                        'track_count': 60,
                                        'similarity_score': 0.67,
                                        'shared_genres': ['Rock']
                                    }
                                ],
                                'total': 8
                            }
                        }
                    },
                    'no_genres': {
                        'summary': 'Source playlist has no genre information',
                        'value': {
                            'success': True,
                            'message': 'No genres found in this playlist',
                            'data': {
                                'playlist_id': 456,
                                'playlist_genres': [],
                                'similar_playlists': [],
                                'total': 0
                            }
                        }
                    },
                    'no_similar': {
                        'summary': 'No other playlists with matching genres',
                        'value': {
                            'success': True,
                            'message': 'Found 0 similar playlists',
                            'data': {
                                'playlist_id': 789,
                                'playlist_genres': ['Jazz'],
                                'similar_playlists': [],
                                'total': 0
                            }
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'playlist_not_found': {
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )

    def get(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        limit = int(request.query_params.get('limit', 10))

        # Get genres from this playlist
        from trackapp.models import Track

        playlist_genres = list(
            Track.objects.filter(
                playlist=playlist
            ).exclude(
                song__genre=''
            ).values_list('song__genre', flat=True).distinct()
        )

        if not playlist_genres:
            return SuccessResponse(
                data={'similar_playlists': []},
                message='No genres found in this playlist'
            )

        # Find playlists with similar genres
        similar_candidates = Track.objects.filter(
            song__genre__in=playlist_genres
        ).exclude(
            playlist_id=playlist_id
        ).values('playlist_id', 'song__genre')

        # Calculate Jaccard similarity (intersection / union)
        # OPTIMIZATION: Fetch all candidate genres in one query to avoid N+1
        playlist_a_genres = set(playlist_genres)

        # Get all playlist-genre pairs in a single query
        candidate_playlist_ids = [c['playlist_id'] for c in similar_candidates]
        all_candidate_genres = Track.objects.filter(
            playlist_id__in=candidate_playlist_ids
        ).exclude(
            song__genre=''
        ).values_list('playlist_id', 'song__genre')

        # Build playlist->genres mapping
        playlist_genres_map = {}
        for pid, genre in all_candidate_genres:
            if pid not in playlist_genres_map:
                playlist_genres_map[pid] = set()
            playlist_genres_map[pid].add(genre)

        # Calculate Jaccard similarity using pre-fetched genres
        playlist_similarities = {}
        for pid in candidate_playlist_ids:
            if pid in playlist_genres_map:
                candidate_genres = playlist_genres_map[pid]
                intersection = len(playlist_a_genres & candidate_genres)
                union = len(playlist_a_genres | candidate_genres)

                if union > 0:
                    jaccard_score = intersection / union
                    playlist_similarities[pid] = jaccard_score

        # Sort by similarity score
        sorted_similar = sorted(
            playlist_similarities.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        # Get playlist objects
        similar_ids = [pid for pid, _ in sorted_similar]

        similar_playlists = Playlist.objects.filter(
            id__in=similar_ids,
            visibility='public'
        ).annotate(
            track_count=Count('tracks')
        )

        # Order by similarity score
        playlist_dict = {p.id: p for p in similar_playlists}
        ordered_playlists = []
        for pid in similar_ids:
            if pid in playlist_dict:
                ordered_playlists.append(playlist_dict[pid])

        return SuccessResponse(
            data={
                'playlist_id': playlist_id,
                'playlist_name': playlist.name,
                'playlist_genres': playlist_genres,
                'total': len(ordered_playlists),
                'similar_playlists': PlaylistSerializer(ordered_playlists, many=True).data
            },
            message=f'Found {len(ordered_playlists)} similar playlists'
        )


class AutoGeneratedPlaylistsView(APIView):
    """
    GET /api/playlists/auto-generated/

    Returns auto-generated playlist suggestions based on:
    - User's most listened genres
    - Trending genres across platform
    - Mood-based mixes

    POST /api/playlists/auto-generated/

    Creates an auto-generated playlist:
    - Based on specified genre or mood
    - Picks top tracks from that category
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Get auto-generated playlist suggestions",
        description="Returns suggestions for auto-generated playlists based on your listening history and preferences. Analyzes genres from your liked playlists to identify favorite genres, then suggests genre-based mixes. Also includes mood-based playlist suggestions (chill, workout, focus). These are suggestions that can be created via the POST endpoint.",
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'suggestions_found': {
                        'summary': 'Auto-generated suggestions retrieved',
                        'value': {
                            'success': True,
                            'message': 'Auto-generated playlist suggestions retrieved',
                            'data': {
                                'suggestions': [
                                    {
                                        'type': 'genre_based',
                                        'name': 'Rock Mix',
                                        'description': 'Auto-generated playlist based on Rock genre',
                                        'estimated_track_count': 150,
                                        'genre': 'Rock'
                                    },
                                    {
                                        'type': 'genre_based',
                                        'name': 'Pop Mix',
                                        'description': 'Auto-generated playlist based on Pop genre',
                                        'estimated_track_count': 200,
                                        'genre': 'Pop'
                                    },
                                    {
                                        'type': 'mood_based',
                                        'name': 'Chill Vibes',
                                        'description': 'Relaxing tracks for unwinding',
                                        'mood': 'chill'
                                    },
                                    {
                                        'type': 'mood_based',
                                        'name': 'Workout Mix',
                                        'description': 'High-energy tracks for workouts',
                                        'mood': 'energetic'
                                    }
                                ]
                            }
                        }
                    },
                    'fallback_suggestions': {
                        'summary': 'No liked playlists, using default genres',
                        'value': {
                            'success': True,
                            'message': 'Auto-generated playlist suggestions retrieved',
                            'data': {
                                'suggestions': [
                                    {
                                        'type': 'genre_based',
                                        'name': 'Pop Mix',
                                        'description': 'Auto-generated playlist based on Pop genre',
                                        'estimated_track_count': 180,
                                        'genre': 'Pop'
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        }
    )

    def get(self, request):
        """Get auto-generated playlist suggestions"""
        # OPTIMIZATION: Fetch liked playlist IDs once and reuse
        liked_playlist_ids = UserPlaylistLike.objects.filter(
            user_id=request.user.id
        ).values_list('playlist_id', flat=True)

        # Get user's favorite genres from their liked playlists in a single query
        liked_genres = list(
            Track.objects.filter(
                playlist_id__in=liked_playlist_ids
            ).exclude(
                song__genre=''
            ).values_list('song__genre', flat=True)
        )

        # Count genre occurrences
        from collections import Counter
        genre_counts = Counter(liked_genres)

        # Get top genres
        top_genres = [genre for genre, _ in genre_counts.most_common(5)]

        if not top_genres:
            # Fallback to popular genres across platform
            top_genres = ['Pop', 'Rock', 'Hip-Hop', 'Electronic', 'Jazz']

        suggestions = []
        for genre in top_genres:
            # Count tracks available in this genre
            track_count = Track.objects.filter(
                song__genre=genre
            ).count()

            if track_count > 0:
                suggestions.append({
                    'type': 'genre_based',
                    'name': f'{genre} Mix',
                    'description': f'Auto-generated playlist based on {genre} genre',
                    'estimated_track_count': track_count,
                    'genre': genre
                })

        # Add mood-based suggestions
        mood_suggestions = [
            {'type': 'mood_based', 'name': 'Chill Vibes', 'description': 'Relaxing tracks for unwinding', 'mood': 'chill'},
            {
                'type': 'mood_based',
                'name': 'Workout Mix',
                'description': 'High-energy tracks for workouts',
                'mood': 'energetic'
            },
            {'type': 'mood_based', 'name': 'Focus Flow', 'description': 'Concentration-boosting tracks', 'mood': 'focus'},
        ]

        return SuccessResponse(
            data={'suggestions': suggestions + mood_suggestions},
            message='Auto-generated playlist suggestions retrieved'
        )

    @extend_schema(
        tags=["Playlists"],
        summary="Create auto-generated playlist",
        description="Creates an auto-generated playlist based on specified criteria. Supports genre-based generation (picks top tracks from a genre), taste-based (your favorite genres), trending (popular tracks), new releases, or similar songs. The playlist is automatically populated with tracks and owned by you.",
        request={
            'application/json': {
                'type': 'object',
                'required': ['generation_type'],
                'properties': {
                    'generation_type': {
                        'type': 'string',
                        'enum': ['genre', 'taste', 'trending', 'new_releases', 'similar_song'],
                        'description': 'Type of auto-generation to perform',
                        'example': 'genre'
                    },
                    'name': {
                        'type': 'string',
                        'description': 'Custom name for the playlist (optional, auto-generated if not provided)',
                        'maxLength': 255,
                        'example': 'My Rock Mix'
                    },
                    'track_limit': {
                        'type': 'integer',
                        'description': 'Maximum number of tracks to include (default: 20)',
                        'minimum': 1,
                        'maximum': 100,
                        'example': 30
                    },
                    'genre': {
                        'type': 'string',
                        'description': 'Genre name (required for genre-based generation)',
                        'example': 'Rock'
                    },
                    'mood': {
                        'type': 'string',
                        'enum': ['chill', 'energetic', 'focus', 'party', 'workout'],
                        'description': 'Mood for mood-based generation (optional)',
                        'example': 'energetic'
                    },
                    'song_id': {
                        'type': 'integer',
                        'description': 'Song ID for similar song generation (required for similar_song type)',
                        'example': 456
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Genre-based playlist',
                description='Create an auto-generated playlist from a specific genre',
                value={
                    'generation_type': 'genre',
                    'genre': 'Rock',
                    'track_limit': 30
                }
            ),
            OpenApiExample(
                'Taste-based playlist',
                description='Create playlist based on your favorite genres',
                value={
                    'generation_type': 'taste',
                    'name': 'My Mix',
                    'track_limit': 50
                }
            ),
            OpenApiExample(
                'Trending playlist',
                description='Create playlist from trending tracks',
                value={
                    'generation_type': 'trending',
                    'track_limit': 20
                }
            )
        ],
        responses={
            201: {
                'type': 'object',
                'examples': {
                    'created_successfully': {
                        'summary': 'Auto-generated playlist created',
                        'value': {
                            'success': True,
                            'message': 'Auto-generated playlist created successfully',
                            'data': {
                                'id': 501,
                                'name': 'Rock Mix',
                                'description': 'Auto-generated from Rock genre',
                                'owner_id': 1,
                                'visibility': 'private',
                                'playlist_type': 'solo',
                                'track_count': 30,
                                'is_system_generated': True
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_genre': {
                        'summary': 'Genre required for genre-based generation',
                        'value': {
                            'success': False,
                            'message': 'Genre is required for genre-based generation',
                            'errors': {
                                'genre': ['Genre is required for genre-based generation']
                            }
                        }
                    },
                    'missing_song_id': {
                        'summary': 'Song ID required for similar song generation',
                        'value': {
                            'success': False,
                            'message': 'Song ID is required for similar song generation',
                            'errors': {
                                'song_id': ['Song ID is required for similar song generation']
                            }
                        }
                    }
                }
            }
        }
    )
    def post(self, request):
        """Create an auto-generated playlist"""
        generation_type = request.data.get('generation_type', 'genre')  # genre, taste, trending, new_releases, similar_song
        name = request.data.get('name')
        track_limit = int(request.data.get('track_limit', 20))

        # Parameters for different generation types
        genre = request.data.get('genre')
        mood = request.data.get('mood')
        song_id = request.data.get('song_id')  # For similar_song type

        # Validate required parameters
        if generation_type == 'genre' and not genre:
            return ValidationErrorResponse(
                errors={'genre': 'Genre is required for genre-based generation'},
                message='Genre is required for genre-based generation'
            )
        if generation_type == 'similar_song' and not song_id:
            return ValidationErrorResponse(
                errors={'song_id': 'Song ID is required for similar song generation'},
                message='Song ID is required for similar song generation'
            )

        # Determine playlist name if not provided
        if not name:
            if generation_type == 'taste':
                name = 'For You Mix'
            elif generation_type == 'trending':
                name = 'Trending Now'
            elif generation_type == 'new_releases':
                name = 'New Releases'
            elif generation_type == 'similar_song':
                name = 'Similar Tracks'
            elif genre:
                name = f'{genre} Mix'
            elif mood:
                name = f'{mood.capitalize()} Mix'
            else:
                name = 'Auto-Generated Playlist'

        # Import searchapp models for recommendation integration
        from searchapp.models import Song

        # Find tracks based on generation type
        tracks_to_add = []

        if generation_type == 'taste':
            # Use personalized recommendations
            import requests
            from django.conf import settings

            # Call internal recommendations endpoint
            try:
                # Get recommended songs from searchapp
                from searchapp.views import RecommendationsView
                from django.test import RequestFactory

                factory = RequestFactory()
                rec_request = factory.get(f'/api/discover/recommendations/?limit={track_limit}')
                rec_request.user = request.user

                view = RecommendationsView.as_view()
                response = view(rec_request)
                response_data = response.data

                if response_data.get('recommendation_type') == 'personalized':
                    song_ids = [song['id'] for song in response_data['songs']]
                    tracks_to_add = Track.objects.filter(
                        song_id__in=song_ids
                    ).select_related('song', 'song__artist', 'song__album').order_by('song_id').distinct('song_id')[:track_limit]
                else:
                    # Fallback to trending
                    tracks_to_add = Track.objects.filter(
                        song__popularity_score__gt=0
                    ).select_related('song', 'song__artist', 'song__album').order_by(
                        'song_id', '-song__popularity_score'
                    ).distinct('song_id')[:track_limit]
            except Exception as e:
                # Fallback to trending on error
                tracks_to_add = Track.objects.filter(
                    song__popularity_score__gt=0
                ).select_related('song', 'song__artist', 'song__album').order_by(
                    'song_id', '-song__popularity_score'
                ).distinct('song_id')[:track_limit]

        elif generation_type == 'trending':
            # Get trending songs
            trending_songs = Song.objects.filter(
                popularity_score__gt=0
            ).order_by('-popularity_score', '-release_date')[:track_limit]

            tracks_to_add = []
            for song in trending_songs:
                tracks_to_add.append(Track(
                    song=song,
                    added_by_id=request.user.id,
                    position=len(tracks_to_add)
                ))

        elif generation_type == 'new_releases':
            # Get new releases (last 90 days)
            from datetime import datetime, timedelta
            since_date = datetime.now().date() - timedelta(days=90)

            new_songs = Song.objects.filter(
                release_date__gte=since_date
            ).order_by('-release_date', '-popularity_score')[:track_limit]

            tracks_to_add = []
            for song in new_songs:
                tracks_to_add.append(Track(
                    song=song,
                    added_by_id=request.user.id,
                    position=len(tracks_to_add)
                ))

        elif generation_type == 'similar_song':
            # Get songs similar to the given song
            try:
                reference_song = Song.objects.get(id=song_id)
            except Song.DoesNotExist:
                return NotFoundResponse(message='Reference song not found')

            # Find similar songs (same genre or artist)
            similar_songs = Song.objects.filter(
                Q(genre__iexact=reference_song.genre) |
                Q(artist_id=reference_song.artist_id)
            ).exclude(
                id=reference_song.id
            ).select_related('artist', 'album').order_by(
                '-popularity_score'
            )[:track_limit]

            tracks_to_add = []
            for song in similar_songs:
                tracks_to_add.append(Track(
                    song=song,
                    added_by_id=request.user.id,
                    position=len(tracks_to_add)
                ))

        else:  # genre or mood-based (original logic)
            tracks_queryset = Track.objects.select_related('song', 'song__artist', 'song__album')

            if genre:
                tracks_to_add = tracks_queryset.filter(
                    song__genre=genre
                ).order_by('song_id', '-added_at').distinct('song_id')[:track_limit]
            else:
                # For mood, we'll use genre as a proxy
                mood_genre_map = {
                    'chill': ['Jazz', 'Ambient', 'Lo-Fi', 'Classical'],
                    'energetic': ['Rock', 'Electronic', 'Hip-Hop', 'Pop'],
                    'focus': ['Classical', 'Ambient', 'Electronic'],
                }

                genres = mood_genre_map.get(mood, ['Pop'])
                tracks_to_add = tracks_queryset.filter(
                    song__genre__in=genres
                ).order_by('song_id', '-added_at').distinct('song_id')[:track_limit]

        if not tracks_to_add:
            return NotFoundResponse(message='No tracks found for the specified criteria')

        # Create the playlist
        description = f'Auto-generated playlist based on {generation_type}'
        if genre:
            description = f'Auto-generated {genre} playlist'
        elif song_id:
            description = 'Songs similar to your selection'
        elif generation_type == 'taste':
            description = 'Personalized recommendations based on your taste'

        playlist = Playlist.objects.create(
            owner_id=request.user.id,
            name=name,
            description=description,
            visibility='private',
            playlist_type='solo',
            is_system_generated=True,
            max_songs=len(tracks_to_add)
        )

        # Add tracks to playlist
        new_tracks = []
        for index, track in enumerate(tracks_to_add):
            if isinstance(track, Track):
                # Track already exists (from queryset), need to duplicate it
                new_tracks.append(Track(
                    playlist=playlist,
                    song=track.song,
                    added_by_id=request.user.id,
                    position=index
                ))
            else:
                # Track created new (with song reference)
                new_tracks.append(track)

        Track.objects.bulk_create(new_tracks)

        return SuccessResponse(
            data=PlaylistSerializer(playlist).data,
            message='Auto-generated playlist created successfully',
            status_code=201
        )


class EnhancedBatchDeleteView(APIView):
    """
    DELETE /api/playlists/batch-delete-advanced/

    Enhanced batch delete with detailed error tracking:
    - Returns per-playlist deletion results
    - Includes reasons for failures
    - Supports partial success
    - Creates snapshots before deletion
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Enhanced batch delete playlists",
        description="Advanced bulk deletion with detailed per-playlist results. Returns success/failure status for each playlist with specific failure reasons. Optionally creates snapshots before deletion for recovery. Only affects playlists owned by the authenticated user. Supports partial success - some playlists can fail while others succeed.",
        request={
            'application/json': {
                'type': 'object',
                'required': ['playlist_ids'],
                'properties': {
                    'playlist_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'List of playlist IDs to delete. Only playlists you own will be deleted.',
                        'minItems': 1,
                        'example': [123, 456, 789]
                    },
                    'create_snapshots': {
                        'type': 'boolean',
                        'description': 'Whether to create snapshots before deletion for potential recovery (default: false)',
                        'default': False,
                        'example': True
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Simple batch delete',
                description='Delete multiple playlists without snapshots',
                value={'playlist_ids': [123, 456]}
            ),
            OpenApiExample(
                'Delete with snapshots',
                description='Delete playlists with backup snapshots',
                value={
                    'playlist_ids': [123, 456, 789],
                    'create_snapshots': True
                }
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'all_deleted': {
                        'summary': 'All playlists deleted successfully',
                        'value': {
                            'success': True,
                            'message': 'Snapshot batch delete completed: 3 deleted',
                            'data': {
                                'total': 3,
                                'deleted': 3,
                                'failed': 0,
                                'results': [
                                    {
                                        'playlist_id': 123,
                                        'status': 'deleted',
                                        'name': 'Old Playlist'
                                    },
                                    {
                                        'playlist_id': 456,
                                        'status': 'deleted',
                                        'name': 'Another Playlist'
                                    },
                                    {
                                        'playlist_id': 789,
                                        'status': 'deleted',
                                        'name': 'Third Playlist'
                                    }
                                ]
                            }
                        }
                    },
                    'partial_success': {
                        'summary': 'Some deleted, some failed',
                        'value': {
                            'success': True,
                            'message': 'Snapshot batch delete completed: 2 deleted',
                            'data': {
                                'total': 4,
                                'deleted': 2,
                                'failed': 2,
                                'results': [
                                    {
                                        'playlist_id': 123,
                                        'status': 'deleted',
                                        'name': 'My Playlist'
                                    },
                                    {
                                        'playlist_id': 456,
                                        'status': 'failed',
                                        'reason': 'not_authorized'
                                    },
                                    {
                                        'playlist_id': 789,
                                        'status': 'failed',
                                        'reason': 'not_found'
                                    },
                                    {
                                        'playlist_id': 999,
                                        'status': 'failed',
                                        'reason': 'not_authorized'
                                    }
                                ]
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_playlist_ids': {
                        'summary': 'playlist_ids field not provided',
                        'value': {
                            'success': False,
                            'message': 'playlist_ids is required',
                            'errors': {
                                'playlist_ids': ['This field is required.']
                            }
                        }
                    }
                }
            }
        }
    )
    def delete(self, request):
        playlist_ids = request.data.get('playlist_ids', [])

        if not playlist_ids:
            return ValidationErrorResponse(
                errors={'playlist_ids': 'This field is required'},
                message='playlist_ids is required'
            )

        if not isinstance(playlist_ids, list):
            return ValidationErrorResponse(
                errors={'playlist_ids': 'Must be a list'},
                message='playlist_ids must be a list'
            )

        create_snapshots = request.data.get('create_snapshots', False)

        results = []
        deleted_count = 0
        failed_count = 0

        for playlist_id in playlist_ids:
            try:
                playlist = Playlist.objects.get(id=playlist_id)

                if playlist.owner_id != request.user.id:
                    results.append({
                        'playlist_id': playlist_id,
                        'status': 'failed',
                        'reason': 'not_authorized'
                    })
                    failed_count += 1
                    continue

                # Create snapshot before deletion if requested
                if create_snapshots:
                    snapshot_data = PlaylistSerializer(playlist).data
                    PlaylistSnapshot.objects.create(
                        playlist=playlist,
                        snapshot_data=snapshot_data,
                        created_by=request.user.id,
                        change_reason='Snapshot before deletion',
                        track_count=playlist.tracks.count()
                    )

                # Delete playlist
                playlist_name = playlist.name
                playlist.delete()

                results.append({
                    'playlist_id': playlist_id,
                    'status': 'deleted',
                    'name': playlist_name
                })
                deleted_count += 1

            except Playlist.DoesNotExist:
                results.append({
                    'playlist_id': playlist_id,
                    'status': 'failed',
                    'reason': 'not_found'
                })
                failed_count += 1

        return SuccessResponse(
            data={
                'total': len(playlist_ids),
                'deleted': deleted_count,
                'failed': failed_count,
                'results': results
            },
            message=f'Snapshot batch delete completed: {deleted_count} deleted'
        )


class PlaylistExportView(APIView):
    """
    GET /api/playlists/{id}/export/

    Export playlist to JSON format:
    - Includes metadata and all tracks
    - Includes song details (artist, album, genre)
    - Can be used for backup or import
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Export playlist",
        description="Exports a playlist to JSON format including all metadata, tracks, and song details. The exported data includes playlist information, all tracks with positions, and complete song details (artist, album, genre, duration). This can be used for backups, data portability, or sharing playlist configurations. Only the playlist owner can export their playlists.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist to export',
                required=True,
                example=123
            ),
            OpenApiParameter(
                name='format',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Export format (currently only JSON is supported)',
                required=False,
                enum=['json'],
                example='json'
            )
        ],
        examples=[
            OpenApiExample(
                'Export playlist',
                description='Export playlist data to JSON',
                value={'format': 'json'}
            )
        ],
        responses={
            200: {
                'type': 'application/json',
                'examples': {
                    'export_success': {
                        'summary': 'Playlist exported successfully',
                        'value': {
                            'success': True,
                            'message': 'Playlist exported successfully',
                            'data': {
                                'playlist': {
                                    'id': 123,
                                    'name': 'My Awesome Playlist',
                                    'description': 'My favorite songs',
                                    'owner_id': 1,
                                    'visibility': 'public',
                                    'playlist_type': 'solo',
                                    'cover_url': 'https://example.com/cover.jpg',
                                    'created_at': '2026-03-01T10:00:00Z',
                                    'updated_at': '2026-04-07T15:30:00Z'
                                },
                                'tracks': [
                                    {
                                        'id': 1001,
                                        'position': 0,
                                        'song': {
                                            'id': 501,
                                            'title': 'Bohemian Rhapsody',
                                            'artist': 'Queen',
                                            'album': 'A Night at the Opera',
                                            'genre': 'Rock',
                                            'duration_seconds': 354,
                                            'release_year': 1975
                                        },
                                        'added_at': '2026-03-01T10:05:00Z'
                                    },
                                    {
                                        'id': 1002,
                                        'position': 1,
                                        'song': {
                                            'id': 502,
                                            'title': 'Stairway to Heaven',
                                            'artist': 'Led Zeppelin',
                                            'album': 'Led Zeppelin IV',
                                            'genre': 'Rock',
                                            'duration_seconds': 482,
                                            'release_year': 1971
                                        },
                                        'added_at': '2026-03-01T10:05:30Z'
                                    }
                                ],
                                'exported_at': '2026-04-07T18:00:00Z',
                                'total_tracks': 2
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Only the owner can export playlists',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to export this playlist'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'playlist_not_found': {
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )
    def get(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization check
        if not user_can_access_playlist(playlist, request.user.id, request.META.get('HTTP_AUTHORIZATION', '')):
            return ForbiddenResponse(message='Not authorized to export this playlist')

        # Get all tracks with song details
        tracks = Track.objects.filter(
            playlist=playlist
        ).select_related(
            'song__artist', 'song__album'
        ).order_by('position')

        # Build export data
        export_data = {
            'playlist': {
                'id': playlist.id,
                'name': playlist.name,
                'description': playlist.description,
                'visibility': playlist.visibility,
                'playlist_type': playlist.playlist_type,
                'max_songs': playlist.max_songs,
                'created_at': playlist.created_at.isoformat(),
                'updated_at': playlist.updated_at.isoformat(),
                'cover_url': playlist.cover_url,
            },
            'tracks': [],
            'export_metadata': {
                'exported_at': timezone.now().isoformat(),
                'exported_by': request.user.id,
                'track_count': tracks.count(),
                'version': '1.0'
            }
        }

        # Add track details
        for track in tracks:
            track_data = {
                'position': track.position,
                'added_at': track.added_at.isoformat() if track.added_at else None,
                'song': {
                    'id': track.song.id,
                    'title': track.song.title,
                    'duration_seconds': track.song.duration_seconds,
                    'genre': track.song.genre,
                    'release_date': track.song.release_date.isoformat() if track.song.release_date else None,
                    'artist': {
                        'id': track.song.artist.id,
                        'name': track.song.artist.name
                    } if track.song.artist else None,
                    'album': {
                        'id': track.song.album.id,
                        'name': track.song.album.name,
                        'cover_url': track.song.album.cover_url
                    } if track.song.album else None
                }
            }
            export_data['tracks'].append(track_data)

        return SuccessResponse(
            data=export_data,
            message='Playlist exported successfully'
        )


class PlaylistImportView(APIView):
    """
    POST /api/playlists/import/

    Import playlist from JSON export:
    - Creates new playlist from export data
    - Validates data integrity
    - Creates all tracks with relationships
    - Supports custom name (for duplicates)
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Import playlist",
        description="Imports a playlist from previously exported JSON data. Creates a new playlist owned by you with the same metadata and tracks. Validates all data integrity and creates track relationships. Songs are matched by ID if available, or by title and artist. Use this to restore backups, duplicate playlists across accounts, or share playlist configurations. The imported playlist is always created as private.",
        request={
            'application/json': {
                'type': 'object',
                'required': ['playlist'],
                'properties': {
                    'playlist': {
                        'type': 'object',
                        'description': 'Playlist export data from the export endpoint',
                        'properties': {
                            'name': {
                                'type': 'string',
                                'description': 'Playlist name from export',
                                'example': 'My Awesome Playlist'
                            },
                            'description': {
                                'type': 'string',
                                'description': 'Playlist description',
                                'example': 'My favorite songs'
                            },
                            'visibility': {
                                'type': 'string',
                                'enum': ['public', 'private'],
                                'example': 'private'
                            },
                            'playlist_type': {
                                'type': 'string',
                                'enum': ['solo', 'collaborative'],
                                'example': 'solo'
                            },
                            'cover_url': {
                                'type': 'string',
                                'description': 'Cover image URL',
                                'example': 'https://example.com/cover.jpg'
                            },
                            'tracks': {
                                'type': 'array',
                                'description': 'List of tracks with song details',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'position': {'type': 'integer'},
                                        'song': {
                                            'type': 'object',
                                            'properties': {
                                                'id': {'type': 'integer'},
                                                'title': {'type': 'string'},
                                                'artist': {'type': 'string'},
                                                'album': {'type': 'string'},
                                                'genre': {'type': 'string'}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    'name': {
                        'type': 'string',
                        'description': 'Custom name for the imported playlist (overrides export name)',
                        'maxLength': 255
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Import playlist',
                description='Import a playlist from exported JSON data',
                value={
                    'playlist': {
                        'name': 'Imported Playlist',
                        'description': 'Imported from backup',
                        'visibility': 'private',
                        'tracks': [
                            {
                                'position': 0,
                                'song': {
                                    'id': 501,
                                    'title': 'Song Title',
                                    'artist': 'Artist Name'
                                }
                            }
                        ]
                    }
                }
            ),
            OpenApiExample(
                'Import with custom name',
                description='Import with a custom name',
                value={
                    'playlist': {
                        'name': 'Original Name',
                        'tracks': []
                    },
                    'name': 'My Custom Name'
                }
            )
        ],
        responses={
            201: {
                'type': 'object',
                'examples': {
                    'import_success': {
                        'summary': 'Playlist imported successfully',
                        'value': {
                            'success': True,
                            'message': 'Playlist imported successfully',
                            'data': {
                                'id': 601,
                                'name': 'My Awesome Playlist',
                                'description': 'Imported from backup',
                                'owner_id': 1,
                                'visibility': 'private',
                                'playlist_type': 'solo',
                                'track_count': 25,
                                'imported_tracks': 25,
                                'skipped_tracks': 0
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_playlist': {
                        'summary': 'playlist field not provided',
                        'value': {
                            'success': False,
                            'message': 'playlist data is required',
                            'errors': {
                                'playlist': ['This field is required.']
                            }
                        }
                    },
                    'invalid_visibility': {
                        'summary': 'Invalid visibility value',
                        'value': {
                            'success': False,
                            'message': 'Invalid visibility value'
                        }
                    }
                }
            }
        }
    )
    def post(self, request):
        import_data = request.data.get('playlist')

        if not import_data:
            return ValidationErrorResponse(
                errors={'playlist': 'This field is required'},
                message='playlist data is required'
            )

        try:
            # Extract playlist data
            name = request.data.get('name', import_data.get('name', 'Imported Playlist'))
            description = import_data.get('description', '')
            visibility = import_data.get('visibility', 'private')
            playlist_type = import_data.get('playlist_type', 'solo')
            max_songs = import_data.get('max_songs', 0)
            cover_url = import_data.get('cover_url', '')

            tracks_data = import_data.get('tracks', [])

            # Validate data
            if visibility not in ['public', 'private']:
                visibility = 'private'

            if playlist_type not in ['solo', 'collaborative']:
                playlist_type = 'solo'

            # Create playlist
            from django.db import transaction
            with transaction.atomic():
                playlist = Playlist.objects.create(
                    owner_id=request.user.id,
                    name=name,
                    description=description,
                    visibility=visibility,
                    playlist_type=playlist_type,
                    max_songs=max_songs,
                    cover_url=cover_url
                )

                # Import tracks
                from trackapp.models import Song
                imported_tracks = []

                for track_data in tracks_data:
                    song_data = track_data.get('song')
                    if not song_data:
                        continue

                    try:
                        # Find or create song
                        song_id = song_data.get('id')
                        song = None

                        if song_id:
                            song = Song.objects.filter(id=song_id).first()

                        if not song:
                            # Try to find by title and artist
                            from artistapp.models import Artist

                            artist_name = song_data.get('artist', {}).get('name') if song_data.get('artist') else None
                            title = song_data.get('title')

                            if artist_name and title:
                                artist = Artist.objects.filter(name=artist_name).first()
                                if artist:
                                    song = Song.objects.filter(
                                        title=title,
                                        artist=artist
                                    ).first()

                        if song:
                            imported_tracks.append(Track(
                                playlist=playlist,
                                song=song,
                                added_by_id=request.user.id,
                                position=track_data.get('position', len(imported_tracks))
                            ))

                    except Exception:
                        # Skip tracks that can't be imported
                        continue

                # Bulk create tracks
                if imported_tracks:
                    Track.objects.bulk_create(imported_tracks)
                    playlist.max_songs = len(imported_tracks)
                    playlist.save()

            return SuccessResponse(
                data=PlaylistSerializer(playlist).data,
                message='Playlist imported successfully',
                status_code=201
            )

        except Exception as e:
            return ErrorResponse(
                error='import_failed',
                message=str(e)
            )


class PlaylistSnapshotView(APIView):
    """
    GET /api/playlists/{id}/snapshots/

    List all snapshots for a playlist

    POST /api/playlists/{id}/snapshots/

    Create a manual snapshot

    DELETE /api/playlists/{id}/snapshots/

    Delete old snapshots (cleanup)
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="List playlist snapshots",
        description="Returns all version snapshots for a playlist in reverse chronological order (newest first). Snapshots are point-in-time backups of playlist state including metadata and track list. Only the playlist owner can view snapshots. Useful for version history, audit trails, and recovery options.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist',
                required=True,
                example=123
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of snapshots to return (default: 20)',
                required=False,
                example=20
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'snapshots_found': {
                        'summary': 'Snapshots retrieved successfully',
                        'value': {
                            'success': True,
                            'message': 'Retrieved 5 snapshots',
                            'data': {
                                'playlist_id': 123,
                                'total': 5,
                                'snapshots': [
                                    {
                                        'id': 1001,
                                        'snapshot_data': {
                                            'name': 'My Playlist',
                                            'track_count': 25
                                        },
                                        'change_reason': 'Manual snapshot',
                                        'track_count': 25,
                                        'created_at': '2026-04-07T18:00:00Z'
                                    },
                                    {
                                        'id': 1002,
                                        'snapshot_data': {
                                            'name': 'My Playlist',
                                            'track_count': 20
                                        },
                                        'change_reason': 'Before major reordering',
                                        'track_count': 20,
                                        'created_at': '2026-04-06T15:30:00Z'
                                    }
                                ]
                            }
                        }
                    },
                    'no_snapshots': {
                        'summary': 'No snapshots exist for this playlist',
                        'value': {
                            'success': True,
                            'message': 'Retrieved 0 snapshots',
                            'data': {
                                'playlist_id': 123,
                                'total': 0,
                                'snapshots': []
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Only the owner can view snapshots',
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
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )
    def get(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization
        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized')

        limit = int(request.query_params.get('limit', 20))

        snapshots = playlist.snapshots.all()[:limit]

        return SuccessResponse(
            data={
                'playlist_id': playlist_id,
                'total': snapshots.count(),
                'snapshots': PlaylistSnapshotSerializer(snapshots, many=True).data
            },
            message=f'Retrieved {snapshots.count()} snapshots'
        )

    @extend_schema(
        tags=["Playlists"],
        summary="Create playlist snapshot",
        description="Creates a manual snapshot of the current playlist state. Snapshots capture all playlist metadata and track information at a point in time. Useful for creating restore points before major changes, preserving important versions, or maintaining version history. Only the playlist owner can create snapshots.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist to snapshot',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'change_reason': {
                        'type': 'string',
                        'description': 'Reason for creating the snapshot (e.g., "Before reordering tracks", "Important version")',
                        'maxLength': 255,
                        'example': 'Before major reorganization'
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Create snapshot',
                description='Create a manual snapshot with reason',
                value={'change_reason': 'Before removing tracks'}
            )
        ],
        responses={
            201: {
                'type': 'object',
                'examples': {
                    'snapshot_created': {
                        'summary': 'Snapshot created successfully',
                        'value': {
                            'success': True,
                            'message': 'Snapshot created successfully',
                            'data': {
                                'id': 1003,
                                'snapshot_data': {
                                    'name': 'My Playlist',
                                    'description': 'My favorite songs',
                                    'track_count': 25
                                },
                                'change_reason': 'Before major reorganization',
                                'track_count': 25,
                                'created_at': '2026-04-07T18:30:00Z'
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Only the owner can create snapshots',
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
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )
    def post(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization
        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized')

        change_reason = request.data.get('change_reason', 'Manual snapshot')

        # Create snapshot
        from .serializers import PlaylistSerializer
        playlist_data = PlaylistSerializer(playlist).data

        snapshot = PlaylistSnapshot.objects.create(
            playlist=playlist,
            snapshot_data=playlist_data,
            created_by=request.user.id,
            change_reason=change_reason,
            track_count=playlist.tracks.count()
        )

        return SuccessResponse(
            data=PlaylistSnapshotSerializer(snapshot).data,
            message='Snapshot created successfully',
            status_code=201
        )

    @extend_schema(
        tags=["Playlists"],
        summary="Delete old playlist snapshots",
        description="Deletes old snapshots for a playlist, keeping only the N most recent ones. Useful for cleanup and storage management. Only the playlist owner can delete snapshots. Oldest snapshots are deleted first. This operation cannot be undone - deleted snapshots are permanently removed.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'keep': {
                        'type': 'integer',
                        'description': 'Number of most recent snapshots to keep (default: 10)',
                        'minimum': 1,
                        'example': 10
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Keep last 10',
                description='Delete all but the 10 most recent snapshots',
                value={'keep': 10}
            ),
            OpenApiExample(
                'Keep last 5',
                description='Delete all but the 5 most recent snapshots',
                value={'keep': 5}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'snapshots_deleted': {
                        'summary': 'Old snapshots deleted successfully',
                        'value': {
                            'success': True,
                            'message': 'Deleted 15 old snapshots',
                            'data': {
                                'kept': 10,
                                'deleted': 15
                            }
                        }
                    },
                    'none_deleted': {
                        'summary': 'No snapshots to delete (already within limit)',
                        'value': {
                            'success': True,
                            'message': 'No snapshots to delete',
                            'data': {
                                'total_snapshots': 5,
                                'kept': 10,
                                'deleted': 0
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Only the owner can delete snapshots',
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
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )
    def delete(self, request, playlist_id):
        """Delete old snapshots, keep only N most recent"""
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization
        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized')

        keep = int(request.data.get('keep', 10))

        # Get all snapshots ordered by date
        all_snapshots = list(playlist.snapshots.all())

        if len(all_snapshots) <= keep:
            return SuccessResponse(
                data={'total_snapshots': len(all_snapshots)},
                message='No snapshots to delete'
            )

        # Delete older snapshots
        to_delete = all_snapshots[keep:]
        deleted_count = 0

        for snapshot in to_delete:
            snapshot.delete()
            deleted_count += 1

        return SuccessResponse(
            data={'kept': keep, 'deleted': deleted_count},
            message=f'Deleted {deleted_count} old snapshots'
        )


class PlaylistRestoreView(APIView):
    """
    POST /api/playlists/{id}/restore/{snapshot_id}/

    Restore playlist from a snapshot
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Restore playlist from snapshot",
        description="Restores a playlist to a previous state from a snapshot. Replaces all playlist metadata and tracks with the snapshot data. The current state is lost unless you have a snapshot of it. Only the playlist owner can restore from snapshots. This is useful for undoing major changes, reverting to previous versions, or recovering from mistakes.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist to restore',
                required=True,
                example=123
            ),
            OpenApiParameter(
                name='snapshot_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the snapshot to restore from',
                required=True,
                example=1001
            )
        ],
        examples=[
            OpenApiExample(
                'Restore from snapshot',
                description='Restore playlist to a previous snapshot state',
                value={}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'restored_successfully': {
                        'summary': 'Playlist restored from snapshot',
                        'value': {
                            'success': True,
                            'message': 'Playlist restored successfully',
                            'data': {
                                'id': 123,
                                'name': 'My Playlist',
                                'description': 'Restored from snapshot',
                                'owner_id': 1,
                                'visibility': 'public',
                                'playlist_type': 'solo',
                                'track_count': 25,
                                'restored_from_snapshot': 1001,
                                'restored_at': '2026-04-07T18:45:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'snapshot_not_found': {
                        'summary': 'Snapshot does not exist for this playlist',
                        'value': {
                            'success': False,
                            'message': 'Snapshot not found'
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Only the owner can restore snapshots',
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
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    },
                    'snapshot_not_found': {
                        'summary': 'Snapshot ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Snapshot not found'
                        }
                    }
                }
            }
        }
    )
    def post(self, request, playlist_id, snapshot_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization
        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized')

        try:
            snapshot = PlaylistSnapshot.objects.get(id=snapshot_id, playlist=playlist)
        except PlaylistSnapshot.DoesNotExist:
            return NotFoundResponse(message='Snapshot not found for this playlist')

        # Create snapshot of current state before restoring
        current_snapshot_data = PlaylistSerializer(playlist).data
        PlaylistSnapshot.objects.create(
            playlist=playlist,
            snapshot_data=current_snapshot_data,
            created_by=request.user.id,
            change_reason='Auto-snapshot before restore',
            track_count=playlist.tracks.count()
        )

        # Restore from snapshot
        from django.db import transaction
        with transaction.atomic():
            snapshot_data = snapshot.snapshot_data

            # Restore playlist fields
            playlist.name = snapshot_data.get('name', playlist.name)
            playlist.description = snapshot_data.get('description', playlist.description)
            playlist.visibility = snapshot_data.get('visibility', playlist.visibility)
            playlist.playlist_type = snapshot_data.get('playlist_type', playlist.playlist_type)
            playlist.max_songs = snapshot_data.get('max_songs', playlist.max_songs)
            playlist.cover_url = snapshot_data.get('cover_url', playlist.cover_url)
            playlist.save()

            # Delete all current tracks
            Track.objects.filter(playlist=playlist).delete()

            # Restore tracks from snapshot
            # Note: This assumes songs still exist in database
            restored_tracks = []
            for track_data in snapshot_data.get('tracks', []):
                song_id = track_data.get('song', {}).get('id')
                if song_id:
                    try:
                        from trackapp.models import Song
                        song = Song.objects.get(id=song_id)
                        restored_tracks.append(Track(
                            playlist=playlist,
                            song=song,
                            added_by_id=request.user.id,
                            position=track_data.get('position')
                        ))
                    except Song.DoesNotExist:
                        # Skip tracks where song no longer exists
                        continue

            if restored_tracks:
                Track.objects.bulk_create(restored_tracks)

        return SuccessResponse(
            data=PlaylistSerializer(playlist).data,
            message='Playlist restored successfully from snapshot'
        )


class PlaylistCommentsView(APIView):
    """
    GET /api/playlists/{id}/comments/

    List all comments for a playlist (threaded):
    - Top-level comments only (parent_id is null)
    - Includes replies_count
    - Supports pagination
    - Sorted by most recent first

    POST /api/playlists/{id}/comments/

    Create a new comment on a playlist:
    - Optional parent_id for replies
    - Auto-sets user_id from authenticated user
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="List playlist comments",
        description="Returns all top-level comments for a playlist in threaded format. Shows replies count for each comment and supports pagination. Comments are sorted by most recent first. Only shows comments on public playlists or your own playlists. Deleted comments are filtered out. Use this endpoint for comment sections and discussion threads.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist',
                required=True,
                example=123
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of comments to return (default: 20)',
                required=False,
                example=20
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of comments to skip for pagination (default: 0)',
                required=False,
                example=0
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'comments_found': {
                        'summary': 'Comments retrieved successfully',
                        'value': {
                            'success': True,
                            'message': 'Retrieved 5 comments',
                            'data': {
                                'playlist_id': 123,
                                'total': 5,
                                'limit': 20,
                                'offset': 0,
                                'comments': [
                                    {
                                        'id': 5001,
                                        'content': 'Great playlist! Love the song selection.',
                                        'user_id': 10,
                                        'username': 'musicfan123',
                                        'parent_id': None,
                                        'replies_count': 2,
                                        'likes_count': 5,
                                        'is_liked': False,
                                        'created_at': '2026-04-07T14:30:00Z',
                                        'updated_at': '2026-04-07T14:30:00Z'
                                    }
                                ]
                            }
                        }
                    },
                    'no_comments': {
                        'summary': 'No comments on this playlist',
                        'value': {
                            'success': True,
                            'message': 'Retrieved 0 comments',
                            'data': {
                                'playlist_id': 123,
                                'total': 0,
                                'limit': 20,
                                'offset': 0,
                                'comments': []
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Cannot view comments on private playlist',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to view comments on this playlist'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'playlist_not_found': {
                        'summary': 'Playlist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Playlist not found'
                        }
                    }
                }
            }
        }
    )
    def get(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization: can view comments on public playlists or own playlists
        if not user_can_access_playlist(playlist, request.user.id, request.META.get('HTTP_AUTHORIZATION', '')):
            return ForbiddenResponse(message='Not authorized to view comments on this playlist')

        # Get top-level comments only (no parent)
        comments = PlaylistComment.objects.filter(
            playlist_id=playlist_id,
            parent_id__isnull=True,
            is_deleted=False
        ).order_by('-created_at')

        # Pagination
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))

        total = comments.count()
        comments_page = comments[offset:offset + limit]

        # Set current user for is_liked check
        serializer = PlaylistCommentSerializer(
            comments_page,
            many=True,
            context={'request': request}
        )

        return SuccessResponse(
            data={
                'playlist_id': playlist_id,
                'total': total,
                'limit': limit,
                'offset': offset,
                'comments': serializer.data
            },
            message=f'Retrieved {len(serializer.data)} comments'
        )

    @extend_schema(
        tags=["Playlists"],
        summary="Create playlist comment",
        description="Posts a new comment on a playlist. Can be a top-level comment or a reply to an existing comment. Replies support up to 2 levels of nesting (comment → reply → reply to reply). Comments are permanently associated with the playlist and cannot be moved. The authenticated user automatically becomes the comment author. Only public playlists or your own playlists can be commented on.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the playlist to comment on',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'required': ['content'],
                'properties': {
                    'content': {
                        'type': 'string',
                        'description': 'Comment text content (cannot be empty or whitespace only)',
                        'minLength': 1,
                        'maxLength': 2000,
                        'example': 'This playlist is amazing! Great song selection.'
                    },
                    'parent_id': {
                        'type': 'integer',
                        'description': 'Parent comment ID if this is a reply (optional)',
                        'example': 5001
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Top-level comment',
                description='Post a new comment on the playlist',
                value={'content': 'Great playlist! Thanks for sharing.'}
            ),
            OpenApiExample(
                'Reply to comment',
                description='Post a reply to an existing comment',
                value={
                    'content': 'I agree! The flow is perfect.',
                    'parent_id': 5001
                }
            )
        ],
        responses={
            201: {
                'type': 'object',
                'examples': {
                    'comment_created': {
                        'summary': 'Comment posted successfully',
                        'value': {
                            'success': True,
                            'message': 'Comment created successfully',
                            'data': {
                                'id': 5002,
                                'content': 'Great playlist! Thanks for sharing.',
                                'user_id': 10,
                                'username': 'musicfan123',
                                'parent_id': None,
                                'replies_count': 0,
                                'likes_count': 0,
                                'is_liked': False,
                                'created_at': '2026-04-07T18:50:00Z',
                                'updated_at': '2026-04-07T18:50:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'empty_content': {
                        'summary': 'Content is empty or whitespace',
                        'value': {
                            'success': False,
                            'message': 'Comment content is required',
                            'errors': {
                                'content': ['This field is required and cannot be empty']
                            }
                        }
                    },
                    'max_reply_level': {
                        'summary': 'Cannot reply to a reply (max 2 levels)',
                        'value': {
                            'success': False,
                            'message': 'Cannot reply to a reply',
                            'errors': {
                                'parent_id': ['Cannot reply to a reply (max 2 levels)']
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Cannot comment on private playlist',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to comment on this playlist'
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
                    'parent_not_found': {
                        'summary': 'Parent comment does not exist',
                        'value': {
                            'success': False,
                            'message': 'Parent comment not found'
                        }
                    }
                }
            }
        }
    )
    def post(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization: can comment on public playlists or own playlists
        if not user_can_access_playlist(playlist, request.user.id, request.META.get('HTTP_AUTHORIZATION', '')):
            return ForbiddenResponse(message='Not authorized to comment on this playlist')

        content = request.data.get('content')
        if not content or not content.strip():
            return ValidationErrorResponse(
                errors={'content': 'This field is required and cannot be empty'},
                message='Comment content is required'
            )

        parent_id = request.data.get('parent_id')

        # Validate parent_id if provided
        if parent_id:
            try:
                parent_comment = PlaylistComment.objects.get(
                    id=parent_id,
                    playlist_id=playlist_id,
                    is_deleted=False
                )
                # Don't allow replying to replies (max 2 levels)
                if parent_comment.parent_id is not None:
                    return ValidationErrorResponse(
                        errors={'parent_id': 'Cannot reply to a reply (max 2 levels)'},
                        message='Cannot reply to a reply'
                    )
            except PlaylistComment.DoesNotExist:
                return NotFoundResponse(message='Parent comment not found')

        # Create comment
        comment = PlaylistComment.objects.create(
            playlist_id=playlist_id,
            user_id=request.user.id,
            parent_id=parent_id,
            content=content.strip()
        )

        serializer = PlaylistCommentSerializer(
            comment,
            context={'request': request}
        )

        return SuccessResponse(
            data=serializer.data,
            message='Comment created successfully',
            status_code=201
        )


class CommentDetailView(APIView):
    """
    GET /api/comments/{id}/

    Get a single comment with its replies

    PATCH /api/comments/{id}/

    Update a comment (content only):
    - Only by comment author
    - Sets is_edited flag

    DELETE /api/comments/{id}/

    Soft delete a comment:
    - Only by comment author
    - Sets is_deleted flag (content remains but marked as deleted)
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Get comment details",
        description="Returns detailed information about a specific comment including the comment content, author information, likes count, edit status, and all replies. Comments are only accessible if you can access the associated playlist. Deleted comments return 404.",
        parameters=[
            OpenApiParameter(
                name='comment_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the comment',
                required=True,
                example=5001
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'comment_found': {
                        'summary': 'Comment retrieved successfully',
                        'value': {
                            'success': True,
                            'message': 'Comment retrieved successfully',
                            'data': {
                                'id': 5001,
                                'content': 'This playlist is amazing!',
                                'user_id': 10,
                                'username': 'musicfan123',
                                'parent_id': None,
                                'replies_count': 2,
                                'likes_count': 5,
                                'is_liked': False,
                                'is_edited': False,
                                'created_at': '2026-04-07T14:30:00Z',
                                'updated_at': '2026-04-07T14:30:00Z',
                                'replies': [
                                    {
                                        'id': 5002,
                                        'content': 'I agree!',
                                        'user_id': 15,
                                        'likes_count': 3
                                    }
                                ]
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Cannot access comment (playlist is private)',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to view this comment'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'comment_not_found': {
                        'summary': 'Comment does not exist or was deleted',
                        'value': {
                            'success': False,
                            'message': 'Comment not found'
                        }
                    }
                }
            }
        }
    )
    def get(self, request, comment_id):
        try:
            comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Check playlist access
        try:
            playlist = Playlist.objects.get(id=comment.playlist_id)
            if not user_can_access_playlist(playlist, request.user.id, request.META.get('HTTP_AUTHORIZATION', '')):
                return ForbiddenResponse(message='Not authorized to view this comment')
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        serializer = PlaylistCommentSerializer(
            comment,
            context={'request': request}
        )

        return SuccessResponse(
            data=serializer.data,
            message='Comment retrieved successfully'
        )

    @extend_schema(
        tags=["Playlists"],
        summary="Update comment",
        description="Updates the content of an existing comment. Only the comment author can edit their own comments. The comment is permanently marked as edited (is_edited flag) and the update timestamp is refreshed. Original content is not preserved. Only the content field can be modified - parent_id and other fields cannot be changed.",
        parameters=[
            OpenApiParameter(
                name='comment_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the comment to update',
                required=True,
                example=5001
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'required': ['content'],
                'properties': {
                    'content': {
                        'type': 'string',
                        'description': 'New comment content (replaces existing content)',
                        'minLength': 1,
                        'maxLength': 2000,
                        'example': 'Updated comment text with corrections.'
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Edit comment',
                description='Update an existing comment',
                value={'content': 'Revised my thoughts on this playlist.'}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'updated': {
                        'summary': 'Comment updated successfully',
                        'value': {
                            'success': True,
                            'message': 'Comment updated successfully',
                            'data': {
                                'id': 5001,
                                'content': 'Revised my thoughts on this playlist.',
                                'user_id': 10,
                                'is_edited': True,
                                'updated_at': '2026-04-07T19:00:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'empty_content': {
                        'summary': 'Content is empty or whitespace',
                        'value': {
                            'success': False,
                            'message': 'Comment content is required',
                            'errors': {
                                'content': ['This field is required and cannot be empty']
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Only the comment author can edit',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to edit this comment'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'comment_not_found': {
                        'summary': 'Comment does not exist or was deleted',
                        'value': {
                            'success': False,
                            'message': 'Comment not found'
                        }
                    }
                }
            }
        }
    )
    def patch(self, request, comment_id):
        try:
            comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Check moderation permissions
        try:
            playlist = Playlist.objects.get(id=comment.playlist_id)
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not user_can_moderate_comment(playlist, comment, request.user.id, auth_header):
                return ForbiddenResponse(message='Not authorized to edit this comment')
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        content = request.data.get('content')
        if not content or not content.strip():
            return ValidationErrorResponse(
                errors={'content': 'This field is required and cannot be empty'},
                message='Comment content is required'
            )

        # Update comment
        comment.content = content.strip()
        comment.is_edited = True
        comment.save()

        serializer = PlaylistCommentSerializer(
            comment,
            context={'request': request}
        )

        return SuccessResponse(
            data=serializer.data,
            message='Comment updated successfully'
        )

    @extend_schema(
        tags=["Playlists"],
        summary="Delete comment",
        description="Soft deletes a comment by marking it as deleted. The comment content remains in the database but is filtered out from views. Only the comment author can delete their own comments. This operation is irreversible - comments cannot be undeleted. Replies to the deleted comment remain visible. The comment ID is preserved for referential integrity.",
        parameters=[
            OpenApiParameter(
                name='comment_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the comment to delete',
                required=True,
                example=5001
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'deleted_successfully': {
                        'summary': 'Comment soft deleted successfully',
                        'value': {
                            'success': True,
                            'message': 'Comment deleted successfully'
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Only the comment author can delete',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to delete this comment'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'comment_not_found': {
                        'summary': 'Comment does not exist or was already deleted',
                        'value': {
                            'success': False,
                            'message': 'Comment not found'
                        }
                    }
                }
            }
        }
    )
    def delete(self, request, comment_id):
        try:
            comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Check moderation permissions
        try:
            playlist = Playlist.objects.get(id=comment.playlist_id)
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not user_can_moderate_comment(playlist, comment, request.user.id, auth_header):
                return ForbiddenResponse(message='Not authorized to delete this comment')
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Soft delete
        comment.is_deleted = True
        comment.save()

        return SuccessResponse(
            message='Comment deleted successfully'
        )


class CommentRepliesView(APIView):
    """
    GET /api/comments/{id}/replies/

    Get all replies to a comment:
    - Direct replies only (one level deep)
    - Sorted by most recent first
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Playlists"],
        summary="Get comment replies",
        description="Returns all direct replies to a specific comment. Only shows one level of nesting (direct replies to the parent, not replies to replies). Replies are sorted by most recent first. Only accessible if you can view the associated playlist. This endpoint is useful for expanding comment threads and showing conversation history.",
        parameters=[
            OpenApiParameter(
                name='comment_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the parent comment',
                required=True,
                example=5001
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'replies_found': {
                        'summary': 'Replies retrieved successfully',
                        'value': {
                            'success': True,
                            'message': 'Retrieved 3 replies',
                            'data': {
                                'comment_id': 5001,
                                'total': 3,
                                'replies': [
                                    {
                                        'id': 5002,
                                        'content': 'I agree with this!',
                                        'user_id': 15,
                                        'username': 'user15',
                                        'parent_id': 5001,
                                        'likes_count': 2,
                                        'created_at': '2026-04-07T15:00:00Z'
                                    },
                                    {
                                        'id': 5003,
                                        'content': 'Same here!',
                                        'user_id': 20,
                                        'username': 'user20',
                                        'parent_id': 5001,
                                        'likes_count': 1,
                                        'created_at': '2026-04-07T15:05:00Z'
                                    }
                                ]
                            }
                        }
                    },
                    'no_replies': {
                        'summary': 'No replies to this comment',
                        'value': {
                            'success': True,
                            'message': 'Retrieved 0 replies',
                            'data': {
                                'comment_id': 5001,
                                'total': 0,
                                'replies': []
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'Cannot access replies (playlist is private)',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to view replies'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'comment_not_found': {
                        'summary': 'Comment does not exist or was deleted',
                        'value': {
                            'success': False,
                            'message': 'Comment not found'
                        }
                    }
                }
            }
        }
    )
    def get(self, request, comment_id):
        try:
            parent_comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Check playlist access
        try:
            playlist = Playlist.objects.get(id=parent_comment.playlist_id)
            if not user_can_access_playlist(playlist, request.user.id, request.META.get('HTTP_AUTHORIZATION', '')):
                return ForbiddenResponse(message='Not authorized to view replies')
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Get replies
        replies = PlaylistComment.objects.filter(
            parent_id=comment_id,
            is_deleted=False
        ).order_by('-created_at')

        serializer = PlaylistCommentSerializer(
            replies,
            many=True,
            context={'request': request}
        )

        return SuccessResponse(
            data={
                'comment_id': comment_id,
                'total': replies.count(),
                'replies': serializer.data
            },
            message=f'Retrieved {replies.count()} replies'
        )


class CommentLikeView(APIView):
    """
    POST /api/comments/{id}/like/

    Like a comment:
    - Idempotent (can like again without error)
    - Increments likes_count

    DELETE /api/comments/{id}/like/

    Unlike a comment:
    - Decrements likes_count
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Comments"],
        summary="Like a comment",
        description="Likes a comment on a playlist. This operation is idempotent - if the user has already liked the comment, the request will succeed without creating a duplicate like. Users cannot like their own comments. The comment's likes_count is incremented when a new like is created. Only users with access to the playlist (public playlists or authorized users) can like comments.",
        parameters=[
            OpenApiParameter(
                name='comment_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the comment to like',
                required=True,
                example=456
            )
        ],
        responses={
            201: {
                'type': 'object',
                'examples': {
                    'comment_liked': {
                        'summary': 'Comment liked successfully',
                        'value': {
                            'success': True,
                            'message': 'Comment liked successfully',
                            'data': {
                                'id': 789,
                                'comment_id': 456,
                                'user_id': 1,
                                'created_at': '2026-04-07T12:00:00Z'
                            }
                        }
                    },
                    'already_liked': {
                        'summary': 'User already liked this comment (idempotent)',
                        'value': {
                            'success': True,
                            'message': 'Already liked this comment',
                            'data': {
                                'id': 789,
                                'comment_id': 456,
                                'user_id': 1,
                                'created_at': '2026-04-07T11:00:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'own_comment': {
                        'summary': 'Cannot like own comment',
                        'value': {
                            'success': False,
                            'message': 'Cannot like your own comment'
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_authorized': {
                        'summary': 'No access to playlist',
                        'value': {
                            'success': False,
                            'message': 'Not authorized to like comments on this playlist'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'comment_not_found': {
                        'summary': 'Comment ID does not exist or is deleted',
                        'value': {
                            'success': False,
                            'message': 'Comment not found'
                        }
                    }
                }
            }
        }
    )
    def post(self, request, comment_id):
        try:
            comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Check playlist access
        try:
            playlist = Playlist.objects.get(id=comment.playlist_id)
            if not user_can_access_playlist(playlist, request.user.id, request.META.get('HTTP_AUTHORIZATION', '')):
                return ForbiddenResponse(message='Not authorized to like comments on this playlist')
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Cannot like own comments
        if comment.user_id == request.user.id:
            return ValidationErrorResponse(
                message='Cannot like your own comment'
            )

        # Create like (idempotent)
        like, created = PlaylistCommentLike.objects.get_or_create(
            comment_id=comment_id,
            user_id=request.user.id
        )

        if created:
            # Increment likes count
            comment.likes_count += 1
            comment.save()

        serializer = PlaylistCommentLikeSerializer(like)

        return SuccessResponse(
            data=serializer.data,
            message='Comment liked successfully' if created else 'Already liked this comment',
            status_code=201 if created else 200
        )

    @extend_schema(
        tags=["Comments"],
        summary="Unlike a comment",
        description="Removes the user's like from a comment. This operation is idempotent - if the user was not liking the comment, the request will succeed without error. The comment's likes_count is decremented when a like is removed (never goes below 0). No authentication error is raised if the user was not liking the comment.",
        parameters=[
            OpenApiParameter(
                name='comment_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the comment to unlike',
                required=True,
                example=456
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'comment_unliked': {
                        'summary': 'Comment unliked successfully',
                        'value': {
                            'success': True,
                            'message': 'Comment unliked successfully'
                        }
                    },
                    'not_liking': {
                        'summary': 'User was not liking this comment (idempotent)',
                        'value': {
                            'success': True,
                            'message': 'Not liking this comment'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'comment_not_found': {
                        'summary': 'Comment ID does not exist or is deleted',
                        'value': {
                            'success': False,
                            'message': 'Comment not found'
                        }
                    }
                }
            }
        }
    )
    def delete(self, request, comment_id):
        try:
            comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Delete like
        deleted_count, _ = PlaylistCommentLike.objects.filter(
            comment_id=comment_id,
            user_id=request.user.id
        ).delete()

        if deleted_count > 0:
            # Decrement likes count
            comment.likes_count = max(0, comment.likes_count - 1)
            comment.save()

        return SuccessResponse(
            message='Comment unliked successfully' if deleted_count > 0 else 'Not liking this comment'
        )
