from django.urls import path
from .views import (
    TrackListView, TrackDetailView, TrackReorderRemoveView,
    TrackRemoveView, PlaylistArchiveView, TrackHideView,
    TrackSortView, health_check,
)

urlpatterns = [
    path("health/", health_check),
    path("<int:playlist_id>/", TrackListView.as_view()),
    path("<int:playlist_id>/remove/", TrackRemoveView.as_view()),
    path("<int:playlist_id>/archive/", PlaylistArchiveView.as_view()),
    path("<int:playlist_id>/reorder/", TrackReorderRemoveView.as_view()),
    path("<int:playlist_id>/sort/", TrackSortView.as_view()),
    path("<int:playlist_id>/<int:track_id>/", TrackDetailView.as_view()),
    path("<int:playlist_id>/<int:track_id>/hide/", TrackHideView.as_view()),
]
