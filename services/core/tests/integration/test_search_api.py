"""
Integration tests for Search API endpoints.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from searchapp.models import Genre


@pytest.mark.django_db
class TestSearchView:
    """Test unified search endpoint."""

    def test_unified_search(self, api_client, authenticated_user, test_song, test_artist, test_album):
        """Test searching across songs, playlists, artists, and albums."""
        url = reverse('search')
        response = api_client.get(url, {'q': 'Test'})

        assert response.status_code == status.HTTP_200_OK
        assert 'songs' in response.data
        assert 'playlists' in response.data
        assert 'artists' in response.data
        assert 'albums' in response.data

    def test_empty_search(self, api_client, authenticated_user):
        """Test search with empty query returns all results."""
        url = reverse('search')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestGenreDiscovery:
    """Test genre-based discovery endpoints."""

    def test_list_genres(self, api_client, authenticated_user):
        """Test listing all genres."""
        Genre.objects.create(name='Rock', description='Rock music')
        Genre.objects.create(name='Pop', description='Pop music')

        url = reverse('genre-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'genres' in response.data
        assert len(response.data['genres']) >= 2

    def test_genre_detail(self, api_client, authenticated_user, test_song):
        """Test getting genre details with songs."""
        url = reverse('genre-detail', kwargs={'genre_name': test_song.genre})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'genre' in response.data
        assert 'songs' in response.data

    def test_new_releases(self, api_client, authenticated_user, test_song):
        """Test getting new releases."""
        url = reverse('new-releases')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'songs' in response.data
        assert 'since_date' in response.data

    def test_trending(self, api_client, authenticated_user, test_song):
        """Test getting trending songs."""
        url = reverse('trending')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'songs' in response.data
        assert 'period' in response.data

    def test_similar_songs(self, api_client, authenticated_user, test_song):
        """Test getting similar songs."""
        url = reverse('similar-songs', kwargs={'song_id': test_song.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'similar_songs' in response.data

    def test_recommendations(self, api_client, authenticated_user):
        """Test personalized recommendations."""
        url = reverse('recommendations')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'songs' in response.data
        assert 'recommendation_type' in response.data


@pytest.mark.django_db
class TestArtistEndpoints:
    """Test artist-related endpoints."""

    def test_list_artists(self, api_client, authenticated_user, test_artist):
        """Test listing artists."""
        url = reverse('artist-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_search_artists(self, api_client, authenticated_user, test_artist):
        """Test searching artists."""
        url = reverse('artist-list')
        response = api_client.get(url, {'q': 'Test'})

        assert response.status_code == status.HTTP_200_OK
        assert any(a['name'] == 'Test Artist' for a in response.data)

    def test_artist_detail(self, api_client, authenticated_user, test_artist):
        """Test getting artist details."""
        url = reverse('artist-detail', kwargs={'artist_id': test_artist.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == test_artist.id
        assert response.data['name'] == test_artist.name


@pytest.mark.django_db
class TestAlbumEndpoints:
    """Test album-related endpoints."""

    def test_list_albums(self, api_client, authenticated_user, test_album):
        """Test listing albums."""
        url = reverse('album-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_search_albums(self, api_client, authenticated_user, test_album):
        """Test searching albums."""
        url = reverse('album-list')
        response = api_client.get(url, {'q': 'Test'})

        assert response.status_code == status.HTTP_200_OK
        assert any(a['title'] == 'Test Album' for a in response.data)

    def test_album_detail(self, api_client, authenticated_user, test_album):
        """Test getting album details."""
        url = reverse('album-detail', kwargs={'album_id': test_album.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == test_album.id
        assert response.data['title'] == test_album.title


@pytest.mark.django_db
class TestSongSearch:
    """Test song search endpoint."""

    def test_search_songs(self, api_client, authenticated_user, test_song):
        """Test searching songs."""
        url = reverse('song-search')
        response = api_client.get(url, {'q': 'Test'})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_filter_songs_by_genre(self, api_client, authenticated_user, test_song):
        """Test filtering songs by genre."""
        url = reverse('song-search')
        response = api_client.get(url, {'genre': test_song.genre})

        assert response.status_code == status.HTTP_200_OK
        assert all(s['genre'] == test_song.genre for s in response.data)

    def test_sort_songs(self, api_client, authenticated_user, test_song):
        """Test sorting songs."""
        url = reverse('song-search')
        response = api_client.get(url, {'sort': 'title', 'order': 'asc'})

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestPlaylistSearch:
    """Test playlist search endpoint."""

    def test_search_playlists(self, api_client, authenticated_user, test_playlist):
        """Test searching public playlists."""
        url = reverse('playlist-search')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_filter_playlists_by_type(self, api_client, authenticated_user, test_playlist):
        """Test filtering playlists by type."""
        url = reverse('playlist-search')
        response = api_client.get(url, {'type': test_playlist.playlist_type})

        assert response.status_code == status.HTTP_200_OK
        assert all(p['playlist_type'] == test_playlist.playlist_type for p in response.data)
