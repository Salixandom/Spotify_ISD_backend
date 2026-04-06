from django.urls import path, include
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import connection
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response(
            {
                "status": "healthy",
                "service": "core",
                "database": "connected",
                "apps": ["playlist", "track", "search", "history"],
            }
        )
    except Exception as e:
        return Response(
            {
                "status": "unhealthy",
                "service": "core",
                "database": "disconnected",
                "error": str(e),
            },
            status=503,
        )


urlpatterns = [
    path("api/playlists/", include("playlistapp.urls")),
    path("api/tracks/", include("trackapp.urls")),
    path("api/search/", include("searchapp.urls")),
    path("api/history/", include("historyapp.urls")),
    path("api/core/health/", health_check),
    # API documentation endpoints
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
