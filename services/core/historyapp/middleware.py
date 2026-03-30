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
            'session_id': request.session.session_key if hasattr(request, 'session') else None,
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
        extractor = get_action_extractor(request.path, request.method)

        if not extractor:
            return

        # Extract action details
        action_details = extractor.extract(request, response)

        # Only log if extractor returned valid data
        if not action_details:
            return

        # Create UserAction record
        action = UserAction.objects.create(
            action_id=action_data['action_id'],
            user_id=action_data['user_id'],
            session_id=action_data['session_id'],
            action_type=action_details['action_type'],
            entity_type=action_details['entity_type'],
            entity_id=action_details['entity_id'],
            before_state=action_details.get('before_state', {}),
            after_state=action_details.get('after_state', {}),
            delta=action_details.get('delta', {}),
            description=action_details.get('description', ''),
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
