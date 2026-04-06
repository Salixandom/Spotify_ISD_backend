"""
Enhanced OpenAPI Schema Extensions for Core Playlist Endpoints
This file contains comprehensive @extend_schema decorators with examples
and error responses for the most critical playlist endpoints.

Apply these decorators to the corresponding methods in views.py
"""

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample

# ============================================================================
# PLAYLIST VIEW SET - LIST METHOD
# ============================================================================

PLAYLIST_LIST_SCHEMA = {
    'tags': ['Playlists'],
    'summary': 'List playlists',
    'description': """
    Returns your playlists with powerful filtering and sorting options.

    **Default behavior:** Shows playlists you own + collaborative playlists
    **Special filters:**
    - `filter=followed` - All playlists you follow (not just owned)
    - `filter=liked` - All playlists you liked

    **Regular filters:** visibility (public/private), type (solo/collaborative),
    is_system_generated, search in name/description, date ranges, track count ranges

    **Sorting:** name, created_at, updated_at, track_count (asc/desc)

    Archived playlists are excluded by default. Use `include_archived=true` to include them.
    """,
    'parameters': [
        OpenApiParameter(
            name='filter',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Special filter: "followed" or "liked"',
            required=False,
            enum=['followed', 'liked']
        ),
        OpenApiParameter(
            name='visibility',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filter by visibility',
            required=False,
            enum=['public', 'private']
        ),
        OpenApiParameter(
            name='type',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filter by playlist type',
            required=False,
            enum=['solo', 'collaborative']
        ),
        OpenApiParameter(
            name='q',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Search in name and description',
            required=False
        ),
        OpenApiParameter(
            name='sort',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Sort field',
            required=False,
            enum=['name', 'created_at', 'updated_at', 'track_count']
        ),
        OpenApiParameter(
            name='order',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Sort order',
            required=False,
            enum=['asc', 'desc']
        ),
        OpenApiParameter(
            name='limit',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Number of results to return',
            required=False
        ),
        OpenApiParameter(
            name='offset',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Offset for pagination',
            required=False
        )
    ],
    'examples': [
        OpenApiExample(
            'My playlists',
            description='Get all my playlists (owned + collaborative)',
            value={}
        ),
        OpenApiExample(
            'Public playlists',
            description='Get only my public playlists',
            value={'visibility': 'public'}
        ),
        OpenApiExample(
            'Followed playlists',
            description='Get all playlists I follow',
            value={'filter': 'followed'}
        ),
        OpenApiExample(
            'Search and sort',
            description='Search playlists by name, sorted by track count',
            value={'q': 'rock', 'sort': 'track_count', 'order': 'desc'}
        )
    ],
    'responses': {
        200: {
            'type': 'object',
            'properties': {
                'success': {
                    'type': 'boolean',
                    'example': True
                },
                'message': {
                    'type': 'string',
                    'example': 'Playlists retrieved successfully'
                },
                'data': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer', 'example': 123},
                            'name': {'type': 'string', 'example': 'Classic Rock'},
                            'description': {
                                'type': 'string',
                                'example': 'Best rock songs of all time'
                            },
                            'owner_id': {'type': 'integer', 'example': 1},
                            'visibility': {
                                'type': 'string',
                                'enum': ['public', 'private', 'collaborative'],
                                'example': 'public'
                            },
                            'playlist_type': {
                                'type': 'string',
                                'enum': ['solo', 'collaborative'],
                                'example': 'solo'
                            },
                            'track_count': {'type': 'integer', 'example': 150},
                            'created_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-01T10:00:00Z'
                            },
                            'updated_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-07T15:30:00Z'
                            }
                        }
                    }
                }
            }
        }
    }
}

# ============================================================================
# PLAYLIST VIEW SET - CREATE METHOD
# ============================================================================

