# Sakib's Comprehensive Backend Enhancement Plan

**Project**: Spotify ISD Backend - Enhanced Spotify Clone
**Date**: 2026-03-30
**Author**: Sakib
**Status**: Ready for Implementation

---

## 📋 Executive Summary

This plan addresses **critical security vulnerabilities**, **architecture inconsistencies**, and **feature gaps** identified through comprehensive codebase audit. The enhancements are organized into **4 phases** with clear priorities, implementation details, and success criteria.

**Current Maturity Level**: Beta (feature-rich but has critical issues)
**Target Maturity Level**: Production-Ready

---

## 🎯 Objectives

### **Primary Goals**
1. ✅ Fix critical security vulnerability in collaboration service
2. ✅ Resolve cross-service dependencies violating microservices principles
3. ✅ Standardize consistency issues across all services
4. ✅ Complete missing features from original requirements

### **Secondary Goals**
5. ✅ Enhance code maintainability and reduce duplication
6. ✅ Improve performance and scalability
7. ✅ Add missing Spotify-like features for competitive parity

---

## 🚨 Critical Issues Overview

### **Issue #1: Authorization Vulnerability - CRITICAL**
**Severity**: 🔴 CRITICAL
**Impact**: Security vulnerability, broken collaboration functionality
**Location**: `/services/collaboration/collabapp/views.py:80-89`
**Fix Time**: 30 minutes

**Problem**: Playlist owners cannot remove collaborators - users can only remove themselves

**Current Code**:
```python
def delete(self, request, playlist_id):
    user_id = request.query_params.get('user_id')
    if str(user_id) != str(request.user.id):
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
    Collaborator.objects.filter(playlist_id=playlist_id, user_id=user_id).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
```

**Impact**: Owners are stuck with collaborators they can't remove

---

### **Issue #2: Cross-Service Dependencies - HIGH PRIORITY**
**Severity**: 🟠 HIGH
**Impact**: Architecture violation, deployment complexity
**Locations**: Multiple files in core service
**Fix Time**: 1-2 days

**Problem**: Services directly import models from each other

**Examples**:
```python
# playlistapp/views.py:206
from collaboration.collabapp.models import Collaborator

# trackapp/views.py:40
from collaboration.collabapp.models import Collaborator
```

**Impact**: Services aren't truly independent, breaks microservices architecture

---

### **Issue #3: Missing Migrations - MEDIUM PRIORITY**
**Severity**: 🟡 MEDIUM
**Impact**: Database schema not properly versioned
**Fix Time**: 1 hour

**Problem**: No custom migration files found for model changes

---

## 📊 Complete Enhancement Plan

---

## **PHASE 1: Critical Security Fixes** (Day 1)
**Priority**: 🔴 CRITICAL
**Time Investment**: 2-3 hours
**Goal**: Fix immediate security and functionality issues

### **Task 1.1: Fix Authorization Vulnerability**
**File**: `/services/collaboration/collabapp/views.py`
**Time**: 30 minutes

**Current Behavior**:
- Users can only remove themselves from playlists
- Playlist owners cannot remove collaborators
- Broken collaboration functionality

**Desired Behavior**:
- Users can remove themselves
- Playlist owners can remove any collaborator
- Proper authorization checks

**Implementation**:
```python
def delete(self, request, playlist_id):
    """
    Remove a collaborator from a playlist.

    Authorization:
    - Users can always remove themselves
    - Playlist owners can remove any collaborator
    """
    user_id = request.query_params.get('user_id')
    if not user_id:
        return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)

    # Allow self-removal
    if str(user_id) == str(request.user.id):
        Collaborator.objects.filter(playlist_id=playlist_id, user_id=user_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Check if requester is playlist owner
    try:
        # Cross-service call to core service
        import requests
        response = requests.get(
            f'http://core:8000/api/playlists/{playlist_id}/',
            headers={'Authorization': request.headers.get('Authorization')}
        )
        if response.status_code == 200:
            playlist_data = response.json()
            if playlist_data.get('owner_id') == request.user.id:
                Collaborator.objects.filter(playlist_id=playlist_id, user_id=user_id).delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({'error': f'Failed to verify ownership: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
```

**Testing**:
1. Owner removes collaborator ✅
2. Collaborator removes themselves ✅
3. Non-owner cannot remove others ✅
4. Non-collaborator cannot remove anyone ✅

**Success Criteria**:
- [ ] Playlist owners can remove any collaborator
- [ ] Users can still remove themselves
- [ ] Authorization properly enforced
- [ ] TODO comment removed
- [ ] Tests pass

---

### **Task 1.2: Create Missing Migrations**
**All Services**
**Time**: 1 hour

**Problem**: Custom migrations not created for model changes

**Solution**:
```bash
# For each service
cd services/auth
uv run python manage.py makemigrations authapp
uv run python manage.py migrate authapp

cd services/core
uv run python manage.py makemigrations
uv run python manage.py migrate

cd services/collaboration
uv run python manage.py makemigrations
uv run python manage.py migrate
```

**Services to Process**:
- [ ] auth service (authapp)
- [ ] core service (playlistapp, trackapp, historyapp, searchapp)
- [ ] collaboration service (collabapp, shareapp)

**Success Criteria**:
- [ ] All migrations created
- [ ] All migrations applied
- [ ] Database schema up-to-date
- [ ] No pending migrations

---

### **Task 1.3: Remove TODO Comments**
**All Services**
**Time**: 30 minutes

**Locations**:
1. `/services/collaboration/collabapp/views.py:80-89` - Authorization TODO
2. `/services/core/playlistapp/views.py:206` - Collaborator count TODO

**Action**: Either implement or remove TODO comments

**Success Criteria**:
- [ ] No TODO comments in production code
- [ ] All documented issues addressed or documented in backlog

---

## **PHASE 2: Architecture Cleanup** (Days 2-3)
**Priority**: 🟠 HIGH
**Time Investment**: 1-2 days
**Goal**: Resolve microservices architecture violations

### **Task 2.1: Implement Service Communication Layer**
**All Services**
**Time**: 1 day

**Problem**: Direct imports between services violate microservices principles

**Current Pattern** (BROKEN):
```python
# In core service
from collaboration.collabapp.models import Collaborator
collab = Collaborator.objects.get(playlist_id=playlist_id, user_id=user_id)
```

