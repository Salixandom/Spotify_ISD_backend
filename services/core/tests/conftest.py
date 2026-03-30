"""
Pytest configuration and shared fixtures.
"""
import pytest
import django
from django.conf import settings

# Configure Django settings for tests
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'rest_framework',
            'rest_framework_simplejwt',
            'playlistapp',
            'trackapp',
            'searchapp',
            'historyapp',
        ],
        SECRET_KEY='test-secret-key',
        USE_TZ=True,
    )

    django.setup()


@pytest.fixture(autouse=True)
def enable_db_access(db):
    """
    Enable database access for all tests.
    This fixture is automatically applied to all tests.
    """
    pass


@pytest.fixture
def api_client():
    """
    Provide an API client for making requests.
    """
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_user(api_client):
    """
    Create and authenticate a test user.
    Returns the user ID.
    """
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.tokens import RefreshToken

    User = get_user_model()
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )

    # Generate JWT token
    token = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    return user.id


@pytest.fixture
def test_playlist(authenticated_user):
    """
    Create a test playlist owned by authenticated user.
    """
    from playlistapp.models import Playlist

    playlist = Playlist.objects.create(
        owner_id=authenticated_user,
        name='Test Playlist',
        description='A test playlist',
        visibility='public',
        playlist_type='solo',
        max_songs=50
    )
    return playlist


@pytest.fixture
def test_artist():
    """
    Create a test artist.
    """
    from searchapp.models import Artist

    artist = Artist.objects.create(
        name='Test Artist',
        bio='A test artist',
        image_url='https://example.com/artist.jpg'
    )
    return artist


@pytest.fixture
def test_album(test_artist):
    """
    Create a test album.
    """
    from searchapp.models import Album

    album = Album.objects.create(
        name='Test Album',
        artist=test_artist,
        release_year=2024,
        cover_url='https://example.com/album.jpg'
    )
    return album


@pytest.fixture
def test_song(test_artist, test_album):
    """
    Create a test song.
    """
    from searchapp.models import Song

    song = Song.objects.create(
        title='Test Song',
        artist=test_artist,
        album=test_album,
        genre='Pop',
        duration_seconds=210,
        cover_url='https://example.com/song.jpg',
        release_date='2024-01-01',
        is_explicit=False,
        popularity_score=80
    )
    return song
