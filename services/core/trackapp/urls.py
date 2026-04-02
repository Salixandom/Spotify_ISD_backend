from django.urls import path
from .views import (
    TrackListView, TrackDetailView, TrackReorderRemoveView,
    TrackRemoveView, PlaylistArchiveView, TrackHideView,
    TrackSortView, health_check,
)

urlpatterns = [
    path("health/", health_check, name="track-health"),
    path("<int:playlist_id>/", TrackListView.as_view(), name="track-list"),
    path("<int:playlist_id>/remove/", TrackRemoveView.as_view(), name="track-remove"),
    path("<int:playlist_id>/archive/", PlaylistArchiveView.as_view(), name="playlist-archive"),
    path("<int:playlist_id>/reorder/", TrackReorderRemoveView.as_view(), name="track-reorder"),
    path("<int:playlist_id>/sort/", TrackSortView.as_view(), name="track-sort"),
    path("<int:playlist_id>/<int:track_id>/", TrackDetailView.as_view(), name="track-detail"),
    path("<int:playlist_id>/<int:track_id>/hide/", TrackHideView.as_view(), name="track-hide"),
]
