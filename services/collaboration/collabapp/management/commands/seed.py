"""
Django Management Command: seed

Generates fake collaboration data for the collaboration service.

Usage:
    uv run python manage.py seed

    Or via Docker:
        docker exec -it spotify_isd_backend-collaboration-1 uv run python manage.py seed
"""

import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker


class Command(BaseCommand):
    help = "Seed database with fake collaboration data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--collaborators",
            type=int,
            default=100,
            help="Number of collaborators to create (default: 100)",
        )
        parser.add_argument(
            "--invites",
            type=int,
            default=50,
            help="Number of invite links to create (default: 50)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip tables that already have data",
        )

    def handle(self, *args, **options):
        """Main entry point for the command."""
        from django.contrib.auth.models import User
        from collabapp.models import Collaborator, InviteLink

        config = {
            "collaborators": options["collaborators"],
            "invites": options["invites"],
        }

        self.stdout.write(self.style.SUCCESS("\n🌱 Starting collaboration service database seeding...\n"))

        fake = Faker()
        random.seed(42)

        # Get existing users and playlists from shared database
        user_ids = list(User.objects.values_list("id", flat=True))

        if not user_ids:
            self.stdout.write(self.style.ERROR("  ✗ No users found! Seed the auth service first."))
            self.stdout.write(self.style.WARNING("  Run: docker exec -it spotify_isd_backend-auth-1 uv run python manage.py seed"))
            return

        # We need playlist IDs from the core service's database
        # Since this is a microservice setup, we'll query the shared database directly
        try:
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute("SELECT id, owner_id, playlist_type FROM playlistapp_playlist WHERE playlist_type = 'collaborative'")
                playlist_rows = cur.fetchall()

                if not playlist_rows:
                    self.stdout.write(self.style.WARNING("  ⚠ No collaborative playlists found! Seed the core service first."))
                    self.stdout.write(self.style.WARNING("  Run: docker exec -it spotify_isd_backend-core-1 uv run python manage.py seed"))
                    return

                playlists = [{"id": row[0], "owner_id": row[1], "type": row[2]} for row in playlist_rows]
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Error fetching playlists: {e}"))
            return

        with transaction.atomic():
            # 1. Generate Collaborators
            self.stdout.write("  Creating collaborators...")
            collaborator_count = 0

            for playlist in playlists:
                owner_id = playlist["owner_id"]
                playlist_id = playlist["id"]

                # Add 2-5 collaborators per collaborative playlist
                num_collabs = random.randint(2, 5)
                potential_collabs = [u for u in user_ids if u != owner_id]

                for user_id in random.sample(potential_collabs, min(num_collabs, len(potential_collabs))):
                    collab, created = Collaborator.objects.get_or_create(
                        playlist_id=playlist_id,
                        user_id=user_id,
                    )
                    if created:
                        collaborator_count += 1

            self.stdout.write(self.style.SUCCESS(f"  ✓ Created {collaborator_count} collaborators"))

            # 2. Generate Invite Links
            self.stdout.write("  Creating invite links...")
            invite_count = 0

            for playlist in playlists:
                # Create 1-3 invite links per collaborative playlist
                num_invites = random.randint(1, 3)

                for _ in range(num_invites):
                    # Create invite with 30-day expiry
                    expires_at = datetime.now() + timedelta(days=random.randint(1, 30))

                    InviteLink.objects.create(
                        playlist_id=playlist["id"],
                        created_by_id=playlist["owner_id"],
                        is_active=random.choice([True, False, True]),  # 70% active
                        expires_at=expires_at,
                    )
                    invite_count += 1

            self.stdout.write(self.style.SUCCESS(f"  ✓ Created {invite_count} invite links"))

        # Summary
        self.stdout.write(self.style.SUCCESS("\n✅ Collaboration service seeding completed successfully!\n"))
        self.stdout.write("📊 Summary:")
        self.stdout.write(f"  • {collaborator_count} collaborators on playlists")
        self.stdout.write(f"  • {invite_count} invite links\n")
        self.stdout.write("💡 Next steps:")
        self.stdout.write("  • Test collaboration features via the API")
        self.stdout.write("  • Generate invite links: POST /api/collab/{playlist_id}/invite/")
        self.stdout.write("  • Join via token: POST /api/collab/join/{token}/\n")
