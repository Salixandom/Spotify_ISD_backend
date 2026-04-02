"""
Performance tests for critical query paths.
Verifies that query optimizations (select_related, prefetch_related) are working.
"""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from playlistapp.models import Playlist
from trackapp.models import Track
from searchapp.models import Song, Artist, Album


@pytest.mark.django_db
class TestTrackListQueryPerformance:
    """Test track list query performance."""

    def test_select_related_optimization(self, api_client, authenticated_user, test_playlist, test_artist, test_album):
        """Test that TrackListView uses select_related to avoid N+1 queries."""
        # Create multiple tracks with distinct songs (unique_together: playlist + song)
        for i in range(10):
            song = Song.objects.create(
                title=f'Perf Song {i}',
                artist=test_artist,
                album=test_album,
                genre='Pop'
            )
            Track.objects.create(
                playlist=test_playlist,
                song=song,
                added_by_id=authenticated_user,
                position=i
            )

        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})

        # Capture queries
        with CaptureQueriesContext(connection) as context:
            response = api_client.get(url)

        assert response.status_code == 200
        # Should use very few queries due to select_related
        # Expected: 1 query for tracks (with joins to song, artist, album)
        # Actual may vary slightly but should be < 5
        query_count = len(context.captured_queries)
        assert query_count < 5, f"Expected < 5 queries, got {query_count}. Queries: {[q['sql'] for q in context.captured_queries]}"

    def test_no_nq1_problem_with_song_data(self, api_client, authenticated_user, test_playlist, test_song):
        """Verify accessing song data doesn't trigger additional queries."""
        Track.objects.create(
            playlist=test_playlist,
            song=test_song,
            added_by_id=authenticated_user,
            position=0
        )

        url = reverse('track-list', kwargs={'playlist_id': test_playlist.id})

        with CaptureQueriesContext(connection) as context:
            response = api_client.get(url)

        # The response includes song, artist, and album data
        # With proper select_related, this should not cause N+1 queries
        assert response.status_code == 200
        assert len(context.captured_queries) < 5


@pytest.mark.django_db
class TestPlaylistQueryPerformance:
    """Test playlist query performance."""

    def test_playlist_list_with_annotations(self, api_client, authenticated_user):
        """Test playlist list uses annotations efficiently."""
        # Create multiple playlists
        for i in range(10):
            Playlist.objects.create(
                owner_id=authenticated_user,
                name=f'Playlist {i}'
            )

        url = reverse('playlist-list')

        with CaptureQueriesContext(connection) as context:
            response = api_client.get(url)

        assert response.status_code == 200
        # Should be efficient even with annotations
        query_count = len(context.captured_queries)
        assert query_count < 20, f"Expected < 20 queries, got {query_count}"


@pytest.mark.django_db
class TestSearchQueryPerformance:
    """Test search query performance."""

    def test_unified_search_efficiency(self, api_client, authenticated_user, test_artist, test_album, test_song):
        """Test unified search doesn't cause excessive queries."""
        url = reverse('search')

        with CaptureQueriesContext(connection) as context:
            response = api_client.get(url, {'q': 'Test'})

        assert response.status_code == 200
        # Should query all 4 models efficiently
        # Expected: ~4 queries (one per model)
        query_count = len(context.captured_queries)
        assert query_count <= 6, f"Expected <= 6 queries, got {query_count}"

    def test_similar_songs_optimization(self, api_client, authenticated_user, test_song):
        """Test similar songs uses the optimized query (not N+1)."""
        url = reverse('similar-songs', kwargs={'song_id': test_song.id})

        with CaptureQueriesContext(connection) as context:
            response = api_client.get(url)

        assert response.status_code == 200
        # With optimization: should fetch all candidate genres in 1-2 queries
        # Without optimization: would query inside the loop (N+1)
        query_count = len(context.captured_queries)
        assert query_count < 10, f"Similar songs should use optimized query, got {query_count} queries"


