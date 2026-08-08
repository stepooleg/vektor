"""URL-конфигурация уведомлений (подключается под /api/v1/notifications/)."""

from __future__ import annotations

from django.urls import path

from .views import SubscribeView, UnsubscribeView, VapidPublicKeyView

app_name = "notifications"

urlpatterns = [
    path("vapid-public/", VapidPublicKeyView.as_view(), name="vapid-public"),
    path("subscribe/", SubscribeView.as_view(), name="subscribe"),
    path("unsubscribe/<path:endpoint>/", UnsubscribeView.as_view(), name="unsubscribe"),
]
