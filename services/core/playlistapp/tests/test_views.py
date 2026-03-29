"""
Test Cases for Playlist App

This module contains comprehensive tests for all playlist endpoints.
Run with: python manage.py test playlistapp.test_views
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Playlist, UserPlaylistFollow, UserPlaylistLike, PlaylistSnapshot

User = get_user_model()


class PlaylistViewSetTest(TestCase):
    """Test core playlist CRUD operations"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.playlist = Playlist.objects.create(
            owner_id=self.user.id,
            name='Test Playlist',
            description='Test description',
            visibility='public'
        )

    def test_list_playlists(self):
        """Test listing playlists"""
        response = self.client.get('/api/playlists/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)

    def test_create_playlist(self):
        """Test creating a new playlist"""
        data = {
            'name': 'New Playlist',
            'description': 'New description',
            'visibility': 'public',
            'playlist_type': 'solo'
        }
        response = self.client.post('/api/playlists/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Playlist')

    def test_filter_by_visibility(self):
        """Test filtering by visibility"""
        response = self.client.get('/api/playlists/?visibility=public')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_by_type(self):
        """Test filtering by playlist type"""
        response = self.client.get('/api/playlists/?type=solo')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_playlists(self):
        """Test searching playlists by name/description"""
        response = self.client.get('/api/playlists/?q=Test')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)

    def test_sort_playlists(self):
        """Test sorting playlists"""
        response = self.client.get('/api/playlists/?sort=name&order=asc')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_own_playlist(self):
        """Test updating own playlist"""
        data = {'name': 'Updated Name'}
        response = self.client.patch(f'/api/playlists/{self.playlist.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Name')

    def test_delete_own_playlist(self):
        """Test deleting own playlist"""
        response = self.client.delete(f'/api/playlists/{self.playlist.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_update_others_playlist(self):
        """Test cannot update other user's playlist"""
        other_user = User.objects.create_user('other', 'pass123')
        other_playlist = Playlist.objects.create(
            owner_id=other_user.id,
            name='Other Playlist',
            visibility='private'
        )

        data = {'name': 'Hacked Name'}
        response = self.client.patch(f'/api/playlists/{other_playlist.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PlaylistStatsViewTest(TestCase):
    """Test playlist statistics endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.playlist = Playlist.objects.create(
            owner_id=self.user.id,
            name='Test Playlist',
            visibility='public'
        )

    def test_get_playlist_stats(self):
        """Test retrieving playlist statistics"""
        response = self.client.get(f'/api/playlists/{self.playlist.id}/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_tracks', response.data)
        self.assertIn('unique_artists', response.data)
        self.assertIn('follower_count', response.data)
        self.assertIn('like_count', response.data)

    def test_stats_for_nonexistent_playlist(self):
        """Test stats for non-existent playlist"""
        response = self.client.get('/api/playlists/99999/stats/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_private_playlist_stats_for_owner(self):
        """Test owner can view private playlist stats"""
        private_playlist = Playlist.objects.create(
            owner_id=self.user.id,
            name='Private Playlist',
            visibility='private'
        )

        response = self.client.get(f'/api/playlists/{private_playlist.id}/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SocialFeaturesTest(TestCase):
    """Test follow/like functionality"""

    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user('user1', 'pass123')
        self.user2 = User.objects.create_user('user2', 'pass123')
        self.client.force_authenticate(user=self.user1)

        self.playlist = Playlist.objects.create(
            owner_id=self.user2.id,
            name='Public Playlist',
            visibility='public'
        )

    def test_follow_playlist(self):
        """Test following a playlist"""
        response = self.client.post(f'/api/playlists/{self.playlist.id}/follow/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            UserPlaylistFollow.objects.filter(
                user_id=self.user1.id,
                playlist=self.playlist
            ).exists()
        )

    def test_unfollow_playlist(self):
        """Test unfollowing a playlist"""
        UserPlaylistFollow.objects.create(
            user_id=self.user1.id,
            playlist=self.playlist
        )

        response = self.client.delete(f'/api/playlists/{self.playlist.id}/follow/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            UserPlaylistFollow.objects.filter(
                user_id=self.user1.id,
                playlist=self.playlist
            ).exists()
        )

    def test_cannot_follow_own_playlist(self):
        """Test cannot follow own playlist"""
        own_playlist = Playlist.objects.create(
            owner_id=self.user1.id,
            name='Own Playlist',
            visibility='public'
        )

        response = self.client.post(f'/api/playlists/{own_playlist.id}/follow/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_like_playlist(self):
        """Test liking a playlist"""
        response = self.client.post(f'/api/playlists/{self.playlist.id}/like/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            UserPlaylistLike.objects.filter(
                user_id=self.user1.id,
                playlist=self.playlist
            ).exists()
        )

    def test_unlike_playlist(self):
        """Test unliking a playlist"""
        UserPlaylistLike.objects.create(
            user_id=self.user1.id,
            playlist=self.playlist
        )

        response = self.client.delete(f'/api/playlists/{self.playlist.id}/like/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_followed_playlists(self):
        """Test filtering followed playlists"""
        UserPlaylistFollow.objects.create(
            user_id=self.user1.id,
            playlist=self.playlist
        )

        response = self.client.get('/api/playlists/?filter=followed')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)

    def test_filter_liked_playlists(self):
        """Test filtering liked playlists"""
        UserPlaylistLike.objects.create(
            user_id=self.user1.id,
            playlist=self.playlist
        )

        response = self.client.get('/api/playlists/?filter=liked')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BatchOperationsTest(TestCase):
    """Test batch operations"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user('testuser', 'testpass123')
        self.client.force_authenticate(user=self.user)

        self.playlist1 = Playlist.objects.create(
            owner_id=self.user.id,
            name='Playlist 1'
        )
        self.playlist2 = Playlist.objects.create(
            owner_id=self.user.id,
            name='Playlist 2'
        )

    def test_batch_delete(self):
        """Test deleting multiple playlists"""
        data = {'playlist_ids': [self.playlist1.id, self.playlist2.id]}
        response = self.client.delete('/api/playlists/batch-delete/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted'], 2)

    def test_batch_update(self):
        """Test updating multiple playlists"""
        data = {
            'playlist_ids': [self.playlist1.id, self.playlist2.id],
            'updates': {'visibility': 'private'}
        }
        response = self.client.patch('/api/playlists/batch-update/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated'], 2)

    def test_enhanced_batch_delete_with_results(self):
        """Test enhanced batch delete with detailed results"""
        data = {
            'playlist_ids': [self.playlist1.id, 99999],
            'create_snapshots': True
        }
        response = self.client.delete('/api/playlists/batch-delete-advanced/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted'], 1)
        self.assertEqual(response.data['failed'], 1)
        self.assertEqual(len(response.data['results']), 2)


