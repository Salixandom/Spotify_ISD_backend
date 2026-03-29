from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PlaylistViewSet,
    health_check,
    PlaylistStatsView,
    FeaturedPlaylistsView,
    DuplicatePlaylistView,
    BatchDeleteView,
    BatchUpdateView,
    CoverUploadView,
    CoverDeleteView,
)

router = DefaultRouter()
router.register(r"", PlaylistViewSet, basename="playlist")

urlpatterns = [
    path("health/", health_check),
    path("<int:playlist_id>/stats/", PlaylistStatsView.as_view(), name="playlist-stats"),
    path("featured/", FeaturedPlaylistsView.as_view(), name="featured-playlists"),
    # Phase 2: Core Operations
    path("<int:playlist_id>/duplicate/", DuplicatePlaylistView.as_view(), name="playlist-duplicate"),
    path("batch-delete/", BatchDeleteView.as_view(), name="batch-delete"),
    path("batch-update/", BatchUpdateView.as_view(), name="batch-update"),
    path("<int:playlist_id>/cover/", CoverUploadView.as_view(), name="cover-upload"),
    path("", include(router.urls)),
]
