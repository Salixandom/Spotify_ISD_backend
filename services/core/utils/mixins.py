"""
Common mixins and utilities for reducing code duplication across services.
"""
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Allow read access to everyone, write access to owner only.
    Works with models that have an owner_id field.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only allowed to owner
        return hasattr(obj, 'owner_id') and obj.owner_id == request.user.id


class IsPlaylistOwnerOrCollaborator(permissions.BasePermission):
    """
    Allow access to playlist owner or collaborators.
    Checks both ownership and collaboration status.
    """

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
        try:
            auth_token = request.headers.get('Authorization', '')
            is_collab = CollaborationServiceClient.is_collaborator(playlist_id, request.user.id)
            return is_collab
        except Exception:
            # If service communication fails, default to False
            return False

    def has_object_permission(self, request, view, obj):
        # Also check object-level permissions
        if hasattr(obj, 'owner_id') and obj.owner_id == request.user.id:
            return True

        # Check collaboration for object
        if hasattr(obj, 'playlist_id'):
            try:
                auth_token = request.headers.get('Authorization', '')
                from utils.service_clients import CollaborationServiceClient
                return CollaborationServiceClient.is_collaborator(obj.playlist_id, request.user.id)
            except Exception:
                return False

        return False


class IsOwnerOrCollaborator(permissions.BasePermission):
    """
    Generic owner or collaborator check.
    Works with models that have both owner_id and collaboration relationships.
    """

    def has_object_permission(self, request, view, obj):
        # Check if owner
        if hasattr(obj, 'owner_id') and obj.owner_id == request.user.id:
            return True

        # Check if collaborator (for models with playlist_id)
        if hasattr(obj, 'playlist_id'):
            try:
                from utils.service_clients import CollaborationServiceClient
                auth_token = request.headers.get('Authorization', '')
                return CollaborationServiceClient.is_collaborator(obj.playlist_id, request.user.id)
            except Exception:
                pass

        return False


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination for list views.
    Consistent pagination across all endpoints.
    """

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        """
        Return paginated response in standard format.
        """
        return {
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        }


def health_check(service_name):
    """
    Factory function for creating health check views.
    Eliminates code duplication across services.
    """
    from django.db import connection
    from utils.responses import SuccessResponse, ServiceUnavailableResponse

    def health_check_view(request):
        """
        Health check endpoint for monitoring and orchestration.
        Returns 200 if service and database are healthy.
        """
        try:
            # Check database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            return SuccessResponse(
                data={'status': 'healthy', 'service': service_name, 'database': 'connected'},
                message='Service is healthy'
            )
        except Exception as e:
            return ServiceUnavailableResponse(
                message=f'Database connection failed: {str(e)}'
            )

    health_check_view.__name__ = f'health_check_{service_name}'
    return health_check_view


class FilterByOwnerMixin:
    """
    Mixin for views that filter querysets by owner.
    Automatically filters to user's own records for non-admin users.
    """

    def get_queryset(self):
        """
        Filter queryset to show only user's own records.
        Override this method for custom filtering logic.
        """
        queryset = super().get_queryset()

        # Filter by owner if queryset has owner_id field
        if hasattr(queryset.model, 'owner_id'):
            # Admin users can see all records
            if not (hasattr(self.request.user, 'is_staff') and self.request.user.is_staff):
                queryset = queryset.filter(owner_id=self.request.user.id)

        return queryset


class BulkOperationMixin:
    """
    Mixin for handling bulk operations (batch create, update, delete).
    Provides consistent error reporting for bulk operations.
    """

    def perform_bulk_operation(self, items, operation_func):
        """
        Perform bulk operation on items with detailed error tracking.

        Args:
            items: List of items to process
            operation_func: Function to apply to each item

        Returns:
            dict with success, failed, and errors details
        """
        succeeded = []
        failed = []
        errors = []

        for index, item in enumerate(items):
            try:
                result = operation_func(item)
                succeeded.append({
                    'index': index,
                    'item': item,
                    'result': result
                })
            except Exception as e:
                failed.append({
                    'index': index,
                    'item': item,
                    'error': str(e)
                })
                errors.append({
                    'index': index,
                    'error': str(e)
                })

        return {
            'total': len(items),
            'succeeded': len(succeeded),
            'failed': len(failed),
            'results': succeeded,
            'errors': errors
        }