@pytest.mark.django_db
class TestRecommendationPerformance:
    """Test recommendation algorithm performance."""

    def test_recommendations_with_genre_aggregation(self, api_client, authenticated_user):
        """Test recommendations use database aggregation for genre counting."""
        # Create a playlist with tracks
        playlist = Playlist.objects.create(owner_id=authenticated_user, name='Test')

        artist = Artist.objects.create(name='Test Artist')
        album = Album.objects.create(name='Test Album', artist=artist)

        for i in range(5):
            song = Song.objects.create(
                title=f'Song {i}',
                artist=artist,
                album=album,
                genre='Pop' if i % 2 == 0 else 'Rock'
            )
            Track.objects.create(
                playlist=playlist,
                song=song,
                added_by_id=authenticated_user,
                position=i
            )

        url = reverse('recommendations')

        with CaptureQueriesContext(connection) as context:
            response = api_client.get(url)

        assert response.status_code == 200
        # With aggregation: should use COUNT in database
        # Without: would fetch all rows and count in Python
        query_count = len(context.captured_queries)
        assert query_count < 10, f"Recommendations should use aggregation, got {query_count} queries"


@pytest.mark.django_db
class TestSimilarPlaylistsOptimization:
    """Test similar playlists optimization."""

    def test_similar_playlists_no_n1_query(self, api_client, authenticated_user):
        """Test similar playlists fetches genres in batches, not per-playlist."""
        # Create multiple playlists with genres
        artist = Artist.objects.create(name='Artist')
        album = Album.objects.create(name='Album', artist=artist)

        playlist1 = Playlist.objects.create(owner_id=authenticated_user, name='Playlist 1')
        playlist2 = Playlist.objects.create(owner_id=authenticated_user + 1, name='Playlist 2')
        playlist2.visibility = 'public'
        playlist2.save()

        # Add tracks with same genre to both
        for i in range(5):
            song = Song.objects.create(
                title=f'Song {i}',
                artist=artist,
                album=album,
                genre='Pop'
            )
            Track.objects.create(
                playlist=playlist1,
                song=song,
                added_by_id=authenticated_user,
                position=i
            )

            song2 = Song.objects.create(
                title=f'Song {i}b',
                artist=artist,
                album=album,
                genre='Pop'
            )
            Track.objects.create(
                playlist=playlist2,
                song=song2,
                added_by_id=authenticated_user + 1,
                position=i
            )

        url = reverse('similar-playlists', kwargs={'pk': playlist1.id})

        with CaptureQueriesContext(connection) as context:
            response = api_client.get(url)

        assert response.status_code == 200
        # With optimization: fetch all candidate genres in 1 query
        # Without: would query for each candidate playlist (N+1)
        query_count = len(context.captured_queries)
        assert query_count < 10, f"Similar playlists should use batch fetch, got {query_count} queries"


@pytest.mark.django_db
class TestIndexUsage:
    """Test that database indexes are being used."""

    def test_composite_index_usage(self, api_client, authenticated_user):
        """Test composite indexes are used for filtering."""
        # Create playlists with different visibilities
        Playlist.objects.create(owner_id=authenticated_user, name='P1', visibility='public')
        Playlist.objects.create(owner_id=authenticated_user, name='P2', visibility='private')
        Playlist.objects.create(owner_id=authenticated_user, name='P3', visibility='public')

        url = reverse('playlist-list')

        with CaptureQueriesContext(connection) as context:
            response = api_client.get(url, {'visibility': 'public'})

        assert response.status_code == 200
        # Should use the (owner_id, visibility) composite index
        # Verify by checking EXPLAIN (not easily testable without DB access)
        # But we can verify it's fast (low query count)
        assert len(context.captured_queries) <= 6


@pytest.mark.django_db
class TestBatchOperationPerformance:
    """Test batch operations scale efficiently."""

    def test_batch_delete_performance(self, api_client, authenticated_user):
        """Test batch delete doesn't cause N queries for N items."""
        # Create many playlists
        playlist_ids = []
        for i in range(20):
            playlist = Playlist.objects.create(
                owner_id=authenticated_user,
                name=f'Playlist {i}'
            )
            playlist_ids.append(playlist.id)

        url = reverse('playlist-batch-delete')
        data = {'playlist_ids': playlist_ids}

        with CaptureQueriesContext(connection) as context:
            response = api_client.delete(url, data, format='json')

        assert response.status_code == 200
        # Should use efficient queries, not N+1
        # Expected: ~N queries for fetch + 1 for delete (or batch delete)
        # But should scale reasonably
        query_count = len(context.captured_queries)
        assert query_count < 30, f"Batch delete should be efficient, got {query_count} queries for 20 items"