**Solution**: Create service client for HTTP communication

**Implementation Plan**:

1. **Create Service Client Utility**
   **File**: `/services/core/utils/service_clients.py`

```python
import requests
import os
from django.conf import settings

class CollaborationServiceClient:
    """Client for communicating with collaboration service"""

    BASE_URL = os.getenv('COLLABORATION_SERVICE_URL', 'http://collaboration:8000')

    @classmethod
    def get_collaborators(cls, playlist_id):
        """Get collaborators for a playlist"""
        response = requests.get(f'{cls.BASE_URL}/api/collab/{playlist_id}/members/')
        response.raise_for_status()
        return response.json()

    @classmethod
    def is_collaborator(cls, playlist_id, user_id):
        """Check if user is a collaborator"""
        response = requests.get(f'{cls.BASE_URL}/api/collab/{playlist_id}/my-role/')
        if response.status_code == 200:
            return response.json().get('role') == 'collaborator'
        return False

    @classmethod
    def add_collaborator(cls, playlist_id, user_id, token):
        """Add user as collaborator via invite token"""
        response = requests.post(
            f'{cls.BASE_URL}/api/collab/join/{token}/',
            json={'user_id': user_id}
        )
        response.raise_for_status()
        return response.json()

    @classmethod
    def remove_collaborator(cls, playlist_id, user_id, auth_token):
        """Remove collaborator from playlist"""
        response = requests.delete(
            f'{cls.BASE_URL}/api/collab/{playlist_id}/members/?user_id={user_id}',
            headers={'Authorization': auth_token}
        )
        response.raise_for_status()
        return response.status_code == 204
```

2. **Update Views to Use Service Client**

**File**: `/services/core/playlistapp/views.py`

**Before**:
```python
from collaboration.collabapp.models import Collaborator

collaborator_count = Collaborator.objects.filter(playlist_id=playlist.id).count()
```

**After**:
```python
from utils.service_clients import CollaborationServiceClient

try:
    collabs = CollaborationServiceClient.get_collaborators(playlist.id)
    collaborator_count = len(collabs)
except Exception as e:
    logger.error(f"Failed to fetch collaborators: {e}")
    collaborator_count = 0
```

**File**: `/services/core/trackapp/views.py`

**Before**:
```python
from collaboration.collabapp.models import Collaborator

Collaborator.objects.get(playlist_id=playlist_id, user_id=user_id)
```

**After**:
```python
from utils.service_clients import CollaborationServiceClient

is_collab = CollaborationServiceClient.is_collaborator(playlist_id, user_id)
if not is_collab:
    return None, Response({'error': 'Not authorized'}, 403)
```

3. **Service Discovery Configuration**

**File**: `docker-compose.yml`

```yaml
services:
  core:
    environment:
      - COLLABORATION_SERVICE_URL=http://collaboration:8000
      - AUTH_SERVICE_URL=http://auth:8000

  collaboration:
    environment:
      - CORE_SERVICE_URL=http://core:8000
      - AUTH_SERVICE_URL=http://auth:8000
```

**Files to Update**:
- [ ] `/services/core/playlistapp/views.py`
- [ ] `/services/core/trackapp/views.py`
- [ ] `/services/core/utils/service_clients.py` (new file)
- [ ] `docker-compose.yml`

**Success Criteria**:
- [ ] No direct imports between services
- [ ] All service communication via HTTP
- [ ] Services can be deployed independently
- [ ] Integration tests pass

---

### **Task 2.2: Standardize Error Response Format**
**All Services**
**Time**: 2 hours

**Problem**: Inconsistent error response formats across endpoints

**Solution**: Create base response classes

**Implementation**:

**File**: `/services/core/utils/responses.py` (create in each service)

```python
from rest_framework.response import Response
from rest_framework import status

class SuccessResponse(Response):
    """Standard success response"""
    def __init__(self, data=None, message="Success", status_code=status.HTTP_200_OK):
        response_data = {
            'success': True,
            'message': message,
            'data': data or {}
        }
        super().__init__(response_data, status=status_code)

class ErrorResponse(Response):
    """Standard error response"""
    def __init__(self, error=None, message="Error", status_code=status.HTTP_400_BAD_REQUEST):
        response_data = {
            'success': False,
            'error': error,
            'message': message
        }
        super().__init__(response_data, status=status_code)

class ValidationErrorResponse(ErrorResponse):
    """Validation error response (400)"""
    def __init__(self, errors=None, message="Validation failed"):
        super().__init__(
            error='validation_error',
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST
        )
        self.data['details'] = errors or {}

class NotFoundResponse(ErrorResponse):
    """Not found response (404)"""
    def __init__(self, message="Resource not found"):
        super().__init__(
            error='not_found',
            message=message,
            status_code=status.HTTP_404_NOT_FOUND
        )

class ForbiddenResponse(ErrorResponse):
    """Forbidden response (403)"""
    def __init__(self, message="Access forbidden"):
        super().__init__(
            error='forbidden',
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )

class UnauthorizedResponse(ErrorResponse):
    """Unauthorized response (401)"""
    def __init__(self, message="Authentication required"):
        super().__init__(
            error='unauthorized',
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )
```

**Usage Example**:

**Before**:
```python
return Response({'error': 'Playlist not found'}, status=404)
```

**After**:
```python
from utils.responses import NotFoundResponse
return NotFoundResponse(message='Playlist not found')
```

**Files to Update**:
- [ ] All views in all services
- [ ] Update error responses systematically

**Success Criteria**:
- [ ] All error responses use standard format
- [ ] Consistent structure across all endpoints
- [ ] Frontend can handle errors uniformly

---

### **Task 2.3: Standardize Field Naming Conventions**
**All Services**
**Time**: 2 hours

**Problem**: Inconsistent field naming for user references

**Current Variations**:
- `user_id`
- `added_by_id`
- `created_by_id`

**Solution**: Standardize on `user_id` for all user references

**Files to Review**:
- [ ] `/services/core/playlistapp/models.py`
- [ ] `/services/core/trackapp/models.py`
- [ ] `/services/collaboration/collabapp/models.py`
- [ ] `/services/collaboration/shareapp/models.py`

**Migration Required**: Yes

**Success Criteria**:
- [ ] All user references use `user_id`
- [ ] Migration created and applied
- [ ] No breaking changes for existing data

---

