from django.urls import path
from .views import SearchView, BrowseView, health_check

urlpatterns = [
    path('health/', health_check),
    path('', SearchView.as_view()),
    path('browse/', BrowseView.as_view()),
]
