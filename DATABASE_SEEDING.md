# Database Seeding Guide

This guide explains how to seed the Spotify ISD database with realistic test data.

## ⚠️ Seeding Order Matters!

**IMPORTANT:** Seed services in this order to avoid foreign key constraint errors:

1. **Auth Service** (Users) → Creates user accounts
2. **Core Service** (Songs, Playlists) → Uses users from auth service
3. **Collaboration Service** (Optional) → Uses users and playlists

## Quick Start

### 1. Start All Services

```bash
cd Spotify_ISD_backend
docker compose up -d db auth core
```

### 2. Seed in Order

#### Step 1: Seed Users (Auth Service)

```bash
# Create 50 users with profiles and follows
docker exec -it spotify_isd_backend-auth-1 uv run python manage.py seed

# Or with custom count
docker exec -it spotify_isd_backend-auth-1 uv run python manage.py seed --users 100
```

This creates:
- User accounts (all with password: `password123`)
- User profiles with avatars and bios
- Follow relationships between users

#### Step 2: Seed Music Data (Core Service)

```bash
# Seed artists, albums, songs, playlists
docker exec -it spotify_isd_backend-core-1 uv run python manage.py seed

# With custom counts
docker exec -it spotify_isd_backend-core-1 uv run python manage.py seed \
  --artists 30 \
  --albums 50 \
  --songs 300 \
  --playlists 50 \
  --tracks-per-playlist 15
```

This creates:
- Music genres (Pop, Rock, Hip-Hop, etc.)
- Artists with images and bios
- Albums with cover art
- Songs with audio URLs
- Playlists owned by the users created in Step 1
- Playlist tracks, comments, snapshots, and history

#### Step 3: Seed Collaborations (Collaboration Service)

```bash
docker compose up -d collaboration
docker exec -it spotify_isd_backend-collaboration-1 uv run python manage.py seed

# With custom counts
docker exec -it spotify_isd_backend-collaboration-1 uv run python manage.py seed \
  --collaborators 100 \
  --invites 50
```

This creates:
- Collaborators on collaborative playlists (links users to playlists)
- Invite links with expirations for sharing playlists

## What Gets Seeded

### Core Service (`playlistapp`, `searchapp`, `trackapp`, `historyapp`)

| Entity | Default Count | Description |
|--------|---------------|-------------|
| Genres | 20 | Music genres (Pop, Rock, Hip-Hop, etc.) |
| Artists | 30 | Artists with images, bios, listener counts |
| Albums | 50 | Albums with cover art and release years |
| Songs | 300 | Songs with audio URLs, genres, popularity |
| Playlists | 50 | User playlists with tracks |
| Tracks | ~750 | Playlist-track relationships |
| Comments | ~100 | Playlist comments and replies |
| Snapshots | ~35 | Playlist version history |
| Play History | 200 | User play history entries |

### Auth Service (`authapp`)

| Entity | Default Count | Description |
|--------|---------------|-------------|
| Users | 50 | Django auth users |
| Profiles | 50 | User profiles with avatars, bios, privacy settings |
| Follows | ~500 | User follow relationships |

## Test Credentials

After seeding, you can login with:

**Core Service (test user):**
- Username: `testuser`
- Password: `password123`

**Auth Service (first seeded user):**
- Username: Check the seed output for the first username
- Password: `password123`

All seeded users use the same password: `password123`

## Seed Command Options

### Core Service Options

| Option | Default | Description |
|--------|---------|-------------|
| `--artists` | 30 | Number of artists to create |
| `--albums` | 50 | Number of albums to create |
| `--songs` | 300 | Number of songs to create |
| `--playlists` | 50 | Number of playlists to create |
| `--tracks-per-playlist` | 15 | Average tracks per playlist |
| `--skip-existing` | false | Don't recreate existing data |

### Auth Service Options

| Option | Default | Description |
|--------|---------|-------------|
| `--users` | 50 | Number of users to create |
| `--skip-existing` | false | Don't recreate existing data |

## Data Sources

The seed data uses:

- **Images**: Unsplash (real, high-quality artist and album images)
- **Audio**: Free sample MP3s from SoundHelix and other sources
- **Metadata**: Generated via Faker library (realistic names, descriptions, dates)

## Reseeding from Scratch

To completely reset and reseed:

```bash
# Stop all services
docker compose down

# Remove volumes (deletes all data)
docker volume rm spotify_isd_backend_postgres_data

# Start services
docker compose up -d db core auth

# Wait for services to be ready
sleep 10

# Run migrations
docker exec spotify_isd_backend-core-1 uv run python manage.py migrate

# Run seeds
docker exec spotify_isd_backend-core-1 uv run python manage.py seed
docker exec spotify_isd_backend-auth-1 uv run python manage.py seed
```

## Troubleshooting

### "No module named 'collabapp'" error

This is expected - the core service seed command only seeds tables that exist in the core database. Collaboration data is seeded separately when needed.

### "No module named 'faker'" error

The faker dependency should be installed automatically. If not:

```bash
# Rebuild the service
docker compose up -d --build core
```

### Database connection errors

Ensure the database container is running:

```bash
docker ps | grep spotify_isd_backend-db-1
```

If not running:
```bash
docker compose up -d db
```

## API Testing with Seeded Data

Once seeded, you can test the APIs:

```bash
# Login as testuser (core service creates this user)
curl -X POST http://localhost/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'

# Get playlists
curl http://localhost/api/playlists/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Search songs
curl "http://localhost/api/search/?q=love" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get trending
curl http://localhost/api/search/discover/trending/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Performance Notes

- **Small dataset** (for quick testing): `--artists 10 --albums 20 --songs 100 --playlists 20`
- **Medium dataset** (default): Balanced size for development
- **Large dataset** (for load testing): `--artists 100 --albums 300 --songs 1000 --playlists 200`

Seed times:
- Small: ~5 seconds
- Medium: ~15 seconds
- Large: ~45 seconds