## **PHASE 3: Feature Enhancements** (Days 4-7)
**Priority**: 🟡 MEDIUM
**Time Investment**: 4 days
**Goal**: Add missing Spotify features for competitive parity

### **Task 3.1: User Profile Management**
**New Feature**
**Time**: 1 day

**Features to Add**:
1. User bio
2. Profile avatar/image
3. User display name
4. User preferences/settings

**Implementation**:

**Option A**: Extend existing Django User model
**Option B**: Create separate UserProfile model

**Recommendation**: Option B (more flexible)

**Model Design**:
```python
# services/auth/authapp/models.py

class UserProfile(models.Model):
    user_id = models.IntegerField(unique=True)
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True, max_length=500)
    avatar_url = models.URLField(blank=True)
    preferences = models.JSONField(default=dict)  # For settings

    # Privacy settings
    profile_visibility = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('followers', 'Followers Only'), ('private', 'Private')],
        default='public'
    )

    # Activity settings
    show_activity = models.BooleanField(default=True)
    allow_messages = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['profile_visibility']),
        ]
```

**API Endpoints**:
- `GET /api/profile/me/` - Get my profile
- `PUT /api/profile/me/` - Update my profile
- `GET /api/profile/{user_id}/` - Get user's public profile
- `POST /api/profile/me/avatar/` - Upload avatar

**Success Criteria**:
- [ ] UserProfile model created
- [ ] API endpoints implemented
- [ ] Avatar upload working
- [ ] Privacy settings enforced
- [ ] Tests pass

---

### **Task 3.2: User-to-User Following**
**New Feature**
**Time**: 1 day

**Features to Add**:
1. Follow other users
2. Unfollow users
3. View followers
4. View following
5. Activity feed from followed users

**Implementation**:

**Model Design**:
```python
# services/auth/authapp/models.py

class UserFollow(models.Model):
    follower_id = models.IntegerField()  # User who follows
    following_id = models.IntegerField()  # User being followed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower_id', 'following_id')
        indexes = [
            models.Index(fields=['follower_id']),
            models.Index(fields=['following_id']),
        ]

    def __str__(self):
        return f"User {self.follower_id} follows {self.following_id}"
```

**API Endpoints**:
- `POST /api/social/follow/{user_id}/` - Follow a user
- `DELETE /api/social/follow/{user_id}/` - Unfollow a user
- `GET /api/social/followers/` - Get my followers
- `GET /api/social/following/` - Get users I'm following
- `GET /api/social/followers/{user_id}/` - Get user's followers
- `GET /api/social/following/{user_id}/` - Get users followed by user

**Activity Feed** (Bonus):
```python
class UserActivity(models.Model):
    user_id = models.IntegerField()
    activity_type = models.CharField(max_length=50)  # 'playlist_created', 'track_added', etc.
    entity_type = models.CharField(max_length=50)  # 'playlist', 'track', etc.
    entity_id = models.IntegerField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user_id', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
```

**Success Criteria**:
- [ ] UserFollow model created
- [ ] Follow/unfollow endpoints working
- [ ] Follower/following lists working
- [ ] Activity feed implemented (optional)
- [ ] Tests pass

---

### **Task 3.3: Playlist Comments**
**New Feature**
**Time**: 1 day

**Features to Add**:
1. Comment on playlists
2. Reply to comments
3. Delete own comments
4. Like comments
5. View comments with threading

**Implementation**:

**Model Design**:
```python
# services/core/playlistapp/models.py

class PlaylistComment(models.Model):
    playlist_id = models.IntegerField()
    user_id = models.IntegerField()
    parent_id = models.IntegerField(null=True, blank=True)  # For threaded replies
    content = models.TextField()

    # Engagement
    likes_count = models.IntegerField(default=0)

    # Moderation
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['playlist_id', '-created_at']),
            models.Index(fields=['user_id']),
            models.Index(fields=['parent_id']),
        ]

    def __str__(self):
        return f"Comment by {self.user_id} on playlist {self.playlist_id}"

class PlaylistCommentLike(models.Model):
    comment_id = models.IntegerField()
    user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('comment_id', 'user_id')
```

**API Endpoints**:
- `POST /api/playlists/{id}/comments/` - Add comment
- `GET /api/playlists/{id}/comments/` - Get all comments (threaded)
- `PUT /api/playlists/{id}/comments/{comment_id}/` - Edit comment
- `DELETE /api/playlists/{id}/comments/{comment_id}/` - Delete comment
- `POST /api/playlists/{id}/comments/{comment_id}/like/` - Like comment
- `DELETE /api/playlists/{id}/comments/{comment_id}/like/` - Unlike comment

**Success Criteria**:
- [ ] PlaylistComment model created
- [ ] Threaded comments working
- [ ] Like/unlike comments working
- [ ] Edit/delete with authorization
- [ ] Tests pass

---

### **Task 3.4: Music Discovery Features**
**New Feature**
**Time**: 1 day

**Features to Add**:
1. Similar artists/songs recommendations
2. Genre-based exploration
3. New releases section
4. Trending music

---

### **Task 3.5: Comprehensive Undo/Redo System**
**New Feature - MAJOR ENHANCEMENT**
**Time**: 2-3 days
**Complexity**: HIGH
**Architectural Impact**: Significant

**Overview**: Full undo/redo system for all user actions, similar to command pattern in desktop applications. Users can undo and redo their actions within a configurable time window.

---

#### **🎯 What This System Does**

**Trackable Actions**:
1. **Playlist Operations**
   - Create playlist → Undo (delete playlist)
   - Delete playlist → Undo (restore playlist + all tracks)
   - Update playlist metadata → Undo (revert to previous state)
   - Duplicate playlist → Undo (delete duplicate)

2. **Track Operations**
   - Add track to playlist → Undo (remove track)
   - Remove track from playlist → Undo (restore track)
   - Reorder tracks → Undo (restore previous order)
   - Sort tracks → Undo (restore custom order)

3. **Social Operations**
   - Follow playlist → Undo (unfollow)
   - Like playlist → Undo (unlike)
   - Add comment → Undo (delete comment)

4. **Collaboration Operations**
   - Generate invite link → Undo (deactivate link)
   - Add collaborator → Undo (remove collaborator)
   - Remove collaborator → Undo (restore access)

