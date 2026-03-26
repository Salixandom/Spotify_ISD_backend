from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from .serializers import RegisterSerializer, UserSerializer
from django.db import connection


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring and orchestration
    Returns 200 if service and database are healthy
    """
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        return Response(
            {"status": "healthy", "service": "auth", "database": "connected"},
            status=200,
        )
    except Exception as e:
        return Response(
            {
                "status": "unhealthy",
                "service": "auth",
                "database": "disconnected",
                "error": str(e),
            },
            status=503,
        )
