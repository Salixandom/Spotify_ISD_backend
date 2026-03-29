from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes

from utils.responses import (
    SuccessResponse,
    NotFoundResponse,
    ServiceUnavailableResponse,
)
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
        return SuccessResponse(
            data=ShareLinkSerializer(share).data,
            message='Share link created successfully',
            status_code=201
        )


class ViewShareLinkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, token):
        try:
            share = ShareLink.objects.get(token=token)
        except ShareLink.DoesNotExist:
            return NotFoundResponse(message='Invalid link')

        if not share.is_valid:
            return NotFoundResponse(message='Share link is expired')

        return SuccessResponse(
            data={
                'valid': True,
                'playlist_id': share.playlist_id,
                'share': ShareLinkSerializer(share).data,
            },
            message='Share link is valid'
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return SuccessResponse(
            data={'status': 'healthy', 'service': 'share', 'database': 'connected'},
            message='Service is healthy'
        )
    except Exception as e:
        return ServiceUnavailableResponse(
            message=f'Database connection failed: {str(e)}'
        )
