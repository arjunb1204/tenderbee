"""
URL endpoints for Authentication & Accounts.
"""
from django.urls import re_path
from apps.accounts.views import (
    CurrentUserAPIView,
    LoginAPIView,
    LogoutAPIView,
    RefreshTokenAPIView,
    RegisterAPIView,
)

app_name = "accounts"

urlpatterns = [
    re_path(r"^register/?$", RegisterAPIView.as_view(), name="auth-register"),
    re_path(r"^login/?$", LoginAPIView.as_view(), name="auth-login"),
    re_path(r"^token/?$", LoginAPIView.as_view(), name="token-obtain-pair"),
    re_path(r"^refresh/?$", RefreshTokenAPIView.as_view(), name="auth-refresh"),
    re_path(r"^token/refresh/?$", RefreshTokenAPIView.as_view(), name="token-refresh"),
    re_path(r"^logout/?$", LogoutAPIView.as_view(), name="auth-logout"),
    re_path(r"^me/?$", CurrentUserAPIView.as_view(), name="auth-me"),
]
