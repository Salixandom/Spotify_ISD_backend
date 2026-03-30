from django.urls import path
from .views import (
    SearchView, BrowseView,
    SongSearchView, PlaylistSearchView,
    ArtistListView, ArtistDetailView,
    AlbumListView, AlbumDetailView,
    GenreListView, GenreDetailView,
    NewReleasesView, TrendingView,
    SimilarSongsView, RecommendationsView,
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

    # Discovery endpoints
    path('discover/genres/', GenreListView.as_view(), name='genre-list'),
    path('discover/genres/<str:genre_name>/', GenreDetailView.as_view(), name='genre-detail'),
    path('discover/new-releases/', NewReleasesView.as_view(), name='new-releases'),
    path('discover/trending/', TrendingView.as_view(), name='trending'),
    path('discover/similar/<int:song_id>/', SimilarSongsView.as_view(), name='similar-songs'),
    path('discover/recommendations/', RecommendationsView.as_view(), name='recommendations'),
]
