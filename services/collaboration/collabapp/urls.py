from django.urls import path
from .views import GenerateInviteView, JoinView, CollaboratorListView, HealthCheckView

urlpatterns = [
    path("health/", HealthCheckView.as_view()),
    path("<int:playlist_id>/invite/", GenerateInviteView.as_view()),
    path("join/<str:token>/", JoinView.as_view()),
    path("<int:playlist_id>/members/", CollaboratorListView.as_view()),
]
