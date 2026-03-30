"""
Unit tests for Search app models.
"""
import pytest
from datetime import date
from searchapp.models import Artist, Album, Song, Genre


@pytest.mark.django_db
class TestArtistModel:
    """Test Artist model functionality."""

    def test_create_artist(self):
        """Test creating a new artist."""
        artist = Artist.objects.create(
            name='Test Artist',
            bio='A test artist',
            image_url='https://example.com/artist.jpg'
        )

        assert artist.id is not None
        assert artist.name == 'Test Artist'
        assert artist.bio == 'A test artist'
        assert artist.image_url == 'https://example.com/artist.jpg'

    def test_artist_str_method(self):
        """Test string representation of artist."""
        artist = Artist.objects.create(name='Test Artist')
        assert str(artist) == 'Test Artist'


@pytest.mark.django_db
class TestAlbumModel:
    """Test Album model functionality."""

    def test_create_album(self, test_artist):
        """Test creating a new album."""
        album = Album.objects.create(
            name='Test Album',
            artist=test_artist,
            release_year=2024,
            cover_url='https://example.com/album.jpg'
        )

        assert album.id is not None
        assert album.name == 'Test Album'
        assert album.artist == test_artist
        assert album.release_year == 2024

    def test_album_str_method(self, test_artist):
        """Test string representation of album."""
        album = Album.objects.create(
            name='Test Album',
            artist=test_artist
        )
        # Album __str__ might include artist name
        album_str = str(album)
        assert 'Test Album' in album_str


@pytest.mark.django_db
class TestSongModel:
    """Test Song model functionality."""

    def test_create_song(self, test_artist, test_album):
        """Test creating a new song."""
        song = Song.objects.create(
            title='Test Song',
            artist=test_artist,
            album=test_album,
            genre='Pop',
            duration_seconds=210,
            cover_url='https://example.com/song.jpg',
            release_date=date(2024, 1, 1),
            is_explicit=False,
            popularity_score=80
        )

        assert song.id is not None
        assert song.title == 'Test Song'
        assert song.artist == test_artist
        assert song.album == test_album
        assert song.genre == 'Pop'
        assert song.duration_seconds == 210
        assert song.popularity_score == 80
        assert song.is_explicit is False

    def test_song_defaults(self, test_artist, test_album):
        """Test default values for song fields."""
        song = Song.objects.create(
            title='Test Song',
            artist=test_artist,
            album=test_album
        )

        assert song.genre == ''
        assert song.duration_seconds == 0
        assert song.cover_url == ''
        assert song.popularity_score == 0
        assert song.is_explicit is False

    def test_song_str_method(self, test_artist, test_album):
        """Test string representation of song."""
        song = Song.objects.create(
            title='Test Song',
            artist=test_artist,
            album=test_album
        )
        # Song __str__ might include artist name, check what it actually returns
        song_str = str(song)
        assert 'Test Song' in song_str


@pytest.mark.django_db
class TestGenreModel:
    """Test Genre model functionality."""

    def test_create_genre(self):
        """Test creating a new genre."""
        genre = Genre.objects.create(
            name='Rock',
            description='Rock music',
            image_url='https://example.com/rock.jpg'
        )

        assert genre.id is not None
        assert genre.name == 'Rock'
        assert genre.description == 'Rock music'
        assert genre.song_count == 0
        assert genre.follower_count == 0

    def test_genre_defaults(self):
        """Test default values for genre fields."""
        genre = Genre.objects.create(name='Jazz')

        assert genre.description == ''
        assert genre.image_url == ''
        assert genre.song_count == 0
        assert genre.follower_count == 0

    def test_genre_unique_name(self):
        """Test that genre names are unique."""
        Genre.objects.create(name='Electronic')

        # Attempting to create again should raise IntegrityError
        with pytest.raises(Exception):  # IntegrityError
            Genre.objects.create(name='Electronic')

    def test_genre_str_method(self):
        """Test string representation of genre."""
        genre = Genre.objects.create(name='Classical')
        assert str(genre) == 'Classical'
