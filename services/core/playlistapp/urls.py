from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PlaylistViewSet,
    health_check,
    PlaylistStatsView,
    FeaturedPlaylistsView,
)

router = DefaultRouter()
router.register(r"", PlaylistViewSet, basename="playlist")

urlpatterns = [
    path("health/", health_check),
    path("<int:playlist_id>/stats/", PlaylistStatsView.as_view(), name="playlist-stats"),
    path("featured/", FeaturedPlaylistsView.as_view(), name="featured-playlists"),
    path("", include(router.urls)),
]
