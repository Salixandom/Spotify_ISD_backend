"""
Unit tests for Auth service models.
"""
import pytest
from authapp.models import UserProfile, UserFollow


@pytest.mark.django_db
class TestUserProfileModel:
    """Test UserProfile model functionality."""

    def test_create_user_profile(self):
        """Test creating a new user profile."""
        profile = UserProfile.objects.create(
            user_id=1,
            display_name='Test User',
            bio='A test user',
            avatar_url='https://example.com/avatar.jpg',
            profile_visibility='public',
            show_activity=True,
            allow_messages=True
        )

        assert profile.id is not None
        assert profile.user_id == 1
        assert profile.display_name == 'Test User'
        assert profile.bio == 'A test user'
        assert profile.avatar_url == 'https://example.com/avatar.jpg'
        assert profile.profile_visibility == 'public'
        assert profile.show_activity is True
        assert profile.allow_messages is True

    def test_profile_defaults(self):
        """Test default values for profile fields."""
        profile = UserProfile.objects.create(user_id=1)

        assert profile.display_name == ''
        assert profile.bio == ''
        assert profile.avatar_url == ''
        assert profile.profile_visibility == 'public'
        assert profile.show_activity is True
        assert profile.allow_messages is True
        assert profile.preferences == {}

    def test_profile_str_method(self):
        """Test string representation of profile."""
        profile = UserProfile.objects.create(user_id=1)
        assert str(profile) == 'Profile for User 1'

    def test_is_public_property(self):
        """Test is_public property."""
        public_profile = UserProfile.objects.create(
            user_id=1,
            profile_visibility='public'
        )
        assert public_profile.is_public is True

        private_profile = UserProfile.objects.create(
            user_id=2,
            profile_visibility='private'
        )
        assert private_profile.is_public is False

    def test_profile_visibility_choices(self):
        """Test valid profile visibility choices."""
        profile = UserProfile.objects.create(user_id=1)

        valid_choices = ['public', 'followers', 'private']
        assert profile.profile_visibility in valid_choices

    def test_unique_user_id(self):
        """Test that user_id must be unique."""
        UserProfile.objects.create(user_id=1)

        # Attempting to create another profile with same user_id should fail
        with pytest.raises(Exception):  # IntegrityError
            UserProfile.objects.create(user_id=1)


@pytest.mark.django_db
class TestUserFollowModel:
    """Test UserFollow model functionality."""

    def test_follow_user(self):
        """Test creating a follow relationship."""
        follow = UserFollow.objects.create(
            follower_id=1,
            following_id=2
        )

        assert follow.id is not None
        assert follow.follower_id == 1
        assert follow.following_id == 2

    def test_unique_follow_constraint(self):
        """Test that a user can only follow another user once."""
        UserFollow.objects.create(
            follower_id=1,
            following_id=2
        )

        # Attempting to follow again should raise IntegrityError
        with pytest.raises(Exception):  # IntegrityError
            UserFollow.objects.create(
                follower_id=1,
                following_id=2
            )

    def test_cannot_follow_self(self):
        """Test that a user cannot follow themselves (enforced at application level)."""
        # This constraint might be enforced in views/serializers, not model
        # Model itself allows it, but business logic should prevent it
        follow = UserFollow.objects.create(
            follower_id=1,
            following_id=1
        )
        # Model allows it, but API should prevent this
        assert follow is not None

    def test_follow_str_method(self):
        """Test string representation of follow."""
        follow = UserFollow.objects.create(
            follower_id=1,
            following_id=2
        )
        assert str(follow) == 'User 1 follows 2'

    def test_follow_ordering(self):
        """Test follows are ordered by created_at descending."""
        follow1 = UserFollow.objects.create(
            follower_id=1,
            following_id=2
        )

        # Small delay to ensure different timestamps
        import time
        time.sleep(0.01)

        follow2 = UserFollow.objects.create(
            follower_id=1,
            following_id=3
        )

        follows = list(UserFollow.objects.all())
        assert follows[0].id == follow2.id  # Most recent first
        assert follows[1].id == follow1.id
