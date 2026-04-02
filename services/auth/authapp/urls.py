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
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", CustomTokenObtainPairView.as_view(), name="login"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),

    # User Profiles
    path("profile/me/", MyProfileView.as_view(), name="my-profile"),
    path("profile/me/avatar/", UpdateAvatarView.as_view(), name="update-avatar"),
    path("profile/<int:user_id>/", PublicProfileView.as_view(), name="user-profile-detail"),

    # Social - Follow/Unfollow
    path("social/follow/<int:user_id>/", FollowUserView.as_view(), name="follow-user"),
    path("social/followers/", FollowersView.as_view(), name="followers"),
    path("social/following/", FollowingView.as_view(), name="following"),
    path("social/followers/<int:user_id>/", FollowersView.as_view(), name="followers-of-user"),
    path("social/following/<int:user_id>/", FollowingView.as_view(), name="following-of-user"),

    # Health Check
    path("health/", health_check, name="auth-health"),
]
