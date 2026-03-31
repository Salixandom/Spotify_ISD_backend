# Custom Token Refresh View for Standardized Response Format

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from django.contrib.auth import authenticate
from django.conf import settings

from utils.responses import (
    SuccessResponse,
    UnauthorizedResponse,
)

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer


class CustomTokenRefreshView(APIView):
    """
    Custom token refresh view that returns JWT tokens in our standardized response format.
    Wraps TokenRefreshView to match our SuccessResponse pattern.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = TokenRefreshSerializer(data=request.data)

        if not serializer.is_valid():
            return UnauthorizedResponse(
                message='Invalid or expired refresh token'
            )

        # Return in our standardized format
        return SuccessResponse(
            data=serializer.validated_data,
            message='Token refreshed successfully'
        )
