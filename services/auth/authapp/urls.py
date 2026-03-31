from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView,
    MeView,
    health_check,
    MyProfileView,
    PublicProfileView,
    UpdateAvatarView,
    FollowUserView,
    FollowersView,
    FollowingView,
    CustomTokenObtainPairView,
    ChangePasswordView,
)
from .token_views import CustomTokenRefreshView

urlpatterns = [
    # Authentication
    path("register/", RegisterView.as_view()),
    path("login/", CustomTokenObtainPairView.as_view()),  # Custom login with response wrapper
    path("token/refresh/", CustomTokenRefreshView.as_view()),  # Custom refresh with response wrapper
    path("me/", MeView.as_view()),
    path("change-password/", ChangePasswordView.as_view()),  # Password change endpoint

    # User Profiles
    path("profile/me/", MyProfileView.as_view()),
    path("profile/me/avatar/", UpdateAvatarView.as_view()),
    path("profile/<int:user_id>/", PublicProfileView.as_view()),

    # Social - Follow/Unfollow
    path("social/follow/<int:user_id>/", FollowUserView.as_view()),
    path("social/followers/", FollowersView.as_view()),
    path("social/following/", FollowingView.as_view()),
    path("social/followers/<int:user_id>/", FollowersView.as_view()),
    path("social/following/<int:user_id>/", FollowingView.as_view()),

    # Health Check
    path("health/", health_check),
]
