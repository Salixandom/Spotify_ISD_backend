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

from .models import Play
from searchapp.models import Song
from searchapp.serializers import SongSerializer


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
