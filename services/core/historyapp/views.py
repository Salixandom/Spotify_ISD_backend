from rest_framework.views import APIView
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from utils.responses import (
    SuccessResponse,
    ErrorResponse,
    NotFoundResponse,
    ValidationErrorResponse,
    ServiceUnavailableResponse,
)
from django.db import connection

from .models import Play, UserAction, UndoRedoConfiguration
from searchapp.models import Song
from searchapp.serializers import SongSerializer
from .serializers import UserActionSerializer, UndoRedoConfigurationSerializer
from .services import UndoRedoService
from django.utils import timezone
from django.db.models import Q


class RecordPlayView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["History"],
        summary="Record song play",
        description="Records a play event for a song. Used for tracking listening history and enabling features like recently played, undo, and recommendations. Each play creates a timestamped record.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'song_id': {
                        'type': 'integer',
                        'description': 'Song ID that was played',
                        'example': 456
                    }
                },
                'required': ['song_id']
            }
        },
        examples=[
            OpenApiExample(
                'Record play',
                description='Record that a song was played',
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
                        'example': 'Play recorded successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'status': {
                                'type': 'string',
                                'example': 'recorded'
                            },
                            'played_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'description': 'Timestamp when the play was recorded',
                                'example': '2026-04-07T18:30:00Z'
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
                                'song_id': ['This field is required.']
                            }
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Song not found'
                }
            }
        }
    )
    def post(self, request):
        song_id = request.data.get("song_id")
        if not song_id:
            return ValidationErrorResponse(
                errors={'song_id': 'This field is required'},
                message='song_id required'
            )
        try:
            song = Song.objects.get(id=song_id)
            Play.objects.create(user_id=request.user.id, song=song)
            return SuccessResponse(
                data={'status': 'recorded'},
                message='Play recorded successfully',
                status_code=201
            )
        except Song.DoesNotExist:
            return NotFoundResponse(message='Song not found')


class RecentPlaysView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["History"],
        summary="Get recently played songs",
        description="Returns your recently played songs. Each song appears only once (most recent play determines position). Results are ordered by most recently played first. Maximum 10 songs returned.",
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
                        'example': 'Retrieved 10 recently played songs'
                    },
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer', 'example': 1},
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
                                'genre': {'type': 'string', 'example': 'Rock'},
                                'last_played_at': {
                                    'type': 'string',
                                    'format': 'date-time',
                                    'description': 'When this song was last played',
                                    'example': '2026-04-07T18:25:00Z'
                                }
                            }
                        },
                        'description': 'Recently played songs, most recent first (max 10)'
                    }
                }
            }
        }
    )
    def get(self, request):
        seen = set()
        recent = []

        plays = (
            Play.objects.filter(user_id=request.user.id)
            .select_related("song", "song__artist", "song__album")
            .order_by("-played_at")
        )

        for play in plays:
            if play.song_id not in seen:
                seen.add(play.song_id)
                recent.append(play.song)
            if len(recent) >= 10:
                break

        return SuccessResponse(
            data=SongSerializer(recent, many=True).data,
            message=f'Retrieved {len(recent)} recently played songs'
        )


