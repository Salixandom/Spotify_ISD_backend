from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlaylistViewSet, health_check

router = DefaultRouter()
router.register(r"", PlaylistViewSet, basename="playlist")

urlpatterns = [
    path("health/", health_check),
    path("", include(router.urls)),
]
