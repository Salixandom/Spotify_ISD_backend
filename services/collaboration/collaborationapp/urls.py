from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CollaborationViewSet, InviteLinkViewSet, health_check

router = DefaultRouter()
router.register(r'playlists', CollaborationViewSet, basename='collaboration')
router.register(r'invites', InviteLinkViewSet, basename='invites')

urlpatterns = [
    path('health/', health_check),
    path('', include(router.urls)),
]