class UndoActionView(APIView):
    """Undo a specific action"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["History"],
        summary="Undo an action",
        description="Reverses a previously performed action. Actions can only be undone if they're within the undo window (configurable, default 24 hours) and haven't been undone already. Common undoable actions: adding tracks to playlist, creating playlists, deleting tracks.",
        parameters=[
            OpenApiParameter(
                name='action_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Action ID to undo (from your action history)',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'undo_success': {
                        'summary': 'Action successfully undone',
                        'value': {
                            'success': True,
                            'message': 'Action undone successfully',
                            'data': {
                                'action_id': 123,
                                'action_type': 'add_track',
                                'undone_at': '2026-04-07T18:35:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'already_undone': {
                        'summary': 'Action already undone',
                        'value': {
                            'success': False,
                            'message': 'Action has already been undone',
                            'error': 'already_undone'
                        }
                    },
                    'expired': {
                        'summary': 'Undo window expired',
                        'value': {
                            'success': False,
                            'message': 'Undo window has expired (24 hours)',
                            'error': 'expired'
                        }
                    },
                    'not_undoable': {
                        'summary': 'Action type cannot be undone',
                        'value': {
                            'success': False,
                            'message': 'This action type cannot be undone',
                            'error': 'not_undoable'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Action not found'
                }
            }
        }
    )
    def post(self, request, action_id):
        result = UndoRedoService.undo_action(request.user.id, action_id)

        if result['success']:
            return SuccessResponse(
                data=result,
                message=result.get('message', 'Action undone successfully')
            )
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get('status') == 'not_found':
                status_code = status.HTTP_404_NOT_FOUND
            return ErrorResponse(
                error=result.get('error', 'Undo failed'),
                message=result.get('error', 'Failed to undo action'),
                status_code=status_code
            )


class RedoActionView(APIView):
    """Redo a previously undone action"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["History"],
        summary="Redo an action",
        description="Redoes an action that was previously undone.",
        parameters=[
            OpenApiParameter(
                name='action_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Action ID to redo',
                required=True
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
                            'success': {'type': 'boolean'},
                            'message': {'type': 'string'}
                        }
                    }
                }
            },
            400: {
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
    def post(self, request, action_id):
        result = UndoRedoService.redo_action(request.user.id, action_id)

        if result['success']:
            return SuccessResponse(
                data=result,
                message=result.get('message', 'Action redone successfully')
            )
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get('status') == 'not_found':
                status_code = status.HTTP_404_NOT_FOUND
            return ErrorResponse(
                error=result.get('error', 'Redo failed'),
                message=result.get('error', 'Failed to redo action'),
                status_code=status_code
            )


class UserActionsView(APIView):
    """List user's actions"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["History"],
        summary="List user actions",
        description="Returns a list of user's recent actions for undo/redo functionality.",
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of actions to return',
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
                            'actions': {
                                'type': 'array',
                                'items': UserActionSerializer
                            },
                            'total': {'type': 'integer'}
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        limit = int(request.query_params.get('limit', 50))

        actions = UserAction.objects.filter(
            user_id=request.user.id
        ).order_by('-created_at')[:limit]

        serializer = UserActionSerializer(actions, many=True)
        return SuccessResponse(
            data={
                'actions': serializer.data,
                'total': actions.count()
            },
            message=f'Retrieved {actions.count()} recent actions'
        )


class UndoableActionsView(APIView):
    """List actions that can be undone"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["History"],
        summary="List undoable actions",
        description="Returns a list of actions that can still be undone (within undo window and not already undone).",
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of actions to return',
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
                            'undoable_actions': {
                                'type': 'array',
                                'items': UserActionSerializer
                            },
                            'total': {'type': 'integer'}
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        limit = int(request.query_params.get('limit', 50))

        actions = UserAction.objects.filter(
            user_id=request.user.id,
            is_undone=False,
            is_undoable=True
        ).filter(
            Q(undo_deadline__isnull=True) |
            Q(undo_deadline__gt=timezone.now())
        ).order_by('-created_at')[:limit]

        serializer = UserActionSerializer(actions, many=True)
        return SuccessResponse(
            data={
                'undoable_actions': serializer.data,
                'total': actions.count()
            },
            message=f'Found {actions.count()} undoable actions'
        )


class UndoRedoConfigView(APIView):
    """Get/update undo/redo configuration"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["History"],
        summary="Get undo/redo configuration",
        description="Returns the current undo/redo configuration for the authenticated user.",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': UndoRedoConfigurationSerializer
                }
            }
        }
    )
    def get(self, request):
        config, created = UndoRedoConfiguration.objects.get_or_create(
            user_id=request.user.id
        )
        serializer = UndoRedoConfigurationSerializer(config)
        return SuccessResponse(
            data=serializer.data,
            message='Configuration retrieved successfully'
        )

    @extend_schema(
        tags=["History"],
        summary="Update undo/redo configuration",
        description="Updates the undo/redo configuration for the authenticated user.",
        request=UndoRedoConfigurationSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': UndoRedoConfigurationSerializer
                }
            }
        }
    )
    def put(self, request):
        config, created = UndoRedoConfiguration.objects.get_or_create(
            user_id=request.user.id
        )

        config.undo_window_hours = request.data.get('undo_window_hours', config.undo_window_hours)
        config.max_actions = request.data.get('max_actions', config.max_actions)
        config.auto_cleanup = request.data.get('auto_cleanup', config.auto_cleanup)
        config.disabled_action_types = request.data.get('disabled_action_types', config.disabled_action_types)
        config.save()

        serializer = UndoRedoConfigurationSerializer(config)
        return SuccessResponse(
            data=serializer.data,
            message='Configuration updated successfully'
        )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@extend_schema(
    tags=["Health"],
    summary="History service health check",
    description="Check if the history service and database are healthy",
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
    """Health check endpoint for monitoring and orchestration."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return SuccessResponse(
            data={'status': 'healthy', 'service': 'history', 'database': 'connected'},
            message='Service is healthy'
        )
    except Exception as e:
        return ServiceUnavailableResponse(
            message=f'Database connection failed: {str(e)}'
        )
