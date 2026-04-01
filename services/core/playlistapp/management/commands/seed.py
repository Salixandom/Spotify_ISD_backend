"""
Django Management Command: seed

Generates comprehensive fake data for the core service database.
Note: This seeds only core service tables (songs, playlists, artists, albums, etc.).
For user data, run this in the auth service.

Usage:
    uv run python manage.py seed

    Or via Docker:
        docker exec -it spotify_isd_backend-core-1 uv run python manage.py seed
"""

import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker


class Command(BaseCommand):
    help = "Seed database with fake data for testing (core service only)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--artists",
            type=int,
            default=30,
            help="Number of artists to create (default: 30)",
        )
        parser.add_argument(
            "--albums",
            type=int,
            default=50,
            help="Number of albums to create (default: 50)",
        )
        parser.add_argument(
            "--songs",
            type=int,
            default=300,
            help="Number of songs to create (default: 300)",
        )
        parser.add_argument(
            "--playlists",
            type=int,
            default=50,
            help="Number of playlists to create (default: 50)",
        )
        parser.add_argument(
            "--tracks-per-playlist",
            type=int,
            default=15,
            help="Average tracks per playlist (default: 15)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip tables that already have data",
        )

    def handle(self, *args, **options):
        """Main entry point for the command."""
        from django.contrib.auth.models import User
        from playlistapp.models import (
            Playlist,
            PlaylistComment,
            PlaylistSnapshot,
        )
        from searchapp.models import Album, Artist, Genre, Song
        from historyapp.models import Play
        from trackapp.models import Track

        config = {
            "artists": options["artists"],
            "albums": options["albums"],
            "songs": options["songs"],
            "playlists": options["playlists"],
            "tracks_per_playlist": options["tracks_per_playlist"],
        }

        self.stdout.write(self.style.SUCCESS("\n🌱 Starting database seeding (core service)...\n"))

        fake = Faker()
        random.seed(42)  # Reproducible data

        # Real image URLs from Unsplash
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

        # Free audio samples for testing
        AUDIO_URLS = [
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

        with transaction.atomic():
            # 1. Create or get a default user for playlist ownership
            self.stdout.write("  Ensuring test user exists...")
            user, _ = User.objects.get_or_create(
                username="testuser",
                defaults={
                    "email": "test@example.com",
                    "first_name": "Test",
                    "last_name": "User",
                    "is_active": True,
                }
            )
            user.set_password("password123")
            user.save()
            self.stdout.write(self.style.SUCCESS(f"  ✓ Test user: testuser / password123"))

            # 2. Generate Genres
            self.stdout.write("  Creating genres...")
            genre_names = [
                "Pop", "Rock", "Hip-Hop", "R&B", "Country", "Jazz", "Electronic",
                "Classical", "Latin", "Indie", "Metal", "Folk", "Soul", "Reggae",
                "Blues", "Punk", "Disco", "House", "Techno", "Ambient"
            ]

            genre_objs = []
            for name in genre_names:
                genre, created = Genre.objects.get_or_create(
                    name=name,
                    defaults={
                        "description": f"{name} music for every mood",
                        "image_url": random.choice(ALBUM_COVERS),
                        "song_count": random.randint(50, 500),
                        "follower_count": random.randint(1000, 50000),
                    }
                )
                genre_objs.append(genre)

            self.stdout.write(self.style.SUCCESS(f"  ✓ Created {len(genre_objs)} genres"))

            # 3. Generate Artists
            if options["skip_existing"] and Artist.objects.exists():
                artist_ids = list(Artist.objects.values_list("id", flat=True))
                self.stdout.write(self.style.WARNING(f"  ✓ Skipped artist creation (already exists)"))
            else:
                self.stdout.write("  Creating artists...")
                artist_ids = []

                for _ in range(config["artists"]):
                    artist = Artist.objects.create(
                        name=fake.name() if random.random() > 0.3 else f"The {fake.word().capitalize()}s",
                        image_url=random.choice(ARTIST_IMAGES),
                        bio=fake.paragraph(nb_sentences=3),
                        monthly_listeners=random.randint(10000, 50000000),
                    )
                    artist_ids.append(artist.id)

                self.stdout.write(self.style.SUCCESS(f"  ✓ Created {len(artist_ids)} artists"))

            # 4. Generate Albums
            if options["skip_existing"] and Album.objects.exists():
                album_ids = list(Album.objects.values_list("id", flat=True))
                self.stdout.write(self.style.WARNING(f"  ✓ Skipped album creation (already exists)"))
            else:
                self.stdout.write("  Creating albums...")
                album_ids = []

                for _ in range(config["albums"]):
                    album = Album.objects.create(
                        name=fake.sentence(nb_words=4)[:-1],
                        cover_url=random.choice(ALBUM_COVERS),
                        release_year=random.randint(1970, 2024),
                        artist_id=random.choice(artist_ids),
                    )
                    album_ids.append(album.id)

                self.stdout.write(self.style.SUCCESS(f"  ✓ Created {len(album_ids)} albums"))

            # 5. Generate Songs
            if options["skip_existing"] and Song.objects.exists():
                song_ids = list(Song.objects.values_list("id", flat=True))
                self.stdout.write(self.style.WARNING(f"  ✓ Skipped song creation (already exists)"))
            else:
                self.stdout.write("  Creating songs...")
                song_ids = []

                for i in range(config["songs"]):
                    artist_id = random.choice(artist_ids)
                    album_id = random.choice(album_ids) if random.random() > 0.1 else None

                    song = Song.objects.create(
                        title=fake.sentence(nb_words=5)[:-1],
                        genre=random.choice(genre_names),
                        release_year=random.randint(1970, 2024),
                        duration_seconds=random.randint(120, 360),
                        cover_url=random.choice(ALBUM_COVERS),
                        audio_url=random.choice(AUDIO_URLS),
                        storage_path=f"songs/{artist_id}/{i+1}.mp3",
                        album_id=album_id,
                        artist_id=artist_id,
                        is_explicit=random.random() < 0.2,
                        popularity_score=random.randint(10, 100),
                        release_date=fake.date_between(start_date="-5y", end_date="today"),
                    )
                    song_ids.append(song.id)

                self.stdout.write(self.style.SUCCESS(f"  ✓ Created {len(song_ids)} songs"))

            # 6. Generate Playlists and Tracks
            self.stdout.write("  Creating playlists with tracks...")
            playlist_ids = []

            for _ in range(config["playlists"]):
                is_collab = random.random() < 0.2

                playlist = Playlist.objects.create(
                    owner_id=user.id,
                    name=fake.sentence(nb_words=4)[:-1],
                    description=fake.paragraph(nb_sentences=2) if random.random() > 0.5 else "",
                    visibility=random.choice(["public", "private"]),
                    playlist_type="collaborative" if is_collab else "solo",
                    cover_url=random.choice(ALBUM_COVERS) if random.random() > 0.5 else "",
                    max_songs=random.randint(50, 200),
                )
                playlist_ids.append(playlist.id)

                # Add tracks
                num_tracks = random.randint(5, config["tracks_per_playlist"])
                selected_songs = random.sample(song_ids, min(num_tracks, len(song_ids)))

                for position, song_id in enumerate(selected_songs, start=1):
                    Track.objects.create(
                        playlist_id=playlist.id,
                        song_id=song_id,
                        added_by_id=user.id,
                        position=position,
                    )

            self.stdout.write(self.style.SUCCESS(f"  ✓ Created {len(playlist_ids)} playlists with tracks"))

            # 7. Generate Playlist Comments
            self.stdout.write("  Creating comments...")
            comment_count = 0

            for playlist_id in random.sample(playlist_ids, min(len(playlist_ids) // 2, len(playlist_ids))):
                num_comments = random.randint(1, 5)

                for _ in range(num_comments):
                    comment = PlaylistComment.objects.create(
                        playlist_id=playlist_id,
                        user_id=user.id,
                        content=fake.paragraph(nb_sentences=2),
                        likes_count=random.randint(0, 20),
                    )

                    # Occasionally add a reply
                    if random.random() < 0.3:
                        PlaylistComment.objects.create(
                            playlist_id=playlist_id,
                            user_id=user.id,
                            parent_id=comment.id,
                            content=fake.sentence(nb_words=8),
                            likes_count=random.randint(0, 10),
                        )
                        comment_count += 2
                    else:
                        comment_count += 1

            self.stdout.write(self.style.SUCCESS(f"  ✓ Created {comment_count} comments"))

            # 8. Generate Snapshots
            self.stdout.write("  Creating snapshots...")
            snapshot_count = 0

            for playlist_id in random.sample(playlist_ids, min(len(playlist_ids) // 3, len(playlist_ids))):
                num_snapshots = random.randint(1, 3)

                for i in range(num_snapshots):
                    tracks = list(Track.objects.filter(playlist_id=playlist_id).values("song_id", "position"))

                    PlaylistSnapshot.objects.create(
                        playlist_id=playlist_id,
                        snapshot_data={"tracks": tracks},
                        created_by=user.id,
                        change_reason=fake.sentence(nb_words=5),
                        track_count=len(tracks),
                    )
                    snapshot_count += 1

            self.stdout.write(self.style.SUCCESS(f"  ✓ Created {snapshot_count} snapshots"))

            # 9. Generate Play History
            self.stdout.write("  Creating play history...")
            history_count = 0

            num_plays = 200
            for _ in range(num_plays):
                Play.objects.create(
                    user_id=user.id,
                    song_id=random.choice(song_ids),
                    played_at=fake.date_time_between(start_date="-3mo", end_date="now"),
                )
                history_count += 1

            self.stdout.write(self.style.SUCCESS(f"  ✓ Created {history_count} play history entries"))

        # Summary
        self.stdout.write(self.style.SUCCESS("\n✅ Database seeding completed successfully!\n"))
        self.stdout.write("📊 Summary:")
        self.stdout.write(f"  • {config['artists']} artists")
        self.stdout.write(f"  • {config['albums']} albums")
        self.stdout.write(f"  • {config['songs']} songs")
        self.stdout.write(f"  • {len(playlist_ids)} playlists with tracks")
        self.stdout.write("  • Comments, snapshots, and history\n")
        self.stdout.write("🔑 Test credentials:")
        self.stdout.write("  Username: testuser")
        self.stdout.write("  Password: password123\n")
        self.stdout.write("💡 Tip: Run this command in the auth service to create more users!")
