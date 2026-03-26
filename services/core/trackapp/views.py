from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from django.db import connection
from .models import Track
from .serializers import TrackSerializer


class TrackListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        tracks = Track.objects.filter(playlist_id=playlist_id).order_by("position")
        serializer = TrackSerializer(tracks, many=True)
        return Response(serializer.data)

    def post(self, request, playlist_id):
        data = request.data.copy()
        data["playlist_id"] = playlist_id
        data["added_by_id"] = request.user.id
        last = (
            Track.objects.filter(playlist_id=playlist_id).order_by("-position").first()
        )
        data["position"] = (last.position + 1) if last else 0
        serializer = TrackSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TrackDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, playlist_id, track_id):
        try:
            track = Track.objects.get(id=track_id, playlist_id=playlist_id)
            track.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Track.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class TrackReorderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, playlist_id):
        ordered_ids = request.data.get("track_ids", [])
        for index, track_id in enumerate(ordered_ids):
            Track.objects.filter(id=track_id, playlist_id=playlist_id).update(
                position=index
            )
        return Response({"status": "reordered"})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return Response(
            {"status": "healthy", "service": "track", "database": "connected"},
            status=200,
        )
    except Exception as e:
        return Response(
            {
                "status": "unhealthy",
                "service": "track",
                "database": "disconnected",
                "error": str(e),
            },
            status=503,
        )
