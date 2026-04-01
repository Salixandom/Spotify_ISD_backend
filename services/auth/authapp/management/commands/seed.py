"""
Django Management Command: seed

Generates fake user data for the auth service.

Usage:
    uv run python manage.py seed

    Or via Docker:
        docker exec -it spotify_isd_backend-auth-1 uv run python manage.py seed
"""

import random

from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

# Django models
from django.contrib.auth.models import User
from authapp.models import UserProfile, UserFollow


class Command(BaseCommand):
    help = "Seed database with fake user data (auth service)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=50,
            help="Number of users to create (default: 50)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip tables that already have data",
        )

    def handle(self, *args, **options):
        """Main entry point for the command."""
        config = {
            "users": options["users"],
        }

        self.stdout.write(self.style.SUCCESS("\n🌱 Starting auth service database seeding...\n"))

        fake = Faker()
        random.seed(42)  # Reproducible data

        with transaction.atomic():
            # 1. Generate Users with Profiles
            if options["skip_existing"] and User.objects.count() > 1:
                user_ids = list(User.objects.values_list("id", flat=True))
                self.stdout.write(self.style.WARNING(f"  ✓ Skipped user creation (already exists)"))
            else:
                self.stdout.write("  Creating users with profiles...")
                user_ids = []

                for i in range(config["users"]):
                    username = fake.user_name() + str(random.randint(1, 9999))
                    email = fake.email()

                    # Create user
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password="password123",  # Default password for all test users
                        first_name=fake.first_name(),
                        last_name=fake.last_name(),
                        is_active=True,
                    )
                    user_ids.append(user.id)

                    # Create profile
                    UserProfile.objects.create(
                        user_id=user.id,
                        display_name=fake.name(),
                        bio=fake.sentence(nb_words=10),
                        avatar_url=f"https://i.pravatar.cc/300?u={username}",
                        profile_visibility=random.choice(["public", "followers", "private"]),
                        show_activity=random.choice([True, False]),
                        allow_messages=random.choice([True, False]),
                        preferences={"theme": random.choice(["dark", "light"]), "language": "en"},
                    )

                self.stdout.write(self.style.SUCCESS(f"  ✓ Created {len(user_ids)} users"))

            # 2. Generate Follow Relationships
            self.stdout.write("  Creating user follows...")
            follow_count = 0

            for follower_id in user_ids:
                # Each user follows 5-15 random users
                num_follows = random.randint(5, 15)
                following_ids = random.sample([u for u in user_ids if u != follower_id], min(num_follows, len(user_ids) - 1))

                for following_id in following_ids:
                    follow, created = UserFollow.objects.get_or_create(
                        follower_id=follower_id,
                        following_id=following_id,
                    )
                    if created:
                        follow_count += 1

            self.stdout.write(self.style.SUCCESS(f"  ✓ Created {follow_count} follow relationships"))

        # Summary
        self.stdout.write(self.style.SUCCESS("\n✅ Auth service seeding completed successfully!\n"))
        self.stdout.write("📊 Summary:")
        self.stdout.write(f"  • {config['users']} users with profiles")
        self.stdout.write(f"  • {follow_count} follow relationships\n")
        self.stdout.write("🔑 Test credentials:")
        self.stdout.write("  All users use password: password123\n")
        self.stdout.write("💡 Next steps:")
        self.stdout.write("  1. Seed the core service (it will use these users)")
        self.stdout.write("  2. Start the core service: docker compose up -d core")
        self.stdout.write("  3. Run: docker exec -it spotify_isd_backend-core-1 uv run python manage.py seed\n")