**NOT Trackable** (by design):
- Login/logout (security actions)
- Password changes (security sensitive)
- Play actions (too many, low value)
- View actions (read-only, no state change)

---

#### **📐 Architecture Design**

##### **1. Data Models**

**File**: `/services/core/historyapp/models.py`

```python
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class UserAction(models.Model):
    """
    Track all user mutations for undo/redo functionality.
    This is the foundation of the undo/redo system.
    """
    # Action identification
    id = models.BigAutoField(primary_key=True)
    action_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # User & context
    user_id = models.IntegerField(db_index=True)
    session_id = models.CharField(max_length=100, db_index=True, null=True, blank=True)

    # Action classification
    ACTION_TYPES = [
        ('playlist_create', 'Create Playlist'),
        ('playlist_delete', 'Delete Playlist'),
        ('playlist_update', 'Update Playlist'),
        ('playlist_duplicate', 'Duplicate Playlist'),
        ('track_add', 'Add Track'),
        ('track_remove', 'Remove Track'),
        ('track_reorder', 'Reorder Tracks'),
        ('track_sort', 'Sort Tracks'),
        ('playlist_follow', 'Follow Playlist'),
        ('playlist_unfollow', 'Unfollow Playlist'),
        ('playlist_like', 'Like Playlist'),
        ('playlist_unlike', 'Unlike Playlist'),
        ('comment_add', 'Add Comment'),
        ('comment_delete', 'Delete Comment'),
        ('invite_generate', 'Generate Invite'),
        ('collaborator_add', 'Add Collaborator'),
        ('collaborator_remove', 'Remove Collaborator'),
    ]

    action_type = models.CharField(max_length=50, choices=ACTION_TYPES, db_index=True)
    entity_type = models.CharField(max_length=50)  # 'playlist', 'track', 'comment', etc.
    entity_id = models.IntegerField()

    # State snapshots (JSON serialized)
    before_state = models.JSONField(default=dict)  # State before action
    after_state = models.JSONField(default=dict)   # State after action
    delta = models.JSONField(default=dict)          # Changes made (for efficient undo)

    # Metadata
    description = models.TextField()  # Human-readable description
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Undo/redo state
    is_undone = models.BooleanField(default=False, db_index=True)
    undone_at = models.DateTimeField(null=True, blank=True)
    undone_action_id = models.UUIDField(null=True, blank=True)  # The undo action

    is_redone = models.BooleanField(default=False)
    redone_at = models.DateTimeField(null=True, blank=True)
    redone_action_id = models.UUIDField(null=True, blank=True)  # The redo action

    # Undoability
    is_undoable = models.BooleanField(default=True)  # Some actions can't be undone
    undo_deadline = models.DateTimeField(null=True, blank=True)  # Time limit for undo

    # Relationships for cascading actions
    parent_action_id = models.UUIDField(null=True, blank=True)  # Original action
    related_actions = models.JSONField(default=list)  # IDs of related actions

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['user_id', '-created_at']),
            models.Index(fields=['action_id']),
            models.Index(fields=['is_undone']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['-created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_type_display()} by User {self.user_id} at {self.created_at}"

    def can_undo(self):
        """Check if action can still be undone"""
        if not self.is_undoable:
            return False
        if self.is_undone:
            return False
        if self.undo_deadline and timezone.now() > self.undo_deadline:
            return False
        return True

    def can_redo(self):
        """Check if undone action can be redone"""
        return self.is_undone and not self.is_redone


class UndoRedoConfiguration(models.Model):
    """
    User preferences for undo/redo system.
    """
    user_id = models.IntegerField(unique=True)

    # Time window for undo (in hours, 0 = unlimited)
    undo_window_hours = models.IntegerField(default=24)

    # Maximum actions to keep per user
    max_actions = models.IntegerField(default=1000)

    # Auto-delete old actions
    auto_cleanup = models.BooleanField(default=True)

    # Enable/disable undo for specific action types
    disabled_action_types = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

---

##### **2. Action Logger Middleware**

**File**: `/services/core/historyapp/middleware.py`

```python
import uuid
import json
from django.utils.deprecation import MiddlewareMixin
from rest_framework.request import Request
from .models import UserAction
from .serializers import UserActionSerializer
from django.utils import timezone
from datetime import timedelta

