#!/usr/bin/env python3
"""
Spotify ISD Database Seeding Script

Generates comprehensive fake data for all application tables.
Run with: python scripts/seed_database.py

Requirements:
    pip install psycopg2-binary faker

Or via docker:
    docker exec -i spotify_isd_backend-db-1 psql -U spotifyuser -d spotifydb < seed_output.sql
"""

import hashlib
import os
import random
import secrets
import string
from datetime import datetime, timedelta
from typing import List

import psycopg2
from faker import Faker

# =============================================================================
# CONFIGURATION
# =============================================================================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "spotifydb"),
    "user": os.getenv("DB_USER", "spotifyuser"),
    "password": os.getenv("DB_PASSWORD", "spotifypass"),
}

SEED_CONFIG = {
    "users": 50,
    "artists": 30,
    "albums": 80,
    "songs": 300,
    "genres": 20,
    "playlists_per_user": 5,
    "tracks_per_playlist": 15,
    "comments_per_playlist": 3,
    "followers_per_user": 10,
    "collaborations": 20,
}

# =============================================================================
# REAL DATA SOURCES (Unsplash, etc.)
# =============================================================================
ARTIST_IMAGES = [
    "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=500",
    "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=500",
    "https://images.unsplash.com/photo-1501386761578-eac5c94b800a?w=500",
    "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=500",
    "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=500",
    "https://images.unsplash.com/photo-1524368535928-5b5e00ddc76b?w=500",
    "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=500",
    "https://images.unsplash.com/photo-1446057032654-9d8885db76c6?w=500",
    "https://images.unsplash.com/photo-1501612780327-45045538702b?w=500",
    "https://images.unsplash.com/photo-1511379938547-c1f69419868d?w=500",
]

ALBUM_COVERS = [
    "https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=400",
    "https://images.unsplash.com/photo-1619983081563-430f63602796?w=400",
    "https://images.unsplash.com/photo-1557672172-298e090bd0f1?w=400",
    "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400",
    "https://images.unsplash.com/photo-1558591710-4b4a1ae0f04d?w=400",
    "https://images.unsplash.com/photo-1621360841013-c768371e93cf?w=400",
    "https://images.unsplash.com/photo-1484755560615-a4c64e778a6c?w=400",
    "https://images.unsplash.com/photo-1506157786151-b8491531f063?w=400",
    "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?w=400",
    "https://images.unsplash.com/photo-1494232410401-ad00d5433cfa?w=400",
]

GENRE_COLORS = [
    "#E13300", "#1DB954", "#BA5D07", "#E1118B", "#503750",
    "#DC148C", "#8D67AB", "#E91429", "#1E3264", "#E91429",
    "#148A08", "#BC5900", "#E13300", "#503750", "#1DB954",
]

# =============================================================================
# DJANGO PASSWORD HASHING (standalone, no Django import needed)
# =============================================================================
def make_django_password(password: str) -> str:
    """
    Generate a Django-compatible PBKDF2 SHA256 password hash.
    Pure Python implementation - no Django required.
    """
    algo = "pbkdf2_sha256"
    iterations = 600000  # Django 4.x default
    salt = secrets.token_hex(16)

    hash_obj = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    encoded_hash = hash_obj.hex()

    return f"{algo}${iterations}${salt}${encoded_hash}"


# =============================================================================
# DATABASE CONNECTION
# =============================================================================
def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def execute_sql(conn, sql: str, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())


