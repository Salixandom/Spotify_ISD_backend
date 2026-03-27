from django.urls import path
from .views import (
    GenerateInviteView,
    JoinView,
    CollaboratorListView,
    HealthCheckView,
    MyCollaborationsView,
    MyRoleView,
    DeactivateInviteView,
)

urlpatterns = [
    path('health/', HealthCheckView.as_view()),
    path('<int:playlist_id>/invite/', GenerateInviteView.as_view()),
    path('join/<str:token>/', JoinView.as_view()),
    path('<int:playlist_id>/members/', CollaboratorListView.as_view()),
    path('my-collaborations/', MyCollaborationsView.as_view()),
    path('<int:playlist_id>/my-role/', MyRoleView.as_view()),
    path('<int:playlist_id>/invite/deactivate/', DeactivateInviteView.as_view()),
]