class ActionLoggerMiddleware(MiddlewareMixin):
    """
    Intercept and log all mutating requests for undo/redo.
    This middleware captures state before and after actions.
    """

    # Actions to log (POST, PUT, PATCH, DELETE)
    LOGGED_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']

    # Endpoints to exclude from logging
    EXCLUDED_PATHS = [
        '/api/login/',
        '/api/register/',
        '/api/token/refresh/',
        '/api/history/undo/',  # Don't log undo actions themselves
        '/api/history/redo/',
        '/health/',
        '/api/health/',
    ]

    def process_request(self, request):
        """Capture state before action"""
        if request.method not in self.LOGGED_METHODS:
            return None

        if self.should_exclude(request):
            return None

        # Generate unique action ID
        action_id = str(uuid.uuid4())
        request.action_id = action_id

        # Store request data for later
        request._action_data = {
            'action_id': action_id,
            'method': request.method,
            'path': request.path,
            'user_id': getattr(request.user, 'id', None),
            'session_id': request.session.session_key,
        }

        return None

    def process_response(self, request, response):
        """Log action after it completes"""
        if not hasattr(request, '_action_data'):
            return response

        # Only log successful mutations
        if response.status_code < 200 or response.status_code >= 300:
            return response

        try:
            self.log_action(request, response)
        except Exception as e:
            # Don't break requests if logging fails
            import logging
            logging.error(f"Failed to log action: {e}")

        return response

    def should_exclude(self, request):
        """Check if request should be excluded from logging"""
        for path in self.EXCLUDED_PATHS:
            if request.path.startswith(path):
                return True
        return False

    def log_action(self, request, response):
        """Extract and store action data"""
        from .action_extractors import get_action_extractor

        action_data = request._action_data
        extractor = get_action_extractor(request.path)
        if not extractor:
            return

        # Extract action details
        action_details = extractor.extract(request, response)

        # Create UserAction record
        action = UserAction.objects.create(
            action_id=action_data['action_id'],
            user_id=action_data['user_id'],
            session_id=action_data['session_id'],
            action_type=action_details['action_type'],
            entity_type=action_details['entity_type'],
            entity_id=action_details['entity_id'],
            before_state=action_details['before_state'],
            after_state=action_details['after_state'],
            delta=action_details['delta'],
            description=action_details['description'],
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            undo_deadline=timezone.now() + timedelta(hours=24),
        )

        # Store in request for potential rollback
        request.created_action = action

    def get_client_ip(self, request):
        """Extract client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
```

---

##### **3. Action Extractors**

**File**: `/services/core/historyapp/action_extractors.py`

```python
"""
Extract action details from requests.
Each extractor knows how to capture before/after state for specific endpoints.
"""

class ActionExtractor:
    """Base class for action extractors"""

    def extract(self, request, response):
        """Extract action details from request/response"""
        raise NotImplementedError


class PlaylistCreateExtractor(ActionExtractor):
    """Extract playlist creation details"""

    def extract(self, request, response):
        from playlistapp.models import Playlist

        # After state from response
        response_data = response.json()
        playlist = Playlist.objects.get(id=response_data['id'])

        return {
            'action_type': 'playlist_create',
            'entity_type': 'playlist',
            'entity_id': playlist.id,
            'before_state': {},  # No before state for creation
            'after_state': {
                'id': playlist.id,
                'name': playlist.name,
                'description': playlist.description,
                'owner_id': playlist.owner_id,
                'visibility': playlist.visibility,
                'track_ids': list(playlist.tracks.values_list('id', flat=True)),
            },
            'delta': {
                'created_id': playlist.id,
            },
            'description': f'Created playlist "{playlist.name}"',
        }


class PlaylistDeleteExtractor(ActionExtractor):
    """Extract playlist deletion details"""

    def extract(self, request, response):
        from playlistapp.models import Playlist
        from trackapp.models import Track

        playlist_id = request.parser_context['kwargs']['id']

        # Capture before state (everything before deletion)
        try:
            playlist = Playlist.objects.get(id=playlist_id)
            tracks = Track.objects.filter(playlist=playlist).select_related('song')

            before_state = {
                'id': playlist.id,
                'name': playlist.name,
                'description': playlist.description,
                'owner_id': playlist.owner_id,
                'visibility': playlist.visibility,
                'type': playlist.type,
                'created_at': playlist.created_at.isoformat(),
                'updated_at': playlist.updated_at.isoformat(),
                'tracks': [
                    {
                        'id': track.id,
                        'song_id': track.song_id,
                        'position': track.position,
                        'added_at': track.added_at.isoformat(),
                    }
                    for track in tracks.order_by('position')
                ],
            }
        except Playlist.DoesNotExist:
            before_state = {}

        return {
            'action_type': 'playlist_delete',
            'entity_type': 'playlist',
            'entity_id': playlist_id,
            'before_state': before_state,
            'after_state': {},  # No after state for deletion
            'delta': {
                'deleted_id': playlist_id,
            },
            'description': f'Deleted playlist ID {playlist_id}',
        }


class TrackAddExtractor(ActionExtractor):
    """Extract track addition details"""

    def extract(self, request, response):
        from trackapp.models import Track

        response_data = response.json()
        track = Track.objects.get(id=response_data['id'])

        return {
            'action_type': 'track_add',
            'entity_type': 'track',
            'entity_id': track.id,
            'before_state': {
                'playlist_id': track.playlist_id,
                'track_count': Track.objects.filter(playlist_id=track.playlist_id).count() - 1,
            },
            'after_state': {
                'id': track.id,
                'playlist_id': track.playlist_id,
                'song_id': track.song_id,
                'position': track.position,
                'added_at': track.added_at.isoformat(),
            },
            'delta': {
                'added_track_id': track.id,
                'song_id': track.song_id,
            },
            'description': f'Added track to playlist {track.playlist_id}',
        }


class TrackRemoveExtractor(ActionExtractor):
    """Extract track removal details"""

    def extract(self, request, response):
        from trackapp.models import Track

        playlist_id = request.parser_context['kwargs']['playlist_id']
        track_id = request.parser_context['kwargs']['track_id']

        # Capture before state
        try:
            track = Track.objects.get(id=track_id, playlist_id=playlist_id)
            before_state = {
                'id': track.id,
                'playlist_id': track.playlist_id,
                'song_id': track.song_id,
                'position': track.position,
                'added_at': track.added_at.isoformat(),
            }
        except Track.DoesNotExist:
            before_state = {}

        return {
            'action_type': 'track_remove',
            'entity_type': 'track',
            'entity_id': track_id,
            'before_state': before_state,
            'after_state': {},
            'delta': {
                'removed_track_id': track_id,
                'playlist_id': playlist_id,
            },
            'description': f'Removed track {track_id} from playlist {playlist_id}',
        }


# Registry of extractors
EXTRACTORS = {
    'POST /api/playlists/': PlaylistCreateExtractor(),
    'DELETE /api/playlists/(?P<id>[^/.]+)/': PlaylistDeleteExtractor(),
    'POST /api/tracks/(?P<playlist_id>[^/.]+)/': TrackAddExtractor(),
    'DELETE /api/tracks/(?P<playlist_id>[^/.]+)/(?P<track_id>[^/.]+)/': TrackRemoveExtractor(),
    # Add more extractors as needed
}


def get_action_extractor(path):
    """Get appropriate extractor for path"""
    for pattern, extractor in EXTRACTORS.items():
        # Simple pattern matching (can use regex for production)
        if path.startswith(pattern.split('(')[0]):
            return extractor
    return None
```

---

##### **4. Undo/Redo Service**

**File**: `/services/core/historyapp/services.py`

```python
from django.db import transaction
from .models import UserAction
import logging

logger = logging.getLogger(__name__)


class UndoRedoService:
    """Service for handling undo/redo operations"""

    @staticmethod
    @transaction.atomic
    def undo_action(user_id, action_id):
        """
        Undo a specific action.

        Args:
            user_id: ID of user performing undo
            action_id: UUID of action to undo

        Returns:
            dict: Result of undo operation
        """
        try:
            action = UserAction.objects.get(action_id=action_id, user_id=user_id)
        except UserAction.DoesNotExist:
            return {
                'success': False,
                'error': 'Action not found or not owned by user',
                'status': 'not_found'
            }

        # Check if action can be undone
        if not action.can_undo():
            return {
                'success': False,
                'error': 'Action cannot be undone',
                'reason': 'already_undone' if action.is_undone else 'expired' if action.undo_deadline else 'not_undoable',
                'status': 'cannot_undo'
            }

        # Perform undo based on action type
        undo_handler = UndoHandlerFactory.get_handler(action.action_type)
        if not undo_handler:
            return {
                'success': False,
                'error': f'No undo handler for action type: {action.action_type}',
                'status': 'not_implemented'
            }

        try:
            # Execute undo
            undo_result = undo_handler.undo(action)

            # Mark action as undone
            action.is_undone = True
            action.undone_at = timezone.now()
            action.save()

            # Log the undo action itself
            UserAction.objects.create(
                user_id=user_id,
                action_type=f'undo_{action.action_type}',
                entity_type=action.entity_type,
                entity_id=action.entity_id,
                before_state=action.after_state,
                after_state=undo_result.get('new_state', {}),
                description=f'Undid: {action.description}',
                is_undoable=False,  # Undo actions can't be undone
            )

            return {
                'success': True,
                'message': f'Successfully undone: {action.description}',
                'undone_action': action.action_id,
                'status': 'undone'
            }

        except Exception as e:
            logger.error(f"Failed to undo action {action_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error'
            }

    @staticmethod
    @transaction.atomic
    def redo_action(user_id, action_id):
        """
        Redo a previously undone action.

        Args:
            user_id: ID of user performing redo
            action_id: UUID of action to redo

        Returns:
            dict: Result of redo operation
        """
        try:
            action = UserAction.objects.get(action_id=action_id, user_id=user_id)
        except UserAction.DoesNotExist:
            return {
                'success': False,
                'error': 'Action not found or not owned by user',
                'status': 'not_found'
            }

        # Check if action can be redone
        if not action.can_redo():
            return {
                'success': False,
                'error': 'Action cannot be redone',
                'reason': 'not_undone' if not action.is_undone else 'already_redone',
                'status': 'cannot_redo'
            }

        # Perform redo based on action type
        redo_handler = RedoHandlerFactory.get_handler(action.action_type)
        if not redo_handler:
            return {
                'success': False,
                'error': f'No redo handler for action type: {action.action_type}',
                'status': 'not_implemented'
            }

        try:
            # Execute redo
            redo_result = redo_handler.redo(action)

            # Mark action as redone
            action.is_redone = True
            action.redone_at = timezone.now()
            action.save()

            return {
                'success': True,
                'message': f'Successfully redone: {action.description}',
                'redone_action': action.action_id,
                'status': 'redone'
            }

        except Exception as e:
            logger.error(f"Failed to redo action {action_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error'
            }
```

---

##### **5. Undo/Redo Handlers**

**File**: `/services/core/historyapp/handlers.py`

```python
"""
Handlers for undoing and redoing specific action types.
Each handler knows how to reverse its specific action.
"""

class UndoHandler:
    """Base class for undo handlers"""

    @staticmethod
    def undo(action):
        """Undo the action"""
        raise NotImplementedError


class RedoHandler:
    """Base class for redo handlers"""

    @staticmethod
    def redo(action):
        """Redo the action"""
        raise NotImplementedError


class PlaylistCreateUndoHandler(UndoHandler):
    """Undo playlist creation = delete playlist"""

    @staticmethod
    def undo(action):
        from playlistapp.models import Playlist
        from trackapp.models import Track

        playlist_id = action.entity_id

        # Delete all tracks first
        Track.objects.filter(playlist_id=playlist_id).delete()

        # Delete playlist
        Playlist.objects.filter(id=playlist_id).delete()

        return {
            'new_state': {},
            'message': f'Deleted playlist {playlist_id}'
        }


class PlaylistDeleteUndoHandler(UndoHandler):
    """Undo playlist deletion = restore playlist + all tracks"""

    @staticmethod
    def undo(action):
        from playlistapp.models import Playlist
        from trackapp.models import Track

        before_state = action.before_state

        # Restore playlist
        playlist = Playlist.objects.create(
            id=before_state['id'],
            name=before_state['name'],
            description=before_state['description'],
            owner_id=before_state['owner_id'],
            visibility=before_state['visibility'],
            type=before_state.get('type', 'solo'),
            created_at=before_state['created_at'],
            updated_at=before_state['updated_at'],
        )

        # Restore tracks
        for track_data in before_state['tracks']:
            Track.objects.create(
                id=track_data['id'],
                playlist_id=playlist.id,
                song_id=track_data['song_id'],
                position=track_data['position'],
                added_at=track_data['added_at'],
            )

        return {
            'new_state': before_state,
            'message': f'Restored playlist {playlist.id}'
        }


class TrackAddUndoHandler(UndoHandler):
    """Undo track addition = remove track"""

    @staticmethod
    def undo(action):
        from trackapp.models import Track

        track_id = action.entity_id
        Track.objects.filter(id=track_id).delete()

        return {
            'new_state': action.before_state,
            'message': f'Removed track {track_id}'
        }


class TrackRemoveUndoHandler(UndoHandler):
    """Undo track removal = restore track"""

    @staticmethod
    def undo(action):
        from trackapp.models import Track

        before_state = action.before_state

        track = Track.objects.create(
            id=before_state['id'],
            playlist_id=before_state['playlist_id'],
            song_id=before_state['song_id'],
            position=before_state['position'],
            added_at=before_state['added_at'],
        )

        return {
            'new_state': {
                'id': track.id,
                'playlist_id': track.playlist_id,
                'song_id': track.song_id,
                'position': track.position,
            },
            'message': f'Restored track {track.id}'
        }


# Handler factories
class UndoHandlerFactory:
    """Factory for getting appropriate undo handler"""

    HANDLERS = {
        'playlist_create': PlaylistCreateUndoHandler,
        'playlist_delete': PlaylistDeleteUndoHandler,
        'track_add': TrackAddUndoHandler,
        'track_remove': TrackRemoveUndoHandler,
        # Add more handlers as needed
    }

    @classmethod
    def get_handler(cls, action_type):
        handler_class = cls.HANDLERS.get(action_type)
        if handler_class:
            return handler_class()
        return None


class RedoHandlerFactory:
    """Factory for getting appropriate redo handler"""

    HANDLERS = {
        # Redo handlers are similar to undo but reverse direction
        'playlist_create': PlaylistCreateUndoHandler,  # Redo create = create again
        'playlist_delete': PlaylistDeleteUndoHandler,  # Redo delete = delete again
        # Add more as needed
    }

    @classmethod
    def get_handler(cls, action_type):
        handler_class = cls.HANDLERS.get(action_type)
        if handler_class:
            return handler_class()
        return None
```

---

##### **6. API Views**

**File**: `/services/core/historyapp/views.py`

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import UserAction, UndoRedoConfiguration
from .services import UndoRedoService
from .serializers import UserActionSerializer


class UndoActionView(APIView):
    """Undo a specific action"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, action_id):
        result = UndoRedoService.undo_action(request.user.id, action_id)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


