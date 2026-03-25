from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Q
from django.db import connection
from .models import Song

from .serializers import SongSerializer

class SearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '')
        if not query:
            return Response([])
        results = Song.objects.filter(
            Q(title__icontains=query) |
            Q(artist__icontains=query) |
            Q(album__icontains=query)
        )[:20]
        serializer = SongSerializer(results, many=True)
        return Response(serializer.data)

class BrowseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        genres = Song.objects.values_list('genre', flat=True).distinct()
        return Response(list(genres))

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
            'service': 'search',
            'database': 'connected'
        }, status=200)
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'service': 'search',
            'database': 'disconnected',
            'error': str(e)
        }, status=503)
