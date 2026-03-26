from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from django.db import connection
from .models import ShareLink
from .serializers import ShareLinkSerializer


class CreateShareLinkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id):
        share = ShareLink.objects.create(
            playlist_id=playlist_id,
            created_by_id=request.user.id,
        )
        serializer = ShareLinkSerializer(share)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DeactivateShareLinkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, playlist_id):
        updated = ShareLink.objects.filter(
            playlist_id=playlist_id,
            is_active=True,
        ).update(is_active=False)
        if updated:
            return Response({"status": "deactivated"}, status=status.HTTP_200_OK)
        return Response(
            {"error": "No active share link found"},
            status=status.HTTP_404_NOT_FOUND,
        )


class ViewShareLinkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, token):
        try:
            share = ShareLink.objects.get(token=token)
        except ShareLink.DoesNotExist:
            return Response({"valid": False}, status=status.HTTP_404_NOT_FOUND)

        if not share.is_valid:
            return Response(
                {"valid": False, "error": "Share link is inactive or expired"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ShareLinkSerializer(share)
        return Response(
            {
                "valid": True,
                "playlist_id": share.playlist_id,
                "share": serializer.data,
            }
        )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint for monitoring and orchestration."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return Response(
            {"status": "healthy", "service": "share", "database": "connected"},
            status=200,
        )
    except Exception as e:
        return Response(
            {
                "status": "unhealthy",
                "service": "share",
                "database": "disconnected",
                "error": str(e),
            },
            status=503,
        )