class RedoActionView(APIView):
    """Redo a previously undone action"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, action_id):
        result = UndoRedoService.redo_action(request.user.id, action_id)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


class UserActionsView(APIView):
    """List user's actions"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        actions = UserAction.objects.filter(
            user_id=request.user.id
        ).select_related('user').order_by('-created_at')[:50]

        serializer = UserActionSerializer(actions, many=True)
        return Response({
            'actions': serializer.data,
            'total': actions.count()
        })


class UndoableActionsView(APIView):
    """List actions that can be undone"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        actions = UserAction.objects.filter(
            user_id=request.user.id,
            is_undone=False
        ).filter(
            models.Q(undo_deadline__isnull=True) |
            models.Q(undo_deadline__gt=timezone.now())
        ).order_by('-created_at')[:50]

        serializer = UserActionSerializer(actions, many=True)
        return Response({
            'undoable_actions': serializer.data,
            'total': actions.count()
        })


class UndoRedoConfigView(APIView):
    """Get/update undo/redo configuration"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        config, created = UndoRedoConfiguration.objects.get_or_create(
            user_id=request.user.id
        )
        return Response({
            'undo_window_hours': config.undo_window_hours,
            'max_actions': config.max_actions,
            'auto_cleanup': config.auto_cleanup,
            'disabled_action_types': config.disabled_action_types,
        })

    def put(self, request):
        config, created = UndoRedoConfiguration.objects.get_or_create(
            user_id=request.user.id
        )

        config.undo_window_hours = request.data.get('undo_window_hours', config.undo_window_hours)
        config.max_actions = request.data.get('max_actions', config.max_actions)
        config.auto_cleanup = request.data.get('auto_cleanup', config.auto_cleanup)
        config.disabled_action_types = request.data.get('disabled_action_types', config.disabled_action_types)
        config.save()

        return Response({
            'message': 'Configuration updated',
            'config': {
                'undo_window_hours': config.undo_window_hours,
                'max_actions': config.max_actions,
                'auto_cleanup': config.auto_cleanup,
                'disabled_action_types': config.disabled_action_types,
            }
        })
