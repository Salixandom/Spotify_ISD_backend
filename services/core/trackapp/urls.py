from django.urls import path
from .views import TrackListView, TrackDetailView, TrackReorderView, health_check

urlpatterns = [
    path('health/', health_check),
    path('<int:playlist_id>/', TrackListView.as_view()),
    path('<int:playlist_id>/<int:track_id>/', TrackDetailView.as_view()),
    path('<int:playlist_id>/reorder/', TrackReorderView.as_view()),
]

