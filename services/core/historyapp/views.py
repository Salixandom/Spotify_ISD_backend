from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes

from utils.responses import (
    SuccessResponse,
    ErrorResponse,
    NotFoundResponse,
    ForbiddenResponse,
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

    def get(self, request):
        config, created = UndoRedoConfiguration.objects.get_or_create(
            user_id=request.user.id
        )
        serializer = UndoRedoConfigurationSerializer(config)
        return SuccessResponse(
            data=serializer.data,
            message='Configuration retrieved successfully'
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