PLAYLIST_CREATE_SCHEMA = {
    'tags': ['Playlists'],
    'summary': 'Create playlist',
    'description': 'Create a new playlist. You become the owner. Collaborative playlists can be shared with others.',
    'request': {
        'application/json': {
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': 'Playlist name (max 255 characters)',
                    'maxLength': 255,
                    'example': 'My Awesome Playlist'
                },
                'description': {
                    'type': 'string',
                    'description': 'Playlist description (optional, max 1000 characters)',
                    'maxLength': 1000,
                    'example': 'A collection of my favorite songs'
                },
                'visibility': {
                    'type': 'string',
                    'enum': ['public', 'private'],
                    'description': 'Who can view this playlist',
                    'example': 'public'
                },
                'playlist_type': {
                    'type': 'string',
                    'enum': ['solo', 'collaborative'],
                    'description': 'Playlist type: solo (only you) or collaborative (others can contribute)',
                    'example': 'solo'
                },
                'is_system_generated': {
                    'type': 'boolean',
                    'description': 'Mark as system-generated (for auto-created playlists)',
                    'example': False
                }
            },
            'required': ['name']
        }
    },
    'examples': [
        OpenApiExample(
            'Create public playlist',
            value={
                'name': 'Summer Vibes 2026',
                'description': 'Perfect songs for summer',
                'visibility': 'public',
                'playlist_type': 'solo'
            }
        ),
        OpenApiExample(
            'Create collaborative playlist',
            value={
                'name': 'Team Workout Mix',
                'description': 'Songs we can exercise to',
                'visibility': 'private',
                'playlist_type': 'collaborative'
            }
        )
    ],
    'responses': {
        201: {
            'type': 'object',
            'properties': {
                'success': {
                    'type': 'boolean',
                    'example': True
                },
                'message': {
                    'type': 'string',
                    'example': 'Playlist created successfully'
                },
                'data': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer', 'example': 456},
                        'name': {'type': 'string', 'example': 'Summer Vibes 2026'},
                        'description': {'type': 'string', 'example': 'Perfect songs for summer'},
                        'owner_id': {'type': 'integer', 'example': 1},
                        'visibility': {
                            'type': 'string',
                            'example': 'public',
                            'enum': ['public', 'private', 'collaborative']
                        },
                        'playlist_type': {
                            'type': 'string',
                            'example': 'solo',
                            'enum': ['solo', 'collaborative']
                        },
                        'track_count': {'type': 'integer', 'example': 0},
                        'created_at': {
                            'type': 'string',
                            'format': 'date-time',
                            'example': '2026-04-07T16:00:00Z'
                        }
                    }
                }
            }
        },
        400: {
            'type': 'object',
            'examples': {
                'missing_name': {
                    'summary': 'Name not provided',
                    'value': {
                        'success': False,
                        'message': 'Validation failed',
                        'errors': {
                            'name': ['This field is required.']
                        }
                    }
                }
            }
        }
    }
}

# ============================================================================
# PLAYLIST VIEW SET - RETRIEVE METHOD
# ============================================================================

PLAYLIST_RETRIEVE_SCHEMA = {
    'tags': ['Playlists'],
    'summary': 'Get playlist details',
    'description': 'Get detailed information about a specific playlist. Requires access: owner, collaborator, or public playlist.',
    'responses': {
        200: {
            'type': 'object',
            'examples': {
                'public_playlist': {
                    'summary': 'Public playlist (anyone can view)',
                    'value': {
                        'success': True,
                        'message': 'Playlist retrieved successfully',
                        'data': {
                            'id': 123,
                            'name': 'Classic Rock Anthems',
                            'description': 'The greatest rock songs ever made',
                            'owner_id': 45,
                            'visibility': 'public',
                            'playlist_type': 'solo',
                            'track_count': 200,
                            'followers_count': 1234,
                            'likes_count': 567,
                            'created_at': '2026-01-15T10:00:00Z',
                            'updated_at': '2026-04-07T14:30:00Z'
                        }
                    }
                },
                'private_playlist': {
                    'summary': 'Your private playlist',
                    'value': {
                        'success': True,
                        'message': 'Playlist retrieved successfully',
                        'data': {
                            'id': 789,
                            'name': 'Private Study Mix',
                            'description': 'Songs for focused studying',
                            'owner_id': 1,
                            'visibility': 'private',
                            'playlist_type': 'solo',
                            'track_count': 25,
                            'followers_count': 0,
                            'likes_count': 0,
                            'created_at': '2026-03-01T08:00:00Z',
                            'updated_at': '2026-04-06T11:20:00Z'
                        }
                    }
                }
            }
        },
        403: {
            'type': 'object',
            'example': {
                'success': False,
                'message': 'You do not have access to this playlist'
            }
        },
        404: {
            'type': 'object',
            'example': {
                'success': False,
                'message': 'Playlist not found'
            }
        }
    }
}

