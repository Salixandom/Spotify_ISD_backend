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
    path('health/', health_check, name='search-health'),
    path('', SearchView.as_view(), name='search'),
    path('songs/', SongSearchView.as_view(), name='song-search'),
    path('playlists/', PlaylistSearchView.as_view(), name='playlist-search'),
    path('browse/', BrowseView.as_view(), name='browse'),
    path('artists/', ArtistListView.as_view(), name='artist-list'),
    path('artists/<int:artist_id>/', ArtistDetailView.as_view(), name='artist-detail'),
    path('albums/', AlbumListView.as_view(), name='album-list'),
    path('albums/<int:album_id>/', AlbumDetailView.as_view(), name='album-detail'),

    # Discovery endpoints
    path('discover/genres/', GenreListView.as_view(), name='genre-list'),
    path('discover/genres/<str:genre_name>/', GenreDetailView.as_view(), name='genre-detail'),
    path('discover/new-releases/', NewReleasesView.as_view(), name='new-releases'),
    path('discover/trending/', TrendingView.as_view(), name='trending'),
    path('discover/similar/<int:song_id>/', SimilarSongsView.as_view(), name='similar-songs'),
    path('discover/recommendations/', RecommendationsView.as_view(), name='recommendations'),
]