def fetch_all(conn, sql: str, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_one(conn, sql: str, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        columns = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        return dict(zip(columns, row)) if row else None


# =============================================================================
# SEED DATA GENERATORS
# =============================================================================
fake = Faker()
random.seed(42)  # Reproducible data


def generate_genres(conn) -> List[int]:
    """Generate music genres with metadata."""
    genre_names = [
        "Pop", "Rock", "Hip-Hop", "R&B", "Country", "Jazz", "Electronic",
        "Classical", "Latin", "Indie", "Metal", "Folk", "Soul", "Reggae",
        "Blues", "Punk", "Disco", "House", "Techno", "Ambient"
    ]

    genre_ids = []
    for name in genre_names:
        sql = """
            INSERT INTO searchapp_genre (name, description, image_url, song_count, follower_count, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET song_count = EXCLUDED.song_count + 1
            RETURNING id
        """
        result = fetch_one(conn, sql, (
            name,
            f"{name} music for every mood",
            random.choice(ALBUM_COVERS),
            random.randint(50, 500),
            random.randint(1000, 50000),
            datetime.now(),
            datetime.now(),
        ))
        genre_ids.append(result["id"])

    print(f"  ✓ Created {len(genre_ids)} genres")
    return genre_ids


def generate_users(conn, count: int) -> List[int]:
    """Generate users with profiles."""
    user_ids = []

    for _ in range(count):
        username = fake.user_name() + str(random.randint(1, 9999))
        email = fake.email()

        # Insert into auth_user
        user_sql = """
            INSERT INTO auth_user (password, username, email, first_name, last_name, is_active, date_joined)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        user_result = fetch_one(conn, user_sql, (
            make_django_password("password123"),
            username,
            email,
            fake.first_name(),
            fake.last_name(),
            True,
            fake.date_time_between(start_date="-2y", end_date="now"),
        ))
        user_id = user_result["id"]
        user_ids.append(user_id)

        # Insert into authapp_userprofile
        profile_sql = """
            INSERT INTO authapp_userprofile
            (user_id, display_name, bio, avatar_url, profile_visibility, show_activity, allow_messages, preferences, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        execute_sql(conn, profile_sql, (
            user_id,
            fake.name(),
            fake.sentence(nb_words=10),
            f"https://i.pravatar.cc/300?u={username}",
            random.choice(["public", "followers", "private"]),
            random.choice([True, False]),
            random.choice([True, False]),
            {"theme": random.choice(["dark", "light"]), "language": "en"},
            fake.date_time_between(start_date="-2y", end_date="now"),
            datetime.now(),
        ))

    print(f"  ✓ Created {len(user_ids)} users")
    return user_ids


def generate_artists(conn, count: int) -> List[int]:
    """Generate music artists."""
    artist_ids = []

    for _ in range(count):
        sql = """
            INSERT INTO searchapp_artist (name, image_url, bio, monthly_listeners, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        result = fetch_one(conn, sql, (
            fake.name() if random.random() > 0.3 else f"The {fake.word().capitalize()}s",
            random.choice(ARTIST_IMAGES),
            fake.paragraph(nb_sentences=3),
            random.randint(10000, 50000000),
            fake.date_time_between(start_date="-5y", end_date="now"),
        ))
        artist_ids.append(result["id"])

    print(f"  ✓ Created {len(artist_ids)} artists")
    return artist_ids


def generate_albums(conn, count: int, artist_ids: List[int]) -> List[int]:
    """Generate albums."""
    album_ids = []

    for _ in range(count):
        sql = """
            INSERT INTO searchapp_album (name, cover_url, release_year, artist_id, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        result = fetch_one(conn, sql, (
            fake.sentence(nb_words=4)[:-1],
            random.choice(ALBUM_COVERS),
            random.randint(1970, 2024),
            random.choice(artist_ids),
            fake.date_time_between(start_date="-5y", end_date="now"),
        ))
        album_ids.append(result["id"])

    print(f"  ✓ Created {len(album_ids)} albums")
    return album_ids


def generate_songs(conn, count: int, artist_ids: List[int], album_ids: List[int], genre_names: List[str]) -> List[int]:
    """Generate songs with audio URLs (using free samples)."""
    song_ids = []

    # Using free audio samples from various sources
    audio_urls = [
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",
        "https://www2.cs.uic.edu/~i101/SoundFiles/BabyElephantWalk60.wav",
        "https://www2.cs.uic.edu/~i101/SoundFiles/StarWars60.wav",
        "https://www2.cs.uic.edu/~i101/SoundFiles/Gettysburg10.wav",
        "https://www2.cs.uic.edu/~i101/SoundFiles/ImperialMarch60.wav",
        "https://www2.cs.uic.edu/~i101/SoundFiles/CantinaBand60.wav",
        "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/no_curator/Tours/Enthusiast/Tours_-_01_-_Enthusiast.mp3",
    ]

    for i in range(count):
        artist_id = random.choice(artist_ids)
        album_id = random.choice(album_ids) if random.random() > 0.1 else None

        sql = """
            INSERT INTO searchapp_song
            (title, genre, release_year, duration_seconds, cover_url, audio_url, storage_path, album_id, artist_id,
             is_explicit, popularity_score, release_date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        result = fetch_one(conn, sql, (
            fake.sentence(nb_words=5)[:-1],
            random.choice(genre_names),
            random.randint(1970, 2024),
            random.randint(120, 360),  # 2-6 minutes
            random.choice(ALBUM_COVERS),
            random.choice(audio_urls),
            f"songs/{artist_id}/{i+1}.mp3",
            album_id,
            artist_id,
            random.random() < 0.2,  # 20% explicit
            random.randint(10, 100),
            fake.date_between(start_date="-5y", end_date="today"),
            fake.date_time_between(start_date="-5y", end_date="now"),
        ))
        song_ids.append(result["id"])

    print(f"  ✓ Created {len(song_ids)} songs")
    return song_ids


def generate_playlists_and_tracks(conn, user_ids: List[int], song_ids: List[int]):
    """Generate playlists with tracks."""
    playlist_ids = []

    for user_id in user_ids:
        for _ in range(random.randint(2, SEED_CONFIG["playlists_per_user"] + 1)):
            is_collab = random.random() < 0.2

            sql = """
                INSERT INTO playlistapp_playlist
                (owner_id, name, description, visibility, playlist_type, cover_url, max_songs, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            result = fetch_one(conn, sql, (
                user_id,
                fake.sentence(nb_words=4)[:-1],
                fake.paragraph(nb_sentences=2) if random.random() > 0.5 else "",
                random.choice(["public", "private"]),
                "collaborative" if is_collab else "solo",
                random.choice(ALBUM_COVERS) if random.random() > 0.5 else "",
                random.randint(50, 200),
                fake.date_time_between(start_date="-1y", end_date="now"),
                datetime.now(),
            ))
            playlist_id = result["id"]
            playlist_ids.append(playlist_id)

            # Add tracks
            num_tracks = random.randint(5, SEED_CONFIG["tracks_per_playlist"])
            selected_songs = random.sample(song_ids, min(num_tracks, len(song_ids)))

            for position, song_id in enumerate(selected_songs, start=1):
                track_sql = """
                    INSERT INTO trackapp_track (playlist_id, song_id, added_by_id, position, added_at)
                    VALUES (%s, %s, %s, %s, %s)
                """
                execute_sql(conn, track_sql, (
                    playlist_id,
                    song_id,
                    user_id,
                    position,
                    fake.date_time_between(start_date="-6mo", end_date="now"),
                ))

    print(f"  ✓ Created {len(playlist_ids)} playlists with tracks")
    return playlist_ids


def generate_follows(conn, user_ids: List[int]):
    """Generate user follow relationships."""
    follow_count = 0

    for follower_id in user_ids:
        # Each user follows 5-15 random users
        num_follows = random.randint(5, 15)
        following_ids = random.sample([u for u in user_ids if u != follower_id], min(num_follows, len(user_ids) - 1))

        for following_id in following_ids:
            # Check if already exists
            existing = fetch_one(conn, """
                SELECT id FROM authapp_userfollow WHERE follower_id = %s AND following_id = %s
            """, (follower_id, following_id))

            if not existing:
                sql = """
                    INSERT INTO authapp_userfollow (follower_id, following_id, created_at)
                    VALUES (%s, %s, %s)
                """
                execute_sql(conn, sql, (
                    follower_id,
                    following_id,
                    fake.date_time_between(start_date="-1y", end_date="now"),
                ))
                follow_count += 1

    print(f"  ✓ Created {follow_count} follow relationships")


def generate_playlist_follows_and_likes(conn, user_ids: List[int], playlist_ids: List[int]):
    """Generate playlist follows and likes."""
    follow_count = 0
    like_count = 0

    for user_id in user_ids:
        # Follow 3-10 random playlists
        num_follows = random.randint(3, 10)
        for playlist_id in random.sample(playlist_ids, min(num_follows, len(playlist_ids))):
            existing = fetch_one(conn, """
                SELECT id FROM playlistapp_userplaylistfollow WHERE user_id = %s AND playlist_id = %s
            """, (user_id, playlist_id))

            if not existing:
                execute_sql(conn, """
                    INSERT INTO playlistapp_userplaylistfollow (user_id, playlist_id, followed_at)
                    VALUES (%s, %s, %s)
                """, (user_id, playlist_id, fake.date_time_between(start_date="-6mo", end_date="now")))
                follow_count += 1

        # Like 5-15 random playlists
        num_likes = random.randint(5, 15)
        for playlist_id in random.sample(playlist_ids, min(num_likes, len(playlist_ids))):
            existing = fetch_one(conn, """
                SELECT id FROM playlistapp_userplaylistlike WHERE user_id = %s AND playlist_id = %s
            """, (user_id, playlist_id))

            if not existing:
                execute_sql(conn, """
                    INSERT INTO playlistapp_userplaylistlike (user_id, playlist_id, liked_at)
                    VALUES (%s, %s, %s)
                """, (user_id, playlist_id, fake.date_time_between(start_date="-6mo", end_date="now")))
                like_count += 1

    print(f"  ✓ Created {follow_count} playlist follows")
    print(f"  ✓ Created {like_count} playlist likes")


def generate_collaborations(conn, user_ids: List[int], playlist_ids: List[int]):
    """Generate playlist collaborators."""
    collab_count = 0

    # Select collaborative playlists
    collab_playlists = fetch_all(conn, """
        SELECT id, owner_id FROM playlistapp_playlist WHERE playlist_type = 'collaborative' LIMIT %s
    """, (SEED_CONFIG["collaborations"],))

    for playlist in collab_playlists:
        # Add 2-5 collaborators per playlist
        num_collabs = random.randint(2, 5)
        potential_collabs = [u for u in user_ids if u != playlist["owner_id"]]

        for user_id in random.sample(potential_collabs, min(num_collabs, len(potential_collabs))):
            existing = fetch_one(conn, """
                SELECT id FROM collabapp_collaborator WHERE playlist_id = %s AND user_id = %s
            """, (playlist["id"], user_id))

            if not existing:
                execute_sql(conn, """
                    INSERT INTO collabapp_collaborator (playlist_id, user_id, joined_at)
                    VALUES (%s, %s, %s)
                """, (playlist["id"], user_id, fake.date_time_between(start_date="-3mo", end_date="now")))
                collab_count += 1

    print(f"  ✓ Created {collab_count} collaborators")


def generate_comments(conn, user_ids: List[int], playlist_ids: List[int]):
    """Generate playlist comments."""
    comment_count = 0

    for playlist_id in random.sample(playlist_ids, min(len(playlist_ids) // 2, len(playlist_ids))):
        # Add 1-5 comments per playlist
        num_comments = random.randint(1, 5)

        for _ in range(num_comments):
            user_id = random.choice(user_ids)

            sql = """
                INSERT INTO playlistapp_playlistcomment
                (playlist_id, user_id, parent_id, content, likes_count, is_edited, is_deleted, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            result = fetch_one(conn, sql, (
                playlist_id,
                user_id,
                None,  # Top-level comments for now
                fake.paragraph(nb_sentences=2),
                random.randint(0, 20),
                False,
                False,
                fake.date_time_between(start_date="-3mo", end_date="now"),
                datetime.now(),
            ))

            # Occasionally add a reply
            if random.random() < 0.3:
                reply_user_id = random.choice([u for u in user_ids if u != user_id])
                execute_sql(conn, """
                    INSERT INTO playlistapp_playlistcomment
                    (playlist_id, user_id, parent_id, content, likes_count, is_edited, is_deleted, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    playlist_id,
                    reply_user_id,
                    result["id"],
                    fake.sentence(nb_words=8),
                    random.randint(0, 10),
                    False,
                    False,
                    fake.date_time_between(start_date="-2mo", end_date="now"),
                    datetime.now(),
                ))
                comment_count += 2
            else:
                comment_count += 1

    print(f"  ✓ Created {comment_count} comments")


def generate_snapshots(conn, playlist_ids: List[int]):
    """Generate playlist snapshots for versioning."""
    snapshot_count = 0

    for playlist_id in random.sample(playlist_ids, min(len(playlist_ids) // 3, len(playlist_ids))):
        # Add 1-3 snapshots per playlist
        num_snapshots = random.randint(1, 3)

        for i in range(num_snapshots):
            tracks = fetch_all(conn, """
                SELECT song_id, position FROM trackapp_track WHERE playlist_id = %s ORDER BY position
            """, (playlist_id,))

            snapshot_data = {
                "tracks": [{"song_id": t["song_id"], "position": t["position"]} for t in tracks],
                "name": f"Snapshot {i+1}",
            }

            sql = """
                INSERT INTO playlistapp_playlistsnapshot
                (playlist_id, snapshot_data, created_by, change_reason, track_count, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            execute_sql(conn, sql, (
                playlist_id,
                snapshot_data,
                1,  # Default to first user
                fake.sentence(nb_words=5),
                len(tracks),
                fake.date_time_between(start_date="-2mo", end_date="now"),
            ))
            snapshot_count += 1

    print(f"  ✓ Created {snapshot_count} snapshots")


def generate_history(conn, user_ids: List[int], song_ids: List[int]):
    """Generate play history."""
    history_count = 0

    for user_id in user_ids:
        # Each user has 20-100 played songs
        num_plays = random.randint(20, 100)

        for _ in range(num_plays):
            execute_sql(conn, """
                INSERT INTO historyapp_play (user_id, song_id, played_at)
                VALUES (%s, %s, %s)
            """, (
                user_id,
                random.choice(song_ids),
                fake.date_time_between(start_date="-3mo", end_date="now"),
            ))
            history_count += 1

    print(f"  ✓ Created {history_count} play history entries")


# =============================================================================
# MAIN SEEDING FUNCTION
# =============================================================================
def seed_database():
    """Main seeding function."""
    print("\n🌱 Starting database seeding...\n")

    conn = get_connection()
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            # Disable triggers during seeding for performance
            cur.execute("SET session_replication_role = replica;")

        # Generate in dependency order
        genre_ids = generate_genres(conn)
        user_ids = generate_users(conn, SEED_CONFIG["users"])
        artist_ids = generate_artists(conn, SEED_CONFIG["artists"])
        album_ids = generate_albums(conn, SEED_CONFIG["albums"], artist_ids)
        song_ids = generate_songs(conn, SEED_CONFIG["songs"], artist_ids, album_ids, [
            "Pop", "Rock", "Hip-Hop", "R&B", "Electronic"
        ])

        playlist_ids = generate_playlists_and_tracks(conn, user_ids, song_ids)

        generate_follows(conn, user_ids)
        generate_playlist_follows_and_likes(conn, user_ids, playlist_ids)
        generate_collaborations(conn, user_ids, playlist_ids)
        generate_comments(conn, user_ids, playlist_ids)
        generate_snapshots(conn, playlist_ids)
        generate_history(conn, user_ids, song_ids)

        conn.commit()

        with conn.cursor() as cur:
            # Re-enable triggers
            cur.execute("SET session_replication_role = DEFAULT;")

        print("\n✅ Database seeding completed successfully!\n")
        print("📊 Summary:")
        print(f"  • {SEED_CONFIG['users']} users")
        print(f"  • {SEED_CONFIG['artists']} artists")
        print(f"  • {SEED_CONFIG['albums']} albums")
        print(f"  • {SEED_CONFIG['songs']} songs")
        print(f"  • {len(playlist_ids)} playlists with tracks")
        print(f"  • Follows, likes, comments, and more\n")
        print("🔑 Test credentials:")
        print("  Username: any user from the database")
        print("  Password: password123\n")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during seeding: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()
