from django.urls import path
from .views import (
    RecordPlayView, RecentPlaysView, health_check,
    UndoActionView, RedoActionView,
    UserActionsView, UndoableActionsView,
    UndoRedoConfigView,
)

urlpatterns = [
    # Existing
    path("health/", health_check, name="history-health"),
    path("played/", RecordPlayView.as_view(), name="record-play"),
    path("recent/", RecentPlaysView.as_view(), name="recent-plays"),

    # Undo/Redo endpoints
    path("actions/", UserActionsView.as_view(), name="user-actions"),
    path("actions/undoable/", UndoableActionsView.as_view(), name="undoable-actions"),
    path("undo/<uuid:action_id>/", UndoActionView.as_view(), name='undo-action'),
    path("redo/<uuid:action_id>/", RedoActionView.as_view(), name='redo-action'),
    path("config/", UndoRedoConfigView.as_view(), name='undo-config'),
]
