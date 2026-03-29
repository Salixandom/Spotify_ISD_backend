# Playlist App API Documentation

**Version:** 1.0
**Last Updated:** 2026-03-30
**Base URL:** `/api/playlists/`

---

## Table of Contents

1. [Authentication](#authentication)
2. [Core Endpoints](#core-endpoints)
3. [Phase 1: Enhanced Filtering & Statistics](#phase-1-enhanced-filtering--statistics)
4. [Phase 2: Core Operations](#phase-2-core-operations)
5. [Phase 3: Social Features](#phase-3-social-features)
6. [Phase 4: Smart Features](#phase-4-smart-features)
7. [Phase 5: Advanced Operations](#phase-5-advanced-operations)
8. [Error Responses](#error-responses)
9. [Rate Limiting](#rate-limiting)

---

## Authentication

All endpoints require authentication via JWT token.

**Header:**
```
Authorization: Bearer <token>
```

**Response Codes:**
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Valid token but insufficient permissions

---

## Core Endpoints

### List Playlists

```http
GET /api/playlists/
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `visibility` | string | - | Filter: `public` or `private` |
| `type` | string | - | Filter: `solo` or `collaborative` |
| `q` | string | - | Search in name/description |
| `min_tracks` | integer | - | Minimum track count |
| `max_tracks` | integer | - | Maximum track count |
| `created_after` | date | - | Filter: YYYY-MM-DD |
| `created_before` | date | - | Filter: YYYY-MM-DD |
| `sort` | string | `updated_at` | Sort field: `name`, `created_at`, `updated_at`, `track_count` |
| `order` | string | `desc` | Sort order: `asc` or `desc` |
| `include_archived` | boolean | `false` | Include archived playlists |
| `filter` | string | - | Special: `followed`, `liked` |
| `limit` | integer | - | Pagination limit |
| `offset` | integer | 0 | Pagination offset |

**Response:** `200 OK`
```json
{
  "count": 42,
  "next": "...",
  "previous": "...",
  "results": [
    {
      "id": 1,
      "owner_id": 123,
      "name": "Rock Classics",
      "description": "Best rock songs",
      "visibility": "public",
      "playlist_type": "solo",
      "cover_url": "https://...",
      "max_songs": 100,
      "created_at": "2026-03-01T10:00:00Z",
      "updated_at": "2026-03-30T12:00:00Z"
    }
  ]
}
```

### Create Playlist

```http
POST /api/playlists/
```

**Request Body:**
```json
{
  "name": "My Playlist",
  "description": "Description",
  "visibility": "public",
  "playlist_type": "solo",
  "max_songs": 100,
  "cover_url": "https://..."
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "owner_id": 123,
  "name": "My Playlist",
  ...
}
```

### Get Playlist

```http
GET /api/playlists/{id}/
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "name": "Rock Classics",
  ...
}
```

### Update Playlist

```http
PATCH /api/playlists/{id}/
```

**Request Body:**
```json
{
  "name": "Updated Name",
  "description": "New description"
}
```

**Response:** `200 OK`

### Delete Playlist

```http
DELETE /api/playlists/{id}/
```

**Response:** `204 No Content`

---

## Phase 1: Enhanced Filtering & Statistics

### Playlist Statistics

```http
GET /api/playlists/{id}/stats/
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "name": "Rock Classics",
  "total_tracks": 50,
  "total_duration_seconds": 10800,
  "total_duration_formatted": "3:00:00",
  "genres": ["Rock", "Classic Rock", "Hard Rock"],
  "unique_artists": 25,
  "unique_albums": 30,
  "last_track_added": "2026-03-30T10:00:00Z",
  "collaborator_count": 0,
  "follower_count": 15,
  "like_count": 42,
  "is_followed": true,
  "is_liked": false,
  "owner_id": 123,
  "cover_url": "https://..."
}
```

### Featured Playlists

```http
GET /api/playlists/featured/
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results |
| `genre` | string | - | Filter by genre |

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "name": "Top Rock",
    ...
  }
]
```

---

## Phase 2: Core Operations

### Duplicate Playlist

```http
POST /api/playlists/{id}/duplicate/
```

**Request Body:**
```json
{
  "name": "My Copy",
  "include_tracks": true,
  "reset_position": false
}
```

**Response:** `201 Created`
```json
{
  "id": 2,
  "name": "My Copy",
  "owner_id": 123,
  ...
}
```

### Batch Delete

```http
DELETE /api/playlists/batch-delete/
```

**Request Body:**
```json
{
  "playlist_ids": [1, 2, 3]
}
```

**Response:** `200 OK`
```json
{
  "deleted": 2,
  "not_found": 1,
  "not_authorized": 0
}
```

### Batch Update

```http
PATCH /api/playlists/batch-update/
```

**Request Body:**
```json
{
  "playlist_ids": [1, 2],
  "updates": {
    "visibility": "private"
  }
}
```

**Response:** `200 OK`
```json
{
  "updated": 2,
  "not_found": 0,
  "not_authorized": 0
}
```

### Set Cover Image

```http
POST /api/playlists/{id}/cover/
```

**Request Body:**
```json
{
  "cover_url": "https://example.com/image.jpg"
}
```

**Response:** `200 OK`

### Remove Cover Image

```http
DELETE /api/playlists/{id}/cover/
```

**Response:** `200 OK`

---

## Phase 3: Social Features

### User Playlists

```http
GET /api/users/{id}/playlists/
```

**Query Parameters:** Same as list playlists

**Response:** `200 OK`
```json
{
  "user_id": 123,
  "total": 10,
  "limit": 50,
  "offset": 0,
  "playlists": [...]
}
```

### Follow Playlist

```http
POST /api/playlists/{id}/follow/
```

**Response:** `201 Created`
```json
{
  "message": "Playlist followed successfully",
  "followed_at": "2026-03-30T10:00:00Z"
}
```

### Unfollow Playlist

```http
DELETE /api/playlists/{id}/follow/
```

**Response:** `200 OK`
```json
{
  "message": "Playlist unfollowed successfully"
}
```

### Like Playlist

```http
POST /api/playlists/{id}/like/
```

**Response:** `201 Created`
```json
{
  "message": "Playlist liked successfully",
  "liked_at": "2026-03-30T10:00:00Z"
}
```

### Unlike Playlist

```http
DELETE /api/playlists/{id}/like/
```

**Response:** `200 OK`
```json
{
  "message": "Playlist unliked successfully"
}
```

---

## Phase 4: Smart Features

### Recommended Playlists

```http
GET /api/playlists/recommended/
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results |

**Response:** `200 OK`
```json
{
  "recommendation_type": "genre_based",
  "preferred_genres": ["Rock", "Pop"],
  "total": 15,
  "playlists": [...]
}
```

### Similar Playlists

```http
GET /api/playlists/{id}/similar/
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Max results |

**Response:** `200 OK`
```json
{
  "playlist_id": 1,
  "playlist_name": "Rock Classics",
  "playlist_genres": ["Rock", "Classic Rock"],
  "total": 8,
  "similar_playlists": [...]
}
```

### Auto-Generated Suggestions

```http
GET /api/playlists/auto-generated/
```

**Response:** `200 OK`
```json
{
  "suggestions": [
    {
      "type": "genre_based",
      "name": "Rock Mix",
      "description": "Auto-generated playlist based on Rock",
      "estimated_track_count": 234,
      "genre": "Rock"
    },
    {
      "type": "mood_based",
      "name": "Chill Vibes",
      "description": "Relaxing tracks",
      "mood": "chill"
    }
  ]
}
```

### Create Auto-Generated Playlist

```http
POST /api/playlists/auto-generated/
```

**Request Body:**
```json
{
  "genre": "Rock",
  "mood": "energetic",
  "name": "My Mix",
  "track_limit": 50
}
```

**Response:** `201 Created`
```json
{
  "id": 5,
  "name": "My Mix",
  ...
}
```

---

## Phase 5: Advanced Operations

### Enhanced Batch Delete

```http
DELETE /api/playlists/batch-delete-advanced/
```

**Request Body:**
```json
{
  "playlist_ids": [1, 2, 3],
  "create_snapshots": true
}
```

**Response:** `200 OK`
```json
{
  "total": 3,
  "deleted": 2,
  "failed": 1,
  "results": [
    {"playlist_id": 1, "status": "deleted", "name": "Playlist 1"},
    {"playlist_id": 2, "status": "deleted", "name": "Playlist 2"},
    {"playlist_id": 3, "status": "failed", "reason": "not_found"}
  ]
}
```

### Export Playlist

```http
GET /api/playlists/{id}/export/
```

**Response:** `200 OK`
```json
{
  "playlist": {
    "id": 1,
    "name": "Rock Classics",
    "description": "...",
    "visibility": "public",
    "tracks": [
      {
        "position": 0,
        "added_at": "2026-03-30T10:00:00Z",
        "song": {
          "id": 1,
          "title": "Song Title",
          "duration_seconds": 240,
          "genre": "Rock",
          "artist": {"id": 1, "name": "Artist Name"},
          "album": {"id": 1, "name": "Album Name", "cover_url": "..."}
        }
      }
    ]
  },
  "export_metadata": {
    "exported_at": "2026-03-30T10:00:00Z",
    "exported_by": 123,
    "track_count": 50,
    "version": "1.0"
  }
}
```

### Import Playlist

```http
POST /api/playlists/import/
```

**Request Body:**
```json
{
  "playlist": {
    "name": "Imported Playlist",
    "description": "...",
    "tracks": [...]
  },
  "name": "My Custom Name"
}
```

**Response:** `201 Created`

### List Snapshots

```http
GET /api/playlists/{id}/snapshots/
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results |

**Response:** `200 OK`
```json
{
  "playlist_id": 1,
  "total": 5,
  "snapshots": [
    {
      "id": 1,
      "created_at": "2026-03-30T10:00:00Z",
      "change_reason": "Manual snapshot",
      "track_count": 50,
      "created_by": 123
    }
  ]
}
```

### Create Snapshot

```http
POST /api/playlists/{id}/snapshots/
```

**Request Body:**
```json
{
  "change_reason": "Before major changes"
}
```

**Response:** `201 Created`

### Cleanup Snapshots

```http
DELETE /api/playlists/{id}/snapshots/
```

**Request Body:**
```json
{
  "keep": 10
}
```

**Response:** `200 OK`
```json
{
  "message": "Deleted 5 old snapshots",
  "kept": 10,
  "deleted": 5
}
```

### Restore from Snapshot

```http
POST /api/playlists/{id}/restore/{snapshot_id}/
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "name": "Rock Classics",
  ...
}
```

---

## Error Responses

All endpoints may return these error responses:

### 400 Bad Request
```json
{
  "error": "invalid_input",
  "message": "Detailed error message"
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
  "error": "forbidden",
  "message": "Not authorized to perform this action"
}
```

### 404 Not Found
```json
{
  "error": "playlist_not_found",
  "message": "Playlist not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "server_error",
  "message": "An unexpected error occurred"
}
```

---

## Rate Limiting

**Current Status:** Not implemented
**Recommended:** 100 requests/minute per user
**Response Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1617192000
```

---

## Pagination

List endpoints support pagination via `limit` and `offset` parameters.

**Default:** No limit (use with caution)
**Recommended:** Set `limit=50` for production

---

## Filtering & Sorting

### Sort Fields
- `name` — Alphabetical by name
- `created_at` — Creation date
- `updated_at` — Last update date
- `track_count` — Number of tracks

### Sort Order
- `asc` — Ascending
- `desc` — Descending (default)

### Special Filters
- `?filter=followed` — Only followed playlists
- `?filter=liked` — Only liked playlists

---

## Data Models

### Playlist Model

```json
{
  "id": integer,
  "owner_id": integer,
  "name": string (max 255),
  "description": string (text, optional),
  "visibility": "public" | "private",
  "playlist_type": "solo" | "collaborative",
  "cover_url": string (URL, optional),
  "max_songs": integer (default 0),
  "created_at": datetime (ISO 8601),
  "updated_at": datetime (ISO 8601)
}
```

### Track Model

```json
{
  "id": integer,
  "playlist": integer (FK),
  "song": integer (FK),
  "added_by": integer (FK),
  "position": integer,
  "added_at": datetime (ISO 8601)
}
```

---

## Best Practices

1. **Always use pagination** for list endpoints
2. **Filter by date ranges** to reduce result sets
3. **Use `select_related`** for foreign key relationships
4. **Cache frequently accessed data** (featured playlists, recommendations)
5. **Use transactions** for multi-step operations
6. **Create snapshots** before destructive operations
7. **Handle missing songs** gracefully during import/restore

---

## Changelog

### v1.0 (2026-03-30)
- Initial release
- All 6 phases implemented
- 30+ endpoints available
- Full CRUD operations
- Social features (follow/like)
- Smart recommendations
- Versioning/snapshots
- Export/import functionality
