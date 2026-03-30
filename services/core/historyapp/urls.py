from django.urls import path
from .views import (
    RecordPlayView, RecentPlaysView, health_check,
    UndoActionView, RedoActionView,
    UserActionsView, UndoableActionsView,
    UndoRedoConfigView,
)

urlpatterns = [
    # Existing
    path("health/", health_check),
    path("played/", RecordPlayView.as_view()),
    path("recent/", RecentPlaysView.as_view()),

    # Undo/Redo endpoints
    path("actions/", UserActionsView.as_view()),
    path("actions/undoable/", UndoableActionsView.as_view()),
    path("undo/<uuid:action_id>/", UndoActionView.as_view(), name='undo-action'),
    path("redo/<uuid:action_id>/", RedoActionView.as_view(), name='redo-action'),
    path("config/", UndoRedoConfigView.as_view(), name='undo-config'),
]
