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
        description="Redoes an action that was previously undone. The action must have been undone first and must be within the redo window. Common redoable actions: undoing track addition, undoing playlist creation, undoing track removal.",
        parameters=[
            OpenApiParameter(
                name='action_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Action ID to redo (from your undo history)',
                required=True,
                example=456
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'redo_success': {
                        'summary': 'Action successfully redone',
                        'value': {
                            'success': True,
                            'message': 'Action redone successfully',
                            'data': {
                                'action_id': 456,
                                'action_type': 'undo_add_track',
                                'redone_at': '2026-04-07T18:40:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'not_undone': {
                        'summary': 'Action has not been undone',
                        'value': {
                            'success': False,
                            'message': 'Action cannot be redone (it was never undone)',
                            'error': 'not_undone'
                        }
                    },
                    'expired': {
                        'summary': 'Redo window expired',
                        'value': {
                            'success': False,
                            'message': 'Redo window has expired (24 hours)',
                            'error': 'expired'
                        }
                    },
                    'not_redoable': {
                        'summary': 'Action type cannot be redone',
                        'value': {
                            'success': False,
                            'message': 'This action type cannot be redone',
                            'error': 'not_redoable'
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
        description="Returns your recent actions that can be undone/redone. Actions are ordered by most recent first. This is your action history for undo/redo functionality. Common action types: add_track, remove_track, create_playlist, delete_playlist.",
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of actions to return (max 100, default 50)',
                required=False,
                example=50
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
                        'example': 'Retrieved 25 recent actions'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'actions': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer', 'example': 789},
                                        'action_type': {
                                            'type': 'string',
                                            'description': 'Type of action performed',
                                            'example': 'add_track'
                                        },
                                        'description': {
                                            'type': 'string',
                                            'description': 'Human-readable description of what was done',
                                            'example': 'Added "Bohemian Rhapsody" to playlist'
                                        },
                                        'created_at': {
                                            'type': 'string',
                                            'format': 'date-time',
                                            'description': 'When the action was performed',
                                            'example': '2026-04-07T18:00:00Z'
                                        },
                                        'can_undo': {
                                            'type': 'boolean',
                                            'description': 'Whether this action can still be undone',
                                            'example': True
                                        },
                                        'undone_at': {
                                            'type': 'string',
                                            'format': 'date-time',
                                            'description': 'When the action was undone (null if not undone)',
                                            'example': None
                                        }
                                    }
                                },
                                'description': 'List of recent actions, most recent first'
                            },
                            'total': {
                                'type': 'integer',
                                'description': 'Total number of actions in your history',
                                'example': 25
                            },
                            'undoable_count': {
                                'type': 'integer',
                                'description': 'Number of actions that can currently be undone',
                                'example': 18
                            }
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
        description="Returns a list of actions that can still be undone. Actions are undoable if they're within the undo window (default 24 hours) and haven't been undone already. Useful for showing undo options in the UI.",
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of actions to return (max 100, default 50)',
                required=False,
                example=20
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
                        'example': 'Found 18 undoable actions'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'undoable_actions': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer', 'example': 789},
                                        'action_type': {
                                            'type': 'string',
                                            'example': 'add_track'
                                        },
                                        'description': {
                                            'type': 'string',
                                            'example': 'Added "Bohemian Rhapsody" to playlist'
                                        },
                                        'created_at': {
                                            'type': 'string',
                                            'format': 'date-time',
                                            'example': '2026-04-07T17:00:00Z'
                                        },
                                        'undo_deadline': {
                                            'type': 'string',
                                            'format': 'date-time',
                                            'description': 'When this action can no longer be undone',
                                            'example': '2026-04-08T17:00:00Z'
                                        }
                                    }
                                },
                                'description': 'Actions that can still be undone, ordered by most recent first'
                            },
                            'total': {
                                'type': 'integer',
                                'description': 'Number of actions currently undoable',
                                'example': 18
                            }
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
        description="Returns your current undo/redo configuration including undo window duration and enabled status. Configuration is auto-created on first access if not set.",
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
                        'example': 'Configuration retrieved successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'user_id': {'type': 'integer', 'example': 1},
                            'undo_window_hours': {
                                'type': 'integer',
                                'description': 'How long after an action it can be undone (in hours)',
                                'example': 24
                            },
                            'max_actions': {
                                'type': 'integer',
                                'description': 'Maximum number of actions stored in history',
                                'example': 100
                            },
                            'is_enabled': {
                                'type': 'boolean',
                                'description': 'Whether undo/redo functionality is enabled for your account',
                                'example': True
                            },
                            'created_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-01T10:00:00Z'
                            },
                            'updated_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-07T12:00:00Z'
                            }
                        }
                    }
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
        description="Update your undo/redo preferences. Configure how long actions can be undone (window duration) and maximum actions to store. All fields optional - update only what you want to change.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'undo_window_hours': {
                        'type': 'integer',
                        'description': 'How long after an action it can be undone (1-168 hours, default 24)',
                        'minimum': 1,
                        'maximum': 168,
                        'example': 48
                    },
                    'max_actions': {
                        'type': 'integer',
                        'description': 'Maximum number of actions to store in history (1-1000, default 100)',
                        'minimum': 1,
                        'maximum': 1000,
                        'example': 200
                    },
                    'is_enabled': {
                        'type': 'boolean',
                        'description': 'Enable or disable undo/redo functionality',
                        'example': True
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Extend undo window',
                description='Extend the undo window from 24 hours to 48 hours',
                value={'undo_window_hours': 48}
            ),
            OpenApiExample(
                'Increase history limit',
                description='Store more actions in history',
                value={'max_actions': 200}
            ),
            OpenApiExample(
                'Disable undo/redo',
                description='Turn off undo/redo functionality',
                value={'is_enabled': False}
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
                        'example': 'Configuration updated successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'user_id': {'type': 'integer', 'example': 1},
                            'undo_window_hours': {'type': 'integer', 'example': 48},
                            'max_actions': {'type': 'integer', 'example': 200},
                            'is_enabled': {'type': 'boolean', 'example': True},
                            'updated_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-07T19:00:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'invalid_window': {
                        'summary': 'Undo window out of range',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'undo_window_hours': ['Must be between 1 and 168 hours']
                            }
                        }
                    },
                    'invalid_max_actions': {
                        'summary': 'Max actions out of range',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'max_actions': ['Must be between 1 and 1000']
                            }
                        }
                    }
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
