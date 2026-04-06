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
        description="Returns a list of all music genres for browsing.",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'array',
                        'items': {'type': 'string'}
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
        description="Returns a list of artists with optional search filtering.",
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query to filter artists by name',
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
                        'type': 'array',
                        'items': ArtistSerializer
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
        description="Returns detailed information about a specific artist.",
        parameters=[
            OpenApiParameter(
                name='artist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Artist ID',
                required=True
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': ArtistSerializer
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
        description="Returns a list of albums with optional search filtering.",
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query to filter albums by name or artist',
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
                        'type': 'array',
                        'items': AlbumSerializer
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
        description="Returns detailed information about a specific album.",
        parameters=[
            OpenApiParameter(
                name='album_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Album ID',
                required=True
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': AlbumSerializer
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
        description="Search for songs with optional filtering by genre, sorting, and text search.",
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query (title, artist, or album)',
                required=False
            ),
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by genre',
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
        description="Search for playlists with optional text search and type filtering.",
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query (name or description)',
                required=False
            ),
            OpenApiParameter(
                name='type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by playlist type',
                required=False,
                enum=['solo', 'collaborative']
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
                        'items': PlaylistSerializer
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
        description="Returns a list of all music genres with statistics. Useful for genre browsing and exploration.",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'genres': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'name': {'type': 'string'},
                                        'song_count': {'type': 'integer'},
                                        'image_url': {'type': 'string'},
                                        'description': {'type': 'string'}
                                    }
                                }
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
        description="Returns genre information along with top songs in that genre. Supports sorting by popularity, recency, or title.",
        parameters=[
            OpenApiParameter(
                name='genre_name',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Genre name',
                required=True
            ),
            OpenApiParameter(
                name='sort',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Sort songs by',
                required=False,
                enum=['popularity', 'recent', 'title']
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of songs to return',
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
                            'genre': {
                                'type': 'object',
                                'properties': {
                                    'name': {'type': 'string'},
                                    'description': {'type': 'string'},
                                    'song_count': {'type': 'integer'},
                                    'image_url': {'type': 'string'},
                                    'follower_count': {'type': 'integer'}
                                }
                            },
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
        description="Returns recently released songs and newly created public playlists. Supports filtering by genre and time period.",
        parameters=[
            OpenApiParameter(
                name='days',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of days to look back (default: 90)',
                required=False
            ),
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by genre',
                required=False
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of results to return',
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
                            'since_date': {'type': 'string', 'format': 'date'},
                            'days': {'type': 'integer'},
                            'songs': {
                                'type': 'array',
                                'items': SongMinimalSerializer
                            },
                            'playlists': {
                                'type': 'array',
                                'items': PlaylistSerializer
                            },
                            'total': {'type': 'integer'}
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
        description="Returns trending songs (by popularity) and trending playlists (by likes/follows). Supports genre and time period filtering.",
        parameters=[
            OpenApiParameter(
                name='genre',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by genre',
                required=False
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of results to return',
                required=False
            ),
            OpenApiParameter(
                name='period',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Time period',
                required=False,
                enum=['all', 'week', 'month']
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
                            'period': {'type': 'string'},
                            'songs': {
                                'type': 'array',
                                'items': SongMinimalSerializer
                            },
                            'playlists': {
                                'type': 'array',
                                'items': PlaylistSerializer
                            },
                            'total': {'type': 'integer'}
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
        description="Returns songs similar to the given song, based on genre and artist. Useful for discovery and recommendations.",
        parameters=[
            OpenApiParameter(
                name='song_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Song ID to find similar songs for',
                required=True
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
        description="Returns personalized song recommendations based on user's liked and followed playlists. Analyzes genre preferences and suggests popular songs in preferred genres that the user hasn't heard yet.",
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of recommendations to return',
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
                            'recommendation_type': {
                                'type': 'string',
                                'enum': ['personalized', 'trending']
                            },
                            'preferred_genres': {
                                'type': 'array',
                                'items': {'type': 'string'}
                            },
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
