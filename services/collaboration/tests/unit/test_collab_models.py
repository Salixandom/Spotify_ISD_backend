"""
Unit tests for Collaboration app models.
"""
import pytest
import uuid
from datetime import timedelta
from django.db import IntegrityError
from django.utils import timezone
from collabapp.models import Collaborator, InviteLink


@pytest.mark.django_db
class TestCollaboratorModel:
    """Test Collaborator model functionality."""

    def test_create_collaborator(self):
        """Test creating a new collaborator."""
        collaborator = Collaborator.objects.create(
            playlist_id=1,
            user_id=100
        )

        assert collaborator.id is not None
        assert collaborator.playlist_id == 1
        assert collaborator.user_id == 100
        assert collaborator.joined_at is not None

    def test_collaborator_defaults(self):
        """Test default values for collaborator fields."""
        collaborator = Collaborator.objects.create(
            playlist_id=1,
            user_id=100
        )

        assert collaborator.joined_at is not None

    def test_collaborator_unique_constraint(self):
        """Test that (playlist_id, user_id) is unique."""
        Collaborator.objects.create(
            playlist_id=1,
            user_id=100
        )

        # Attempting to create again should raise IntegrityError
        with pytest.raises(Exception):  # IntegrityError
            Collaborator.objects.create(
                playlist_id=1,
                user_id=100
            )

    def test_different_users_same_playlist(self):
        """Test that different users can collaborate on same playlist."""
        collab1 = Collaborator.objects.create(playlist_id=1, user_id=100)
        collab2 = Collaborator.objects.create(playlist_id=1, user_id=101)

        assert collab1.id != collab2.id
        assert Collaborator.objects.count() == 2

    def test_same_user_different_playlists(self):
        """Test that same user can collaborate on different playlists."""
        collab1 = Collaborator.objects.create(playlist_id=1, user_id=100)
        collab2 = Collaborator.objects.create(playlist_id=2, user_id=100)

        assert collab1.id != collab2.id
        assert Collaborator.objects.count() == 2

    def test_collaborator_str_method(self):
        """Test string representation of collaborator."""
        collaborator = Collaborator.objects.create(
            playlist_id=1,
            user_id=100
        )
        collab_str = str(collaborator)
        assert '100' in collab_str
        assert '1' in collab_str


@pytest.mark.django_db
class TestInviteLinkModel:
    """Test InviteLink model functionality."""

    def test_create_invite_link(self):
        """Test creating a new invite link."""
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=100
        )

        assert invite.id is not None
        assert invite.playlist_id == 1
        assert invite.created_by_id == 100
        assert invite.token is not None
        assert isinstance(invite.token, uuid.UUID)

    def test_invite_link_defaults(self):
        """Test default values for invite link fields."""
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=100
        )

        assert invite.is_active is True
        assert invite.created_at is not None
        assert invite.expires_at is not None

    def test_invite_link_unique_token(self):
        """Test that tokens are unique."""
        invite1 = InviteLink.objects.create(playlist_id=1, created_by_id=100)
        invite2 = InviteLink.objects.create(playlist_id=1, created_by_id=100)

        assert invite1.token != invite2.token

    def test_is_valid_property_active_and_not_expired(self):
        """Test is_valid returns True for active, non-expired links."""
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=100,
            is_active=True
        )

        assert invite.is_valid is True

    def test_is_valid_property_inactive(self):
        """Test is_valid returns False for inactive links."""
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=100,
            is_active=False
        )

        assert invite.is_valid is False

    def test_is_valid_property_expired(self):
        """Test is_valid returns False for expired links."""
        past_time = timezone.now() - timedelta(days=1)

        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=100,
            is_active=True,
            expires_at=past_time
        )

        assert invite.is_valid is False

    def test_default_expiration(self):
        """Test that default expiration is 30 days from creation."""
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=100
        )

        time_diff = invite.expires_at - invite.created_at
        # Should be approximately 30 days (allow small variance)
        assert 29 <= time_diff.days <= 30

    def test_custom_expiration(self):
        """Test creating invite with custom expiration."""
        future_time = timezone.now() + timedelta(days=60)

        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=100,
            expires_at=future_time
        )

        assert invite.expires_at == future_time

    def test_invite_link_str_method(self):
        """Test string representation of invite link."""
        invite = InviteLink.objects.create(
            playlist_id=1,
            created_by_id=100
        )
        invite_str = str(invite)
        assert str(invite.token) in invite_str
        assert '1' in invite_str


@pytest.mark.django_db
class TestPostgreSQLConstraints:
    """PostgreSQL-specific constraint tests for collaboration models.

    Verifies that unique constraints raise django.db.IntegrityError (the
    specific exception) and that SELECT FOR UPDATE works — both behaviours
    that SQLite does not reliably reproduce.
    """

    def test_collaborator_unique_raises_integrity_error(self):
        """unique_together on (playlist_id, user_id) raises IntegrityError specifically."""
        Collaborator.objects.create(playlist_id=10, user_id=200)
        with pytest.raises(IntegrityError):
            Collaborator.objects.create(playlist_id=10, user_id=200)

    def test_invite_token_unique_raises_integrity_error(self):
        """Duplicate UUID token on InviteLink raises IntegrityError."""
        fixed_token = uuid.uuid4()
        InviteLink.objects.create(playlist_id=1, created_by_id=1, token=fixed_token)
        with pytest.raises(IntegrityError):
            InviteLink.objects.create(playlist_id=2, created_by_id=1, token=fixed_token)

    @pytest.mark.django_db(transaction=True)
    def test_select_for_update_on_collaborator(self):
        """select_for_update() must not raise — PostgreSQL supports row-level locking."""
        from django.db import transaction
        collab = Collaborator.objects.create(playlist_id=20, user_id=300)
        with transaction.atomic():
            locked = Collaborator.objects.select_for_update().get(id=collab.id)
            assert locked.id == collab.id
