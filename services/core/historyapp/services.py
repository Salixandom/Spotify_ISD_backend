from django.db import transaction
from django.utils import timezone
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
            reason = 'already_undone' if action.is_undone else 'expired' if action.undo_deadline else 'not_undoable'
            return {
                'success': False,
                'error': 'Action cannot be undone',
                'reason': reason,
                'status': 'cannot_undo'
            }

        # Perform undo based on action type
        from .handlers import UndoHandlerFactory
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

            return {
                'success': True,
                'message': f'Successfully undone: {action.description}',
                'undone_action': str(action.action_id),
                'status': 'undone',
                'result': undo_result
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
            reason = 'not_undone' if not action.is_undone else 'already_redone'
            return {
                'success': False,
                'error': 'Action cannot be redone',
                'reason': reason,
                'status': 'cannot_redo'
            }

        # Perform redo based on action type
        from .handlers import RedoHandlerFactory
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
                'redone_action': str(action.action_id),
                'status': 'redone',
                'result': redo_result
            }

        except Exception as e:
            logger.error(f"Failed to redo action {action_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error'
            }
