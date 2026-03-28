from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from django.db import connection

from .models import Play
from searchapp.models import Song
from searchapp.serializers import SongSerializer


class RecordPlayView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        song_id = request.data.get("song_id")
        if not song_id:
            return Response(
                {"error": "song_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            song = Song.objects.get(id=song_id)
            Play.objects.create(user_id=request.user.id, song=song)
            return Response({"status": "recorded"}, status=status.HTTP_201_CREATED)
        except Song.DoesNotExist:
            return Response(
                {"error": "Song not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


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

        return Response(SongSerializer(recent, many=True).data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint for monitoring and orchestration."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return Response(
            {
                "status": "healthy",
                "service": "history",
                "database": "connected",
            },
            status=200,
        )
    except Exception as e:
        return Response(
            {
                "status": "unhealthy",
                "service": "history",
                "database": "disconnected",
                "error": str(e),
            },
            status=503,
        )
