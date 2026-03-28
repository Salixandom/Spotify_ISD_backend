from django.urls import path
from .views import RecordPlayView, RecentPlaysView, health_check

urlpatterns = [
    path("health/", health_check),
    path("played/", RecordPlayView.as_view()),
    path("recent/", RecentPlaysView.as_view()),
]
