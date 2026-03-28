from django.urls import path
from .views import (
    SearchView, BrowseView,
    SongSearchView, PlaylistSearchView,
    ArtistListView, ArtistDetailView,
    AlbumListView, AlbumDetailView,
    health_check,
)

urlpatterns = [
    path('health/', health_check),
    path('', SearchView.as_view()),
    path('songs/', SongSearchView.as_view()),
    path('playlists/', PlaylistSearchView.as_view()),
    path('browse/', BrowseView.as_view()),
    path('artists/', ArtistListView.as_view()),
    path('artists/<int:artist_id>/', ArtistDetailView.as_view()),
    path('albums/', AlbumListView.as_view()),
    path('albums/<int:album_id>/', AlbumDetailView.as_view()),
]