class ExportImportTest(TestCase):
    """Test export/import functionality"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user('testuser', 'testpass123')
        self.client.force_authenticate(user=self.user)

        self.playlist = Playlist.objects.create(
            owner_id=self.user.id,
            name='Export Test',
            visibility='public'
        )

    def test_export_playlist(self):
        """Test exporting playlist to JSON"""
        response = self.client.get(f'/api/playlists/{self.playlist.id}/export/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('playlist', response.data)
        self.assertIn('export_metadata', response.data)

    def test_export_includes_metadata(self):
        """Test export includes all metadata"""
        response = self.client.get(f'/api/playlists/{self.playlist.id}/export/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('exported_at', response.data['export_metadata'])
        self.assertIn('exported_by', response.data['export_metadata'])
        self.assertIn('version', response.data['export_metadata'])

    def test_import_playlist(self):
        """Test importing playlist from JSON"""
        export_data = {
            'playlist': {
                'name': 'Imported Playlist',
                'description': 'Test import',
                'visibility': 'private',
                'tracks': []
            }
        }

        response = self.client.post('/api/playlists/import/', export_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Imported Playlist')


class SnapshotTest(TestCase):
    """Test snapshot/versioning functionality"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user('testuser', 'testpass123')
        self.client.force_authenticate(user=self.user)

        self.playlist = Playlist.objects.create(
            owner_id=self.user.id,
            name='Snapshot Test',
            visibility='public'
        )

    def test_create_snapshot(self):
        """Test creating manual snapshot"""
        data = {'change_reason': 'Test snapshot'}
        response = self.client.post(f'/api/playlists/{self.playlist.id}/snapshots/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            PlaylistSnapshot.objects.filter(
                playlist=self.playlist,
                change_reason='Test snapshot'
            ).exists()
        )

    def test_list_snapshots(self):
        """Test listing snapshots"""
        PlaylistSnapshot.objects.create(
            playlist=self.playlist,
            snapshot_data={},
            created_by=self.user.id,
            change_reason='Test',
            track_count=0
        )

        response = self.client.get(f'/api/playlists/{self.playlist.id}/snapshots/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)

    def test_cleanup_old_snapshots(self):
        """Test cleaning up old snapshots"""
        # Create multiple snapshots
        for i in range(15):
            PlaylistSnapshot.objects.create(
                playlist=self.playlist,
                snapshot_data={},
                created_by=self.user.id,
                change_reason=f'Snapshot {i}',
                track_count=0
            )

        data = {'keep': 10}
        response = self.client.delete(f'/api/playlists/{self.playlist.id}/snapshots/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['kept'], 10)
        self.assertEqual(PlaylistSnapshot.objects.filter(playlist=self.playlist).count(), 10)


class SmartFeaturesTest(TestCase):
    """Test recommendation and similarity features"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user('testuser', 'testpass123')
        self.client.force_authenticate(user=self.user)

        self.playlist = Playlist.objects.create(
            owner_id=self.user.id,
            name='Test Playlist',
            visibility='public'
        )

    def test_get_recommendations(self):
        """Test getting personalized recommendations"""
        response = self.client.get('/api/playlists/recommended/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('playlists', response.data)

    def test_similar_playlists(self):
        """Test finding similar playlists"""
        response = self.client.get(f'/api/playlists/{self.playlist.id}/similar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('similar_playlists', response.data)

    def test_auto_generated_suggestions(self):
        """Test getting auto-generated suggestions"""
        response = self.client.get('/api/playlists/auto-generated/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('suggestions', response.data)


class FeaturedPlaylistsTest(TestCase):
    """Test featured playlists endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user('testuser', 'testpass123')
        self.client.force_authenticate(user=self.user)

        # Create some public playlists
        for i in range(5):
            Playlist.objects.create(
                owner_id=self.user.id,
                name=f'Playlist {i}',
                visibility='public'
            )

    def test_get_featured_playlists(self):
        """Test getting featured playlists"""
        response = self.client.get('/api/playlists/featured/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_featured_with_limit(self):
        """Test featured playlists with limit"""
        response = self.client.get('/api/playlists/featured/?limit=3')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data), 3)


class UserPlaylistsTest(TestCase):
    """Test user playlists endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user('user1', 'pass123')
        self.user2 = User.objects.create_user('user2', 'pass123')
        self.client.force_authenticate(user=self.user1)

        # User1's playlists
        Playlist.objects.create(
            owner_id=self.user1.id,
            name='Public Playlist',
            visibility='public'
        )
        Playlist.objects.create(
            owner_id=self.user1.id,
            name='Private Playlist',
            visibility='private'
        )

        # User2's playlists
        Playlist.objects.create(
            owner_id=self.user2.id,
            name='Other Public',
            visibility='public'
        )

    def test_get_own_playlists(self):
        """Test getting own playlists shows all"""
        response = self.client.get(f'/api/users/{self.user1.id}/playlists/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 2)

    def test_get_other_users_playlists(self):
        """Test getting other user's playlists shows only public"""
        response = self.client.get(f'/api/users/{self.user2.id}/playlists/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)
