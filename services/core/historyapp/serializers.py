from rest_framework import serializers
from .models import Play, UserAction, UndoRedoConfiguration
from searchapp.serializers import SongSerializer


class PlaySerializer(serializers.ModelSerializer):
    song = SongSerializer(read_only=True)

    class Meta:
        model = Play
        fields = ["id", "user_id", "song", "played_at"]
        read_only_fields = ["user_id", "played_at"]


class UserActionSerializer(serializers.ModelSerializer):
    """Serializer for UserAction model"""

    class Meta:
        model = UserAction
        fields = [
            'id', 'action_id', 'user_id', 'session_id',
            'action_type', 'entity_type', 'entity_id',
            'before_state', 'after_state', 'delta',
            'description', 'ip_address', 'user_agent',
            'is_undone', 'undone_at', 'undone_action_id',
            'is_redone', 'redone_at', 'redone_action_id',
            'is_undoable', 'undo_deadline',
            'parent_action_id', 'related_actions',
            'created_at'
        ]
        read_only_fields = [
            'id', 'action_id', 'created_at', 'undone_at', 'redone_at'
        ]

    def get_action_type_display(self, obj):
        return obj.get_action_type_display()


class UndoRedoConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for UndoRedoConfiguration model"""

    class Meta:
        model = UndoRedoConfiguration
        fields = [
            'user_id', 'undo_window_hours', 'max_actions',
            'auto_cleanup', 'disabled_action_types',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user_id', 'created_at', 'updated_at']