```

---

##### **7. URL Routes**

**File**: `/services/core/historyapp/urls.py`

```python
from django.urls import path
from .views import (
    UndoActionView,
    RedoActionView,
    UserActionsView,
    UndoableActionsView,
    UndoRedoConfigView,
    RecordPlayView,
    RecentPlaysView,
    health_check,
)

urlpatterns = [
    # Existing
    path('', RecordPlayView.as_view()),
    path('health/', health_check),

    # Undo/Redo endpoints
    path('actions/', UserActionsView.as_view()),
    path('actions/undoable/', UndoableActionsView.as_view()),
    path('undo/<uuid:action_id>/', UndoActionView.as_view()),
    path('redo/<uuid:action_id>/', RedoActionView.as_view()),
    path('config/', UndoRedoConfigView.as_view()),
]
```

---

#### **🎯 Success Criteria**

- [ ] UserAction model created with all fields
- [ ] ActionLoggerMiddleware intercepts all mutations
- [ ] Action extractors for all trackable actions
- [ ] Undo/redo handlers implemented
- [ ] API endpoints functional
- [ ] Transaction safety ensured
- [ ] Performance tested (< 100ms per undo)
- [ ] Integration tests pass
- [ ] Documentation complete

---

#### **⚠️ Important Considerations**

**1. Cascading Actions**
- Undo playlist delete must restore all tracks
- Use transactions for atomicity
- Handle failures gracefully

**2. Concurrency**
- What if someone else modifies the entity?
- Check state validity before undo
- Use optimistic locking

**3. Performance**
- Limit history size (default: 1000 actions per user)
- Auto-cleanup old actions
- Index critical fields

**4. Storage**
- JSON fields can grow large
- Consider compression for old states
- Archive old actions periodically

**5. Security**
- Users can only undo their own actions
- Audit log of all undo/redo operations
- Rate limiting to prevent abuse

**Implementation**:

**Model Enhancements**:
```python
# services/core/searchapp/models.py

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)

    # Statistics
    song_count = models.IntegerField(default=0)
    follower_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

