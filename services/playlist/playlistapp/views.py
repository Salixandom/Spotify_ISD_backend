from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.db import connection
from .models import Playlist
from .serializers import PlaylistSerializer


class PlaylistViewSet(viewsets.ModelViewSet):
    serializer_class = PlaylistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Playlist.objects.filter(owner_id=self.request.user.id)

    def perform_create(self, serializer):
        serializer.save(owner_id=self.request.user.id)

    def update(self, request, *args, **kwargs):
        playlist = self.get_object()
        if playlist.owner_id != request.user.id:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        playlist = self.get_object()
        if playlist.owner_id != request.user.id:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

from rest_framework.decorators import api_view, permission_classes


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint"""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return Response({
            'status': 'healthy',
            'service': 'playlist',
            'database': 'connected'
        }, status=200)
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'service': 'playlist',
            'database': 'disconnected',
            'error': str(e)
        }, status=503)