# ============================================================================
# PLAYLIST VIEW SET - UPDATE METHOD
# ============================================================================

PLAYLIST_UPDATE_SCHEMA = {
    'tags': ['Playlists'],
    'summary': 'Update playlist',
    'description': 'Update playlist details. Only owner can update. All fields optional - partial updates supported.',
    'request': {
        'application/json': {
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'maxLength': 255,
                    'example': 'Updated Playlist Name'
                },
                'description': {
                    'type': 'string',
                    'maxLength': 1000,
                    'example': 'Updated description'
                },
                'visibility': {
                    'type': 'string',
                    'enum': ['public', 'private'],
                    'example': 'public'
                }
            }
        }
    },
    'examples': [
        OpenApiExample(
            'Update name and visibility',
            value={
                'name': 'Renamed Playlist',
                'visibility': 'public'
            }
        ),
        OpenApiExample(
            'Update description only',
            value={
                'description': 'New description for this playlist'
            }
        )
    ],
    'responses': {
        200: {
            'type': 'object',
            'properties': {
                'success': {
                    'type': 'boolean',
                    'example': True
                },
                'message': {
                    'type': 'string',
                    'example': 'Playlist updated successfully'
                },
                'data': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer', 'example': 123},
                        'name': {'type': 'string', 'example': 'Renamed Playlist'},
                        'updated_at': {
                            'type': 'string',
                            'format': 'date-time',
                            'example': '2026-04-07T17:00:00Z'
                        }
                    }
                }
            }
        },
        403: {
            'type': 'object',
            'example': {
                'success': False,
                'message': 'Only the playlist owner can update'
            }
        },
        404: {
            'type': 'object',
            'example': {
                'success': False,
                'message': 'Playlist not found'
            }
        }
    }
}

# ============================================================================
# PLAYLIST VIEW SET - DESTROY METHOD
# ============================================================================

PLAYLIST_DESTROY_SCHEMA = {
    'tags': ['Playlists'],
    'summary': 'Delete playlist',
    'description': 'Permanently delete a playlist. Only the owner can delete. This action cannot be undone.',
    'responses': {
        200: {
            'type': 'object',
            'example': {
                'success': True,
                'message': 'Playlist deleted successfully'
            }
        },
        403: {
            'type': 'object',
            'example': {
                'success': False,
                'message': 'Only the playlist owner can delete'
            }
        },
        404: {
            'type': 'object',
            'example': {
                'success': False,
                'message': 'Playlist not found'
            }
        }
    }
}

"""
USAGE INSTRUCTIONS:

1. Import these constants at the top of your views.py:
   from .enhanced_schemas import (
       PLAYLIST_LIST_SCHEMA,
       PLAYLIST_CREATE_SCHEMA,
       PLAYLIST_RETRIEVE_SCHEMA,
       PLAYLIST_UPDATE_SCHEMA,
       PLAYLIST_DESTROY_SCHEMA
   )

2. Apply to PlaylistViewSet methods:

   @extend_schema(**PLAYLIST_LIST_SCHEMA)
   def list(self, request, *args, **kwargs):
       # existing code

   @extend_schema(**PLAYLIST_CREATE_SCHEMA)
   def create(self, request, *args, **kwargs):
       # existing code

   @extend_schema(**PLAYLIST_RETRIEVE_SCHEMA)
   def retrieve(self, request, *args, **kwargs):
       # existing code

   @extend_schema(**PLAYLIST_UPDATE_SCHEMA)
   def update(self, request, *args, **kwargs):
       # existing code

   @extend_schema(**PLAYLIST_DESTROY_SCHEMA)
   def destroy(self, request, *args, **kwargs):
       # existing code

This pattern provides comprehensive documentation for all 5 ViewSet methods.
"""
