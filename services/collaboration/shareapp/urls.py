from django.urls import path
from .views import CreateShareLinkView, ViewShareLinkView, health_check

urlpatterns = [
    path('health/', health_check),
    path('<int:playlist_id>/create/', CreateShareLinkView.as_view()),
    path('view/<str:token>/', ViewShareLinkView.as_view()),
]
