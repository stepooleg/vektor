"""URL-конфигурация авторизации (подключается под /api/v1/auth/)."""

from __future__ import annotations

from django.urls import path

from .views import CurrentUserView, LoginView, LogoutView

app_name = "users"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
]
