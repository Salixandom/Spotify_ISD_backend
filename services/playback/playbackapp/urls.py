from django.urls import path
from .views import AudioFileUploadView, AudioFileListView, AudioFileStreamView, health_check

urlpatterns = [
    path("upload/", AudioFileUploadView.as_view()),
    path("files/", AudioFileListView.as_view()),
    path("stream/<int:pk>/", AudioFileStreamView.as_view()),
    path("health/", health_check),
]
