from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from utils.responses import (
    SuccessResponse,
    NotFoundResponse,
    ServiceUnavailableResponse,
)
from django.db.models import Q
from django.db import connection

from .models import Artist, Album, Song, Genre
from .serializers import ArtistSerializer, AlbumSerializer, SongSerializer, GenreSerializer, SongMinimalSerializer
from playlistapp.models import Playlist
from playlistapp.serializers import PlaylistSerializer

SONG_SORT_MAP = {
    'title':    'title',
    'artist':   'artist__name',
    'album':    'album__name',
    'genre':    'genre',
    'duration': 'duration_seconds',
    'year':     'release_year',
}


class SearchView(APIView):
    """Unified search across songs, playlists, artists, and albums."""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Unified search",
        description="Search across songs, playlists, artists, and albums with a single query. Searches song titles, artist names, album names, playlist names, and descriptions. Returns up to 20 results per category. For playlists, shows all public playlists plus your own playlists (including private).",
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query - searches across song titles, artists, albums, and playlist names',
                required=False,
                example='Beatles'
            )
        ],
        examples=[
            OpenApiExample(
                'Search for artist',
                description='Search for songs, albums, and playlists by artist name',
                value={'q': 'Beatles'}
            ),
            OpenApiExample(
                'Search for song',
                description='Search for a specific song title',
                value={'q': 'Hey Jude'}
            ),
            OpenApiExample(
                'Browse all',
                description='Get all content without filtering (empty query)',
                value={}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Search completed successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'songs': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer', 'example': 1},
                                        'title': {'type': 'string', 'example': 'Hey Jude'},
                                        'artist': {
                                            'type': 'object',
                                            'properties': {
                                                'id': {'type': 'integer', 'example': 1},
                                                'name': {'type': 'string', 'example': 'The Beatles'}
                                            }
                                        },
                                        'album': {
                                            'type': 'object',
                                            'properties': {
                                                'id': {'type': 'integer', 'example': 1},
                                                'name': {'type': 'string', 'example': 'Abbey Road'}
                                            }
                                        },
                                        'duration_seconds': {'type': 'integer', 'example': 431},
                                        'genre': {'type': 'string', 'example': 'Rock'}
                                    }
                                },
                                'description': 'Up to 20 songs matching the search query'
                            },
                            'playlists': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer', 'example': 123},
                                        'name': {'type': 'string', 'example': 'Classic Rock'},
                                        'description': {'type': 'string', 'example': 'Best rock songs ever'},
                                        'owner_id': {'type': 'integer', 'example': 45},
                                        'visibility': {
                                            'type': 'string',
                                            'enum': ['public', 'private', 'collaborative'],
                                            'example': 'public'
                                        },
                                        'track_count': {'type': 'integer', 'example': 150}
                                    }
                                },
                                'description': 'Up to 20 playlists (public + your own)'
                            },
                            'artists': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer', 'example': 1},
                                        'name': {'type': 'string', 'example': 'The Beatles'},
                                        'genre': {'type': 'string', 'example': 'Rock'},
                                        'image_url': {'type': 'string', 'example': 'https://example.com/beatles.jpg'}
                                    }
                                },
                                'description': 'Up to 20 artists matching the search query'
                            },
                            'albums': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer', 'example': 1},
                                        'name': {'type': 'string', 'example': 'Abbey Road'},
                                        'artist': {
                                            'type': 'object',
                                            'properties': {
                                                'id': {'type': 'integer', 'example': 1},
                                                'name': {'type': 'string', 'example': 'The Beatles'}
                                            }
                                        },
                                        'release_year': {'type': 'integer', 'example': 1969},
                                        'genre': {'type': 'string', 'example': 'Rock'}
                                    }
                                },
                                'description': 'Up to 20 albums matching the search query'
                            }
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        query = request.query_params.get('q', '')

        songs = Song.objects.select_related('artist', 'album')
        # Show all public playlists + user's own playlists (both public and private)
        playlists = Playlist.objects.filter(
            Q(visibility='public') | Q(owner_id=request.user.id)
        ).distinct()
        artists = Artist.objects.all()
        albums = Album.objects.select_related('artist')

        if query:
            songs = songs.filter(
                Q(title__icontains=query)
                | Q(artist__name__icontains=query)
                | Q(album__name__icontains=query)
            )
            playlists = playlists.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
            )
            artists = artists.filter(name__icontains=query)
            albums = albums.filter(
                Q(name__icontains=query)
                | Q(artist__name__icontains=query)
            )

        return SuccessResponse(
            data={
                'songs': SongSerializer(songs[:20], many=True).data,
                'playlists': PlaylistSerializer(playlists[:20], many=True).data,
                'artists': ArtistSerializer(artists[:20], many=True).data,
                'albums': AlbumSerializer(albums[:20], many=True).data,
            },
            message='Search completed successfully'
        )


class BrowseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Browse genres",
        description="Returns a list of all unique music genres available in the system. Genres are extracted from all songs in the database, excluding empty values. The list is alphabetically sorted and contains only genre names (not IDs). Use this endpoint to build genre filters, browse menus, or faceted search interfaces.",
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'multiple_genres': {
                        'summary': 'Multiple genres found',
                        'value': {
                            'success': True,
                            'message': 'Found 25 genres',
                            'data': [
                                'Alternative',
                                'Blues',
                                'Classical',
                                'Country',
                                'Dance',
                                'Electronic',
                                'Folk',
                                'Hip-Hop',
                                'Indie',
                                'Jazz',
                                'Metal',
                                'Pop',
                                'Punk',
                                'R&B',
                                'Reggae',
                                'Rock',
                                'Soul',
                                'Techno',
                                'World'
                            ]
                        }
                    },
                    'few_genres': {
                        'summary': 'Limited genres in library',
                        'value': {
                            'success': True,
                            'message': 'Found 3 genres',
                            'data': [
                                'Pop',
                                'Rock',
                                'Electronic'
                            ]
                        }
                    },
                    'no_genres': {
                        'summary': 'No songs with genre information',
                        'value': {
                            'success': True,
                            'message': 'Found 0 genres',
                            'data': []
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        genres = (
            Song.objects.exclude(genre='')
            .values_list('genre', flat=True)
            .distinct()
            .order_by('genre')
        )
        return SuccessResponse(
            data=list(genres),
            message=f'Found {len(list(genres))} genres'
        )


class ArtistListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="List artists",
        description="Returns a list of all artists in the system, alphabetically sorted by name. You can optionally filter artists by name using the search query parameter. Each artist includes their name, genre, and image URL if available.",
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query to filter artists by name (case-insensitive partial match)',
                required=False,
                example='Beat'
            )
        ],
        examples=[
            OpenApiExample(
                'List all artists',
                description='Get all artists in the system',
                value={}
            ),
            OpenApiExample(
                'Search for artist',
                description='Filter artists by name',
                value={'q': 'Beat'}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'all_artists': {
                        'summary': 'All artists returned',
                        'value': {
                            'success': True,
                            'message': 'Found 150 artists',
                            'data': [
                                {
                                    'id': 1,
                                    'name': 'The Beatles',
                                    'genre': 'Rock',
                                    'image_url': 'https://example.com/beatles.jpg'
                                },
                                {
                                    'id': 2,
                                    'name': 'Taylor Swift',
                                    'genre': 'Pop',
                                    'image_url': 'https://example.com/taylor.jpg'
                                },
                                {
                                    'id': 3,
                                    'name': 'Daft Punk',
                                    'genre': 'Electronic',
                                    'image_url': 'https://example.com/daft.jpg'
                                }
                            ]
                        }
                    },
                    'filtered_results': {
                        'summary': 'Artists filtered by search query',
                        'value': {
                            'success': True,
                            'message': 'Found 2 artists',
                            'data': [
                                {
                                    'id': 1,
                                    'name': 'The Beatles',
                                    'genre': 'Rock',
                                    'image_url': 'https://example.com/beatles.jpg'
                                },
                                {
                                    'id': 45,
                                    'name': 'Beatles Tribute',
                                    'genre': 'Rock',
                                    'image_url': None
                                }
                            ]
                        }
                    },
                    'no_results': {
                        'summary': 'No artists match the search',
                        'value': {
                            'success': True,
                            'message': 'Found 0 artists',
                            'data': []
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        query = request.query_params.get('q', '')
        qs = Artist.objects.all()
        if query:
            qs = qs.filter(name__icontains=query)
        return SuccessResponse(
            data=ArtistSerializer(qs.order_by('name'), many=True).data,
            message=f'Found {qs.count()} artists'
        )


class ArtistDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Get artist details",
        description="Returns detailed information about a specific artist including their name, genre, image URL, and associated songs. This endpoint provides a comprehensive artist profile useful for artist pages, artist discovery features, and music library browsing.",
        parameters=[
            OpenApiParameter(
                name='artist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the artist to retrieve',
                required=True,
                example=1
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'artist_found': {
                        'summary': 'Artist details retrieved successfully',
                        'value': {
                            'success': True,
                            'message': 'Artist retrieved successfully',
                            'data': {
                                'id': 1,
                                'name': 'The Beatles',
                                'genre': 'Rock',
                                'image_url': 'https://example.com/beatles.jpg',
                                'songs': [
                                    {
                                        'id': 101,
                                        'title': 'Hey Jude',
                                        'album': 'Abbey Road',
                                        'duration_seconds': 431,
                                        'genre': 'Rock'
                                    },
                                    {
                                        'id': 102,
                                        'title': 'Let It Be',
                                        'album': 'Let It Be',
                                        'duration_seconds': 243,
                                        'genre': 'Rock'
                                    }
                                ]
                            }
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'artist_not_found': {
                        'summary': 'Artist ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Artist not found'
                        }
                    }
                }
            }
        }
    )
    def get(self, request, artist_id):
        try:
            artist = Artist.objects.get(id=artist_id)
        except Artist.DoesNotExist:
            return NotFoundResponse(message='Artist not found')
        return SuccessResponse(
            data=ArtistSerializer(artist).data,
            message='Artist retrieved successfully'
        )


class AlbumListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="List albums",
        description="Returns a list of all albums in the system, alphabetically sorted by name. Each album includes the artist information, release year, and genre. You can optionally filter albums by name or artist name using the search query parameter. The search performs a case-insensitive partial match on both album name and artist name.",
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query to filter albums by name or artist (case-insensitive partial match)',
                required=False,
                example='Abbey'
            )
        ],
        examples=[
            OpenApiExample(
                'List all albums',
                description='Get all albums in the system',
                value={}
            ),
            OpenApiExample(
                'Search by album name',
                description='Filter albums by name',
                value={'q': 'Abbey'}
            ),
            OpenApiExample(
                'Search by artist',
                description='Filter albums by artist name',
                value={'q': 'Beatles'}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'all_albums': {
                        'summary': 'All albums returned',
                        'value': {
                            'success': True,
                            'message': 'Found 85 albums',
                            'data': [
                                {
                                    'id': 1,
                                    'name': 'Abbey Road',
                                    'artist': {
                                        'id': 1,
                                        'name': 'The Beatles'
                                    },
                                    'release_year': 1969,
                                    'genre': 'Rock'
                                },
                                {
                                    'id': 2,
                                    'name': 'Thriller',
                                    'artist': {
                                        'id': 45,
                                        'name': 'Michael Jackson'
                                    },
                                    'release_year': 1982,
                                    'genre': 'Pop'
                                }
                            ]
                        }
                    },
                    'filtered_results': {
                        'summary': 'Albums filtered by search query',
                        'value': {
                            'success': True,
                            'message': 'Found 3 albums',
                            'data': [
                                {
                                    'id': 1,
                                    'name': 'Abbey Road',
                                    'artist': {
                                        'id': 1,
                                        'name': 'The Beatles'
                                    },
                                    'release_year': 1969,
                                    'genre': 'Rock'
                                }
                            ]
                        }
                    },
                    'no_results': {
                        'summary': 'No albums match the search',
                        'value': {
                            'success': True,
                            'message': 'Found 0 albums',
                            'data': []
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        query = request.query_params.get('q', '')
        qs = Album.objects.select_related('artist')
        if query:
            qs = qs.filter(
                Q(name__icontains=query) | Q(artist__name__icontains=query)
            )
        return SuccessResponse(
            data=AlbumSerializer(qs.order_by('name'), many=True).data,
            message=f'Found {qs.count()} albums'
        )


class AlbumDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Get album details",
        description="Returns detailed information about a specific album including name, artist, release year, genre, and all tracks on the album. This endpoint provides a complete album profile useful for album pages, track listings, and music library browsing. The artist information is included for context.",
        parameters=[
            OpenApiParameter(
                name='album_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the album to retrieve',
                required=True,
                example=1
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'album_found': {
                        'summary': 'Album details retrieved successfully',
                        'value': {
                            'success': True,
                            'message': 'Album retrieved successfully',
                            'data': {
                                'id': 1,
                                'name': 'Abbey Road',
                                'artist': {
                                    'id': 1,
                                    'name': 'The Beatles'
                                },
                                'release_year': 1969,
                                'genre': 'Rock',
                                'songs': [
                                    {
                                        'id': 101,
                                        'title': 'Come Together',
                                        'duration_seconds': 259,
                                        'genre': 'Rock'
                                    },
                                    {
                                        'id': 102,
                                        'title': 'Something',
                                        'duration_seconds': 182,
                                        'genre': 'Rock'
                                    },
                                    {
                                        'id': 103,
                                        'title': 'Here Comes the Sun',
                                        'duration_seconds': 185,
                                        'genre': 'Rock'
                                    }
                                ]
                            }
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'album_not_found': {
                        'summary': 'Album ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Album not found'
                        }
                    }
                }
            }
        }
    )
    def get(self, request, album_id):
        try:
            album = Album.objects.select_related('artist').get(id=album_id)
        except Album.DoesNotExist:
            return NotFoundResponse(message='Album not found')
        return SuccessResponse(
            data=AlbumSerializer(album).data,
            message='Album retrieved successfully'
        )


class SongSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Search songs",
        description="Advanced song search with support for text filtering (title, artist, album), genre filtering, and multiple sort options. Returns up to 20 songs per request. **Note:** Text search is case-insensitive and matches partial strings. Use this endpoint for building advanced search interfaces and music discovery features.",
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Text search query - searches song title, artist name, and album name (case-insensitive partial match)',
                required=False,
                example='Queen'
            ),
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter songs by genre (exact match, case-insensitive)',
                required=False,
                example='Rock'
            ),
            OpenApiParameter(
                name='sort',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort field',
                required=False,
                enum=['title', 'artist', 'album', 'genre', 'duration', 'year', 'added_at'],
                example='title'
            ),
            OpenApiParameter(
                name='order',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort order (default: asc)',
                required=False,
                enum=['asc', 'desc'],
                example='asc'
            )
        ],
        examples=[
            OpenApiExample(
                'Search by text',
                description='Search for songs by artist, title, or album',
                value={'q': 'Queen'}
            ),
            OpenApiExample(
                'Filter by genre',
                description='Get songs from a specific genre',
                value={'genre': 'Rock'}
            ),
            OpenApiExample(
                'Search and sort',
                description='Search and sort results by year',
                value={
                    'q': 'Beatles',
                    'sort': 'year',
                    'order': 'desc'
                }
            ),
            OpenApiExample(
                'List all songs',
                description='Get all songs without filters',
                value={}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'search_results': {
                        'summary': 'Songs matching search query',
                        'value': {
                            'success': True,
                            'message': 'Found 15 songs',
                            'data': [
                                {
                                    'id': 101,
                                    'title': 'Bohemian Rhapsody',
                                    'artist': 'Queen',
                                    'album': 'A Night at the Opera',
                                    'duration_seconds': 354,
                                    'genre': 'Rock',
                                    'release_year': 1975
                                },
                                {
                                    'id': 102,
                                    'title': 'We Will Rock You',
                                    'artist': 'Queen',
                                    'album': 'News of the World',
                                    'duration_seconds': 121,
                                    'genre': 'Rock',
                                    'release_year': 1977
                                }
                            ]
                        }
                    },
                    'filtered_by_genre': {
                        'summary': 'Songs filtered by genre',
                        'value': {
                            'success': True,
                            'message': 'Found 25 songs',
                            'data': [
                                {
                                    'id': 201,
                                    'title': 'Sweet Child O\' Mine',
                                    'artist': 'Guns N\' Roses',
                                    'album': 'Appetite for Destruction',
                                    'duration_seconds': 356,
                                    'genre': 'Rock',
                                    'release_year': 1987
                                }
                            ]
                        }
                    },
                    'no_results': {
                        'summary': 'No songs match the criteria',
                        'value': {
                            'success': True,
                            'message': 'Found 0 songs',
                            'data': []
                        }
                    }
                }
            }
        }
    )
                required=False
            ),
            OpenApiParameter(
                name='sort',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort field',
                required=False,
                enum=['title', 'artist', 'album', 'genre', 'duration', 'year']
            ),
            OpenApiParameter(
                name='order',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort order',
                required=False,
                enum=['asc', 'desc']
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'array',
                        'items': SongSerializer
                    }
                }
            }
        }
    )
    def get(self, request):
        query = request.query_params.get('q', '')
        genre = request.query_params.get('genre', '')
        sort = request.query_params.get('sort', '')
        order = request.query_params.get('order', 'asc')

        qs = Song.objects.select_related('artist', 'album')

        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(artist__name__icontains=query)
                | Q(album__name__icontains=query)
            )

        if genre:
            qs = qs.filter(genre__iexact=genre)

        if sort in SONG_SORT_MAP:
            order_field = SONG_SORT_MAP[sort]
            if order == 'desc':
                order_field = '-' + order_field
            qs = qs.order_by(order_field)

        return SuccessResponse(
            data=SongSerializer(qs[:20], many=True).data,
            message=f'Found {min(qs.count(), 20)} songs'
        )


class PlaylistSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Search playlists",
        description="Search for playlists with support for text filtering (name and description) and playlist type filtering. Returns all public playlists plus the authenticated user's own playlists (including private ones). Results are limited to 20 playlists and sorted alphabetically by name.",
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Text search query - searches playlist name and description (case-insensitive partial match)',
                required=False,
                example='workout'
            ),
            OpenApiParameter(
                name='type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by playlist type',
                required=False,
                enum=['solo', 'collaborative'],
                example='collaborative'
            )
        ],
        examples=[
            OpenApiExample(
                'Search by text',
                description='Search for playlists by name or description',
                value={'q': 'workout'}
            ),
            OpenApiExample(
                'Filter by type',
                description='Get only collaborative playlists',
                value={'type': 'collaborative'}
            ),
            OpenApiExample(
                'Search and filter',
                description='Search within collaborative playlists',
                value={
                    'q': 'party',
                    'type': 'collaborative'
                }
            ),
            OpenApiExample(
                'List all playlists',
                description='Get all public and your own playlists',
                value={}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'search_results': {
                        'summary': 'Playlists matching search query',
                        'value': {
                            'success': True,
                            'message': 'Found 12 playlists',
                            'data': [
                                {
                                    'id': 123,
                                    'name': 'Workout Mix',
                                    'description': 'High energy songs for exercise',
                                    'owner_id': 45,
                                    'visibility': 'public',
                                    'playlist_type': 'solo',
                                    'track_count': 30
                                },
                                {
                                    'id': 456,
                                    'name': 'Morning Workout',
                                    'description': 'Start your day right',
                                    'owner_id': 78,
                                    'visibility': 'public',
                                    'playlist_type': 'solo',
                                    'track_count': 25
                                }
                            ]
                        }
                    },
                    'collaborative_only': {
                        'summary': 'Collaborative playlists only',
                        'value': {
                            'success': True,
                            'message': 'Found 5 playlists',
                            'data': [
                                {
                                    'id': 789,
                                    'name': 'Team Playlist',
                                    'description': 'Our team favorites',
                                    'owner_id': 1,
                                    'visibility': 'public',
                                    'playlist_type': 'collaborative',
                                    'track_count': 50
                                }
                            ]
                        }
                    },
                    'no_results': {
                        'summary': 'No playlists match the criteria',
                        'value': {
                            'success': True,
                            'message': 'Found 0 playlists',
                            'data': []
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        query = request.query_params.get('q', '')
        playlist_type = request.query_params.get('type', '')

        # Show all public playlists + user's own playlists (both public and private)
        qs = Playlist.objects.filter(
            Q(visibility='public') | Q(owner_id=request.user.id)
        ).distinct()

        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
            )

        if playlist_type in ('solo', 'collaborative'):
            qs = qs.filter(playlist_type=playlist_type)

        return SuccessResponse(
            data=PlaylistSerializer(qs.order_by('name')[:20], many=True).data,
            message=f'Found {min(qs.count(), 20)} playlists'
        )


class GenreListView(APIView):
    """
    GET /api/discover/genres/

    List all music genres with statistics.
    Can be used for genre browsing and exploration.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="List all genres",
        description="Returns a list of all music genres with statistics including song count, image URL, and description. This endpoint is ideal for building genre browsing interfaces, genre filters, and music discovery features. **Note:** If the Genre table is empty, it automatically falls back to extracting genres from the Song database.",
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'from_genre_table': {
                        'summary': 'Genres from Genre table (with full details)',
                        'value': {
                            'success': True,
                            'message': 'Found 15 genres',
                            'data': {
                                'genres': [
                                    {
                                        'name': 'Rock',
                                        'song_count': 1250,
                                        'image_url': 'https://example.com/rock.jpg',
                                        'description': 'Rock music is a broad genre of popular music that originated as "rock and roll" in the United States.'
                                    },
                                    {
                                        'name': 'Pop',
                                        'song_count': 980,
                                        'image_url': 'https://example.com/pop.jpg',
                                        'description': 'Pop music is a genre of popular music that originated in its modern form in the mid-1950s.'
                                    },
                                    {
                                        'name': 'Jazz',
                                        'song_count': 450,
                                        'image_url': 'https://example.com/jazz.jpg',
                                        'description': 'Jazz is a music genre that originated in the African-American communities of New Orleans.'
                                    }
                                ]
                            }
                        }
                    },
                    'fallback_to_songs': {
                        'summary': 'Genres extracted from Song database (Genre table empty)',
                        'value': {
                            'success': True,
                            'message': 'Found 8 genres',
                            'data': {
                                'genres': [
                                    {
                                        'name': 'Alternative',
                                        'song_count': 85,
                                        'image_url': '',
                                        'description': 'Alternative music'
                                    },
                                    {
                                        'name': 'Electronic',
                                        'song_count': 120,
                                        'image_url': '',
                                        'description': 'Electronic music'
                                    },
                                    {
                                        'name': 'Hip-Hop',
                                        'song_count': 95,
                                        'image_url': '',
                                        'description': 'Hip-Hop music'
                                    }
                                ]
                            }
                        }
                    },
                    'no_genres': {
                        'summary': 'No genres found',
                        'value': {
                            'success': True,
                            'message': 'Found 0 genres',
                            'data': {
                                'genres': []
                            }
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        genres = Genre.objects.all().order_by('name')

        # If no genres in Genre table yet, return from Song genres
        if genres.count() == 0:
            # Fallback to genres from Song model
            from django.db.models import Count
            genre_stats = Song.objects.exclude(genre='').values('genre').annotate(
                song_count=Count('id')
            ).order_by('genre')

            genre_list = []
            for item in genre_stats:
                genre_list.append({
                    'name': item['genre'],
                    'song_count': item['song_count'],
                    'image_url': '',
                    'description': f'{item["genre"]} music'
                })

            return SuccessResponse(
                data={'genres': genre_list},
                message=f'Found {len(genre_list)} genres'
            )

        serializer = GenreSerializer(genres, many=True)
        return SuccessResponse(
            data={'genres': serializer.data},
            message=f'Found {genres.count()} genres'
        )


class GenreDetailView(APIView):
    """
    GET /api/discover/genres/{genre_name}/

    Get genre details with top songs.
    Supports pagination and sorting by popularity.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Get genre details",
        description="Returns detailed information about a specific genre including description, song count, image, follower count, and top songs in that genre. **Note:** If the genre is not found in the Genre table, it falls back to calculating statistics from the Song database. Songs can be sorted by popularity, recency, or title, and you can limit the number of results.",
        parameters=[
            OpenApiParameter(
                name='genre_name',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Name of the genre (case-insensitive)',
                required=True,
                example='Rock'
            ),
            OpenApiParameter(
                name='sort',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort order for songs within the genre',
                required=False,
                enum=['popularity', 'recent', 'title'],
                example='popularity'
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of songs to return (default: 20)',
                required=False,
                example=20
            )
        ],
        examples=[
            OpenApiExample(
                'Get genre with popular songs',
                description='Retrieve genre details with most popular songs',
                value={'sort': 'popularity', 'limit': 20}
            ),
            OpenApiExample(
                'Get genre with recent songs',
                description='Retrieve genre details with recently added songs',
                value={'sort': 'recent', 'limit': 10}
            ),
            OpenApiExample(
                'Get genre with alphabetical songs',
                description='Retrieve genre details with songs sorted by title',
                value={'sort': 'title', 'limit': 50}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'from_genre_table': {
                        'summary': 'Genre from Genre table (complete data)',
                        'value': {
                            'success': True,
                            'message': 'Genre retrieved successfully',
                            'data': {
                                'genre': {
                                    'name': 'Rock',
                                    'description': 'Rock music is a broad genre of popular music that originated as "rock and roll" in the 1950s.',
                                    'song_count': 1250,
                                    'image_url': 'https://example.com/rock.jpg',
                                    'follower_count': 45000
                                },
                                'songs': [
                                    {
                                        'id': 101,
                                        'title': 'Bohemian Rhapsody',
                                        'artist': 'Queen',
                                        'album': 'A Night at the Opera',
                                        'duration_seconds': 354,
                                        'release_year': 1975
                                    },
                                    {
                                        'id': 102,
                                        'title': 'Stairway to Heaven',
                                        'artist': 'Led Zeppelin',
                                        'album': 'Led Zeppelin IV',
                                        'duration_seconds': 482,
                                        'release_year': 1971
                                    }
                                ],
                                'total': 1250
                            }
                        }
                    },
                    'fallback_to_songs': {
                        'summary': 'Genre from Song database (Genre table missing)',
                        'value': {
                            'success': True,
                            'message': 'Genre retrieved successfully',
                            'data': {
                                'genre': {
                                    'name': 'Electronic',
                                    'description': 'Electronic music',
                                    'song_count': 120,
                                    'image_url': '',
                                    'follower_count': 0
                                },
                                'songs': [
                                    {
                                        'id': 201,
                                        'title': 'Around the World',
                                        'artist': 'Daft Punk',
                                        'album': 'Homework',
                                        'duration_seconds': 427,
                                        'release_year': 1997
                                    }
                                ],
                                'total': 120
                            }
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'genre_not_found': {
                        'summary': 'Genre does not exist in Genre table or Song database',
                        'value': {
                            'success': False,
                            'message': 'Genre not found'
                        }
                    }
                }
            }
        }
    )
    def get(self, request, genre_name):
        # Try to get from Genre table first
        try:
            genre = Genre.objects.get(name__iexact=genre_name)
            genre_data = GenreSerializer(genre).data
        except Genre.DoesNotExist:
            # Fallback: create genre data from Song model
            song_count = Song.objects.filter(genre__iexact=genre_name).count()
            genre_data = {
                'name': genre_name,
                'description': f'{genre_name} music',
                'song_count': song_count,
                'image_url': '',
                'follower_count': 0
            }

        # Get songs in this genre
        sort = request.query_params.get('sort', 'popularity')  # popularity, recent, title
        limit = int(request.query_params.get('limit', 20))

        songs = Song.objects.filter(genre__iexact=genre_name).select_related(
            'artist', 'album'
        )

        # Sort songs
        if sort == 'popularity':
            songs = songs.order_by('-popularity_score', '-release_date')
        elif sort == 'recent':
            songs = songs.order_by('-release_date', '-popularity_score')
        elif sort == 'title':
            songs = songs.order_by('title')
        else:
            songs = songs.order_by('-popularity_score')

        songs = songs[:limit]

        return SuccessResponse(
            data={
                'genre': genre_data,
                'songs': SongMinimalSerializer(songs, many=True).data,
                'total': songs.count()
            },
            message=f'Found {songs.count()} songs in {genre_name}'
        )


class NewReleasesView(APIView):
    """
    GET /api/discover/new-releases/

    Get recently released songs and recently created playlists.
    Supports filtering by genre and pagination.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Get new releases",
        description="Returns recently released songs and newly created public playlists within a specified time window. Songs are filtered by release date and sorted by recency and popularity. Playlists are filtered by creation date. Use this endpoint for music discovery and keeping users updated with new content.",
        parameters=[
            OpenApiParameter(
                name='days',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of days to look back from today (default: 90, maximum: 365)',
                required=False,
                example=30
            ),
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter songs by genre (exact match, case-insensitive)',
                required=False,
                example='Pop'
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of songs and playlists to return each (default: 20)',
                required=False,
                example=20
            )
        ],
        examples=[
            OpenApiExample(
                'Recent releases',
                description='Get releases from the last 30 days',
                value={'days': 30, 'limit': 20}
            ),
            OpenApiExample(
                'New releases by genre',
                description='Get recent Rock releases',
                value={
                    'days': 90,
                    'genre': 'Rock',
                    'limit': 30
                }
            ),
            OpenApiExample(
                'All time new releases',
                description='Get all new releases (up to 1 year)',
                value={'days': 365}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'new_releases': {
                        'summary': 'New releases found',
                        'value': {
                            'success': True,
                            'message': 'Found 45 new releases',
                            'data': {
                                'since_date': '2026-03-08',
                                'days': 30,
                                'songs': [
                                    {
                                        'id': 501,
                                        'title': 'New Song',
                                        'artist': 'Modern Artist',
                                        'album': 'Latest Album',
                                        'duration_seconds': 210,
                                        'release_year': 2026
                                    },
                                    {
                                        'id': 502,
                                        'title': 'Summer Hit',
                                        'artist': 'Pop Star',
                                        'album': 'Summer Vibes',
                                        'duration_seconds': 195,
                                        'release_year': 2026
                                    }
                                ],
                                'playlists': [
                                    {
                                        'id': 789,
                                        'name': 'New Music April 2026',
                                        'description': 'Fresh releases this month',
                                        'owner_id': 1,
                                        'visibility': 'public',
                                        'playlist_type': 'solo',
                                        'track_count': 40
                                    }
                                ],
                                'total': 45
                            }
                        }
                    },
                    'no_recent_releases': {
                        'summary': 'No new releases in time period',
                        'value': {
                            'success': True,
                            'message': 'Found 0 new releases',
                            'data': {
                                'since_date': '2026-01-07',
                                'days': 90,
                                'songs': [],
                                'playlists': [],
                                'total': 0
                            }
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        from datetime import datetime, timedelta

        # Get date range (default: last 90 days)
        days = int(request.query_params.get('days', 90))
        since_date = datetime.now().date() - timedelta(days=days)

        genre = request.query_params.get('genre')
        limit = int(request.query_params.get('limit', 20))

        # Query songs with release_date
        songs = Song.objects.filter(
            release_date__gte=since_date
        ).select_related(
            'artist', 'album'
        ).order_by('-release_date', '-popularity_score')

        # Filter by genre if specified
        if genre:
            songs = songs.filter(genre__iexact=genre)

        # For songs without release_date, use release_year as fallback
        songs_with_year = Song.objects.filter(
            release_date__isnull=True,
            release_year__gte=datetime.now().year - 1
        ).select_related(
            'artist', 'album'
        ).order_by('-release_year', '-popularity_score')[:limit//2]

        # Combine results
        songs_list = list(songs[:limit]) + list(songs_with_year)

        # Get recently created playlists (within the same time period)
        playlists = Playlist.objects.filter(
            created_at__gte=datetime.now().date() - timedelta(days=days),
            visibility='public',
            is_system_generated=False  # Exclude system playlists
        ).order_by('-created_at')[:limit]

        return SuccessResponse(
            data={
                'since_date': since_date.isoformat(),
                'days': days,
                'songs': SongMinimalSerializer(songs_list[:limit], many=True).data,
                'playlists': PlaylistSerializer(playlists, many=True).data,
                'total': len(songs_list[:limit]) + playlists.count()
            },
            message=f'Found {len(songs_list[:limit])} new releases and {playlists.count()} new playlists'
        )


class TrendingView(APIView):
    """
    GET /api/discover/trending/

    Get trending content based on popularity score (songs) and likes/follows (playlists).
    Supports filtering by genre and time period.
    Returns both trending songs and trending playlists.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Get trending content",
        description="Returns currently trending songs (sorted by popularity score) and trending playlists (sorted by likes and followers). Supports filtering by genre and time period (all time, this week, this month). Use this endpoint for music discovery, homepage features, and keeping users engaged with popular content.",
        parameters=[
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter results by genre (exact match, case-insensitive)',
                required=False,
                example='Pop'
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of songs and playlists to return each (default: 20)',
                required=False,
                example=20
            ),
            OpenApiParameter(
                name='period',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Time period for trending content',
                required=False,
                enum=['all', 'week', 'month'],
                example='week'
            )
        ],
        examples=[
            OpenApiExample(
                'Trending this week',
                description='Get most popular content from the last 7 days',
                value={'period': 'week', 'limit': 20}
            ),
            OpenApiExample(
                'Trending by genre',
                description='Get trending Rock music',
                value={
                    'genre': 'Rock',
                    'period': 'month',
                    'limit': 30
                }
            ),
            OpenApiExample(
                'All time trending',
                description='Get most popular content of all time',
                value={'period': 'all', 'limit': 50}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'trending_content': {
                        'summary': 'Trending songs and playlists',
                        'value': {
                            'success': True,
                            'message': 'Found 40 trending items',
                            'data': {
                                'period': 'week',
                                'songs': [
                                    {
                                        'id': 601,
                                        'title': 'Viral Hit',
                                        'artist': 'Trending Artist',
                                        'album': 'Breaking Through',
                                        'duration_seconds': 198,
                                        'release_year': 2026
                                    },
                                    {
                                        'id': 602,
                                        'title': 'Summer Anthem',
                                        'artist': 'Pop Sensation',
                                        'album': 'Hot Summer',
                                        'duration_seconds': 215,
                                        'release_year': 2026
                                    }
                                ],
                                'playlists': [
                                    {
                                        'id': 890,
                                        'name': 'Viral Hits 2026',
                                        'description': 'The songs everyone is listening to',
                                        'owner_id': 12,
                                        'visibility': 'public',
                                        'playlist_type': 'solo',
                                        'track_count': 50
                                    }
                                ],
                                'total': 40
                            }
                        }
                    },
                    'no_trending': {
                        'summary': 'No trending content found',
                        'value': {
                            'success': True,
                            'message': 'Found 0 trending items',
                            'data': {
                                'period': 'week',
                                'songs': [],
                                'playlists': [],
                                'total': 0
                            }
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        from datetime import datetime, timedelta
        from django.db.models import Count, Q

        genre = request.query_params.get('genre')
        limit = int(request.query_params.get('limit', 20))
        time_period = request.query_params.get('period', 'all')  # all, week, month

        # Get trending songs
        songs = Song.objects.select_related('artist', 'album')

        # Filter by time period
        if time_period == 'week':
            since_date = datetime.now().date() - timedelta(days=7)
            songs = songs.filter(release_date__gte=since_date)
        elif time_period == 'month':
            since_date = datetime.now().date() - timedelta(days=30)
            songs = songs.filter(release_date__gte=since_date)

        # Filter by genre if specified
        if genre:
            songs = songs.filter(genre__iexact=genre)

        # Order by popularity score
        songs = songs.order_by('-popularity_score', '-release_date')

        # Filter out songs with very low popularity
        songs = songs.filter(popularity_score__gt=0)

        songs = songs[:limit]

        # Get trending playlists (sorted by likes and follows count)
        # If no playlists have likes/follows, fall back to recently created playlists
        playlists_with_engagement = Playlist.objects.filter(
            visibility='public',
            is_system_generated=False  # Exclude system playlists from trending
        ).annotate(
            likes_count=Count('likes', distinct=True),
            follows_count=Count('followers', distinct=True)
        ).filter(
            Q(likes_count__gt=0) | Q(follows_count__gt=0)
        ).order_by('-likes_count', '-follows_count', '-created_at')

        # If no trending playlists with engagement, get recent public playlists
        if playlists_with_engagement.count() == 0:
            playlists = Playlist.objects.filter(
                visibility='public',
                is_system_generated=False
            ).order_by('-created_at')[:limit]
        else:
            playlists = playlists_with_engagement[:limit]

        return SuccessResponse(
            data={
                'period': time_period,
                'songs': SongMinimalSerializer(songs, many=True).data,
                'playlists': PlaylistSerializer(playlists, many=True).data,
                'total': songs.count() + playlists.count()
            },
            message=f'Found {songs.count()} trending songs and {playlists.count()} trending playlists'
        )


class SimilarSongsView(APIView):
    """
    GET /api/discover/similar/{song_id}/

    Get songs similar to the given song.
    Similarity based on genre and artist.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Get similar songs",
        description="Finds songs similar to the specified song based on genre and artist. Similar songs include other tracks by the same artist and tracks in the same genre. Results are ordered by similarity and limited to 20 songs. Use this endpoint for music discovery, recommendation features, and building 'more like this' experiences.",
        parameters=[
            OpenApiParameter(
                name='song_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Unique identifier of the song to find similar songs for',
                required=True,
                example=101
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of similar songs to return (default: 20)',
                required=False,
                example=20
            )
        ],
        examples=[
            OpenApiExample(
                'Get similar songs',
                description='Find songs similar to the specified track',
                value={'limit': 20}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'similar_songs_found': {
                        'summary': 'Similar songs retrieved successfully',
                        'value': {
                            'success': True,
                            'message': 'Found 15 similar songs',
                            'data': {
                                'song_id': 101,
                                'similar_songs': [
                                    {
                                        'id': 102,
                                        'title': 'Another Song',
                                        'artist': 'Same Artist',
                                        'album': 'Same Album',
                                        'duration_seconds': 245,
                                        'genre': 'Rock',
                                        'release_year': 1975
                                    },
                                    {
                                        'id': 205,
                                        'title': 'Related Track',
                                        'artist': 'Different Artist',
                                        'album': 'Similar Style',
                                        'duration_seconds': 198,
                                        'genre': 'Rock',
                                        'release_year': 1980
                                    }
                                ],
                                'total': 15
                            }
                        }
                    },
                    'no_similar_songs': {
                        'summary': 'No similar songs found',
                        'value': {
                            'success': True,
                            'message': 'Found 0 similar songs',
                            'data': {
                                'song_id': 999,
                                'similar_songs': [],
                                'total': 0
                            }
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'song_not_found': {
                        'summary': 'Song ID does not exist',
                        'value': {
                            'success': False,
                            'message': 'Song not found'
                        }
                    }
                }
            }
        }
    )
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of similar songs to return',
                required=False
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'song_id': {'type': 'integer'},
                            'song_title': {'type': 'string'},
                            'song_genre': {'type': 'string'},
                            'similar_songs': {
                                'type': 'array',
                                'items': SongMinimalSerializer
                            },
                            'total': {'type': 'integer'}
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def get(self, request, song_id):
        try:
            song = Song.objects.get(id=song_id)
        except Song.DoesNotExist:
            return NotFoundResponse(message='Song not found')

        limit = int(request.query_params.get('limit', 10))

        # Find songs by same artist (excluding current song)
        same_artist = Song.objects.filter(
            artist=song.artist
        ).exclude(id=song.id).select_related('artist', 'album')[:limit//2]

        # Find songs in same genre (excluding current song and artist's songs)
        same_genre = Song.objects.filter(
            genre__iexact=song.genre
        ).exclude(
            id=song.id
        ).exclude(
            artist=song.artist
        ).select_related('artist', 'album').order_by(
            '-popularity_score'
        )[:limit//2]

        # Combine and deduplicate
        similar_songs = list(set(list(same_artist) + list(same_genre)))[:limit]

        # Sort by popularity
        similar_songs.sort(key=lambda s: s.popularity_score, reverse=True)

        return SuccessResponse(
            data={
                'song_id': song_id,
                'song_title': song.title,
                'song_genre': song.genre,
                'similar_songs': SongMinimalSerializer(similar_songs, many=True).data,
                'total': len(similar_songs)
            },
            message=f'Found {len(similar_songs)} similar songs'
        )


class RecommendationsView(APIView):
    """
    GET /api/discover/recommendations/

    Get personalized song recommendations based on:
    - User's liked playlists' genres
    - User's followed playlists' genres
    - High popularity songs in preferred genres
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Search"],
        summary="Get personalized recommendations",
        description="Returns personalized song recommendations based on the authenticated user's music taste. Analyzes genres from liked and followed playlists to identify preferences, then suggests popular songs in those genres that the user hasn't discovered yet. If no preference data exists, falls back to trending songs. Results are limited and sorted by relevance and popularity.",
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of recommended songs to return (default: 20)',
                required=False,
                example=20
            )
        ],
        examples=[
            OpenApiExample(
                'Get recommendations',
                description='Retrieve personalized song suggestions',
                value={'limit': 30}
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'personalized': {
                        'summary': 'Personalized recommendations based on user taste',
                        'value': {
                            'success': True,
                            'message': 'Found 25 recommendations',
                            'data': {
                                'recommendation_type': 'personalized',
                                'preferred_genres': ['Rock', 'Pop', 'Electronic'],
                                'songs': [
                                    {
                                        'id': 701,
                                        'title': 'New Discovery',
                                        'artist': 'Artist You Might Like',
                                        'album': 'Great Album',
                                        'duration_seconds': 220,
                                        'genre': 'Rock',
                                        'release_year': 2025
                                    },
                                    {
                                        'id': 702,
                                        'title': 'Recommended Track',
                                        'artist': 'Popular in Genre',
                                        'album': 'Hits Collection',
                                        'duration_seconds': 195,
                                        'genre': 'Pop',
                                        'release_year': 2026
                                    }
                                ],
                                'total': 25
                            }
                        }
                    },
                    'fallback_trending': {
                        'summary': 'No preference data, showing trending songs',
                        'value': {
                            'success': True,
                            'message': 'Found 20 recommendations',
                            'data': {
                                'recommendation_type': 'trending',
                                'preferred_genres': [],
                                'songs': [
                                    {
                                        'id': 801,
                                        'title': 'Viral Song',
                                        'artist': 'Trending Artist',
                                        'album': 'Popular Album',
                                        'duration_seconds': 210,
                                        'genre': 'Pop',
                                        'release_year': 2026
                                    }
                                ],
                                'total': 20
                            }
                        }
                    },
                    'no_recommendations': {
                        'summary': 'No songs available for recommendation',
                        'value': {
                            'success': True,
                            'message': 'Found 0 recommendations',
                            'data': {
                                'recommendation_type': 'personalized',
                                'preferred_genres': ['Rock'],
                                'songs': [],
                                'total': 0
                            }
                        }
                    }
                }
            }
        }
    )
                            'songs': {
                                'type': 'array',
                                'items': SongMinimalSerializer
                            },
                            'total': {'type': 'integer'}
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        limit = int(request.query_params.get('limit', 20))

        # Get genres from user's liked playlists
        from playlistapp.models import UserPlaylistLike, UserPlaylistFollow
        from trackapp.models import Track

        liked_playlist_ids = UserPlaylistLike.objects.filter(
            user_id=request.user.id
        ).values_list('playlist_id', flat=True)

        # Get genres from user's followed playlists
        # OPTIMIZATION: Use union() instead of set operations for better query performance
        followed_playlist_ids = UserPlaylistFollow.objects.filter(
            user_id=request.user.id
        ).values_list('playlist_id', flat=True)

        # Combine to get user's preferred playlists
        preferred_playlist_ids = set(liked_playlist_ids) | set(followed_playlist_ids)

        if not preferred_playlist_ids:
            # No preferences, return trending songs
            trending = Song.objects.filter(
                popularity_score__gt=0
            ).select_related(
                'artist', 'album'
            ).order_by('-popularity_score')[:limit]

            return SuccessResponse(
                data={
                    'recommendation_type': 'trending',
                    'songs': SongMinimalSerializer(trending, many=True).data,
                    'total': trending.count()
                },
                message='Trending songs (no user preferences yet)'
            )

        # Get genres from user's preferred playlists
        preferred_genres = list(
            Track.objects.filter(
                playlist_id__in=preferred_playlist_ids
            ).exclude(
                song__genre=''
            ).values_list('song__genre', flat=True).distinct()
        )

        if not preferred_genres:
            # No genres found, return trending
            trending = Song.objects.filter(
                popularity_score__gt=0
            ).select_related(
                'artist', 'album'
            ).order_by('-popularity_score')[:limit]

            return SuccessResponse(
                data={
                    'recommendation_type': 'trending',
                    'songs': SongMinimalSerializer(trending, many=True).data,
                    'total': trending.count()
                },
                message='Trending songs (no genres found in your playlists)'
            )

        # Count genre occurrences for weighting
        # OPTIMIZATION: Use aggregation to count genres in database instead of Python Counter
        from django.db.models import Count

        genre_weights_data = Track.objects.filter(
            playlist_id__in=preferred_playlist_ids
        ).exclude(
            song__genre=''
        ).values('song__genre').annotate(
            count=Count('id')
        )

        genre_weights = {item['song__genre']: item['count'] for item in genre_weights_data}

        # Get top songs in preferred genres, weighted by preference
        recommended_songs = []
        seen_songs = set()

        # Prioritize genres by weight (sorted descending by count)
        for genre, _ in sorted(genre_weights.items(), key=lambda x: x[1], reverse=True):
            if len(recommended_songs) >= limit:
                break

            # Get top songs in this genre that user hasn't heard
            genre_songs = Song.objects.filter(
                genre__iexact=genre
            ).select_related(
                'artist', 'album'
            ).order_by('-popularity_score')

            for song in genre_songs:
                if song.id not in seen_songs and len(recommended_songs) < limit:
                    # Check if user has this song in any of their playlists
                    user_has_song = Track.objects.filter(
                        playlist_id__in=Playlist.objects.filter(
                            owner_id=request.user.id
                        ).values_list('id', flat=True),
                        song=song
                    ).exists()

                    if not user_has_song:
                        recommended_songs.append(song)
                        seen_songs.add(song.id)

        return SuccessResponse(
            data={
                'recommendation_type': 'personalized',
                'preferred_genres': preferred_genres,
                'songs': SongMinimalSerializer(recommended_songs, many=True).data,
                'total': len(recommended_songs)
            },
            message=f'Found {len(recommended_songs)} personalized recommendations'
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@extend_schema(
    tags=["Health"],
    summary="Search service health check",
    description="Check if the search service and database are healthy",
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'},
                'data': {
                    'type': 'object',
                    'properties': {
                        'status': {'type': 'string'},
                        'service': {'type': 'string'},
                        'database': {'type': 'string'}
                    }
                }
            }
        },
        503: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'}
            }
        }
    }
)
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return SuccessResponse(
            data={'status': 'healthy', 'service': 'search', 'database': 'connected'},
            message='Service is healthy'
        )
    except Exception as e:
        return ServiceUnavailableResponse(
            message=f'Database connection failed: {str(e)}'
        )