# Add to Song model
release_date = models.DateField(null=True, blank=True)
is_explicit = models.BooleanField(default=False)
popularity_score = models.IntegerField(default=0)  # 0-100
```

**API Endpoints**:
- `GET /api/discover/genres/` - List all genres
- `GET /api/discover/genres/{id}/` - Genre details with songs
- `GET /api/discover/new-releases/` - Recently released songs
- `GET /api/discover/trending/` - Trending songs
- `GET /api/discover/similar/{song_id}/` - Similar songs
- `GET /api/discover/recommendations/` - Personalized recommendations

**Recommendation Algorithm** (Basic):
```python
def get_similar_songs(song_id, limit=10):
    """Find similar songs based on genre, artist"""
    song = Song.objects.get(id=song_id)

    # Find songs by same artist
    same_artist = Song.objects.filter(
        artist=song.artist
    ).exclude(id=song_id)[:limit//2]

    # Find songs in same genre
    same_genre = Song.objects.filter(
        genre=song.genre
    ).exclude(id=song_id).order_by('-popularity_score')[:limit//2]

    return list(set(list(same_artist) + list(same_genre)))[:limit]
```

**Success Criteria**:
- [ ] Genre browsing working
- [ ] New releases endpoint working
- [ ] Trending songs working
- [ ] Similar songs algorithm working
- [ ] Basic personalized recommendations
- [ ] Tests pass

---

## **PHASE 4: Code Quality & Performance** (Days 8-10)
**Priority**: 🟢 LOW
**Time Investment**: 3 days
**Goal**: Improve maintainability and performance

### **Task 4.1: Extract Common Patterns**
**All Services**
**Time**: 1 day

**Duplications to Remove**:

1. **Health Check Endpoints**
   - All apps have identical health check
   - Extract to shared utility

2. **Permission Checks**
   - Create reusable permission classes

3. **Pagination**
   - Create pagination mixin

**Implementation**:

**File**: `/services/core/utils/mixins.py`

```python
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination

class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow read access to everyone, write access to owner only"""

    def has_object_permission(self, request, view, obj):
        # Read permissions allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only allowed to owner
        return obj.owner_id == request.user.id

class IsPlaylistOwnerOrCollaborator(permissions.BasePermission):
    """Allow access to playlist owner or collaborators"""

    def has_permission(self, request, view):
        from utils.service_clients import CollaborationServiceClient

        playlist_id = view.kwargs.get('playlist_id')
        if not playlist_id:
            return False

        # Check if owner
        try:
            from playlistapp.models import Playlist
            playlist = Playlist.objects.get(id=playlist_id)
            if playlist.owner_id == request.user.id:
                return True
        except Playlist.DoesNotExist:
            return False

        # Check if collaborator
        return CollaborationServiceClient.is_collaborator(playlist_id, request.user.id)

class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list views"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
```

**Success Criteria**:
- [ ] Health check extracted to utility
- [ ] Common permission classes created
- [ ] Pagination mixin created
- [ ] All views updated to use mixins
- [ ] Code duplication reduced

---

### **Task 4.2: Performance Optimizations**
**All Services**
**Time**: 1 day

**Optimizations**:

1. **Add select_related and prefetch_related**
   - Identify N+1 query problems
   - Add optimizations to list views

2. **Database Indexes**
   - Review all models for missing indexes
   - Add composite indexes for common queries

3. **Query Optimization**
   - Use `.only()` and `.defer()` for large models
   - Add `select_related` for foreign keys
   - Add `prefetch_related` for many-to-many

**Example**:
```python
# Before
playlists = Playlist.objects.all()

# After
playlists = Playlist.objects.select_related(
    'owner'
).prefetch_related(
    'tracks__song__artist',
    'tracks__song__album'
).only(
    'id', 'name', 'description', 'owner_id',
    'owner__id', 'owner__username'
)
```

**Success Criteria**:
- [ ] N+1 queries eliminated
- [ ] Database indexes added
- [ ] Query count reduced by 50%
- [ ] Response times improved

---

### **Task 4.3: Testing & Documentation**
**All Services**
**Time**: 1 day

**Testing Additions**:
1. Integration tests for service communication
2. Authorization tests for all endpoints
3. Performance tests for critical paths

**Documentation Updates**:
1. Update API documentation with new endpoints
2. Add architecture diagrams
3. Document service communication patterns

**Success Criteria**:
- [ ] Test coverage > 80%
- [ ] All critical paths tested
- [ ] API docs updated
- [ ] Architecture documented

---

## 📊 Implementation Timeline

### **Week 1: Critical Fixes & Architecture**
- Day 1: Phase 1 (Security fixes)
- Days 2-3: Phase 2 (Architecture cleanup)

### **Week 2: Feature Enhancements (Part 1)**
- Days 4-7: Phase 3.1-3.4 (User profiles, social features, music discovery)

### **Week 3: Feature Enhancements (Part 2)**
- Days 8-10: Phase 3.5 (Undo/Redo system - MAJOR FEATURE)

### **Week 4: Quality & Performance**
- Days 11-13: Phase 4 (Code quality & performance)

---

## ✅ Success Criteria

### **Phase 1 Success**:
- [ ] Authorization vulnerability fixed
- [ ] All migrations created and applied
- [ ] No TODO comments in code

### **Phase 2 Success**:
- [ ] No direct imports between services
- [ ] Consistent error response format
- [ ] Standardized field naming

### **Phase 3 Success**:
- [ ] User profiles implemented
- [ ] User-to-user following working
- [ ] Playlist comments functional
- [ ] Music discovery features working

### **Phase 4 Success**:
- [ ] Code duplication reduced
- [ ] Performance improved (50% fewer queries)
- [ ] Test coverage > 80%
- [ ] Documentation complete

---

## 🚀 Deployment Readiness Checklist

### **Pre-Deployment**:
- [ ] All phases complete
- [ ] All tests passing
- [ ] Security audit passed
- [ ] Performance benchmarks met
- [ ] Documentation updated

### **Deployment Steps**:
1. Create backup of database
2. Deploy to staging environment
3. Run smoke tests
4. Monitor for 24 hours
5. Deploy to production

### **Post-Deployment**:
- [ ] Monitor error rates
- [ ] Check performance metrics
- [ ] Verify service communication
- [ ] Test critical user flows

---

## 📝 Notes & Considerations

### **Rollback Plan**:
- Keep previous deployment available
- Database migrations must be reversible
- Feature flags for new features

### **Risks & Mitigations**:
1. **Cross-service communication failure**
   - Mitigation: Circuit breakers, retry logic
2. **Migration failures**
   - Mitigation: Test migrations in staging first
3. **Performance regression**
   - Mitigation: Benchmark before and after

### **Future Enhancements** (Out of Scope):
- Real-time collaborative editing
- Advanced recommendation algorithms
- Smart playlists with auto-update criteria
- Offline availability
- Push notifications

---

## 🎓 Lessons Learned

### **What Went Well**:
- Comprehensive feature set implemented
- Good separation of concerns
- Extensive API coverage

### **What Needs Improvement**:
- Cross-service dependencies violated architecture
- Authorization checks incomplete
- Missing user-focused features

### **Process Improvements**:
- More thorough security reviews
- Architecture validation before implementation
- User experience consideration in backend design

---

## 📞 Contact & Support

**Project Owner**: Sakib
**Documentation**: `/docs/`
**Code Repository**: `/home/sakib/Projects/Spotify_ISD/Spotify_ISD_backend`

**Emergency Contacts**:
- Backend issues: Sakib
- Deployment issues: DevOps team

---

**Plan Status**: ✅ Ready for Implementation
**Next Step**: Begin Phase 1 - Task 1.1 (Fix Authorization Vulnerability)
**Target Completion**: 10 days from start

---

*This plan is a living document. Update as priorities change or new issues are discovered.*
