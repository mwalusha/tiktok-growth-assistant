from django.urls import path

from . import views


urlpatterns = [
    path(
        "connect/",
        views.connect_tiktok,
        name="connect-tiktok",
    ),
    path(
        "callback/",
        views.tiktok_callback,
        name="tiktok-callback",
    ),
    path(
        "dashboard/",
        views.dashboard,
        name="tiktok-dashboard",
    ),
    path(
        "disconnect/",
        views.disconnect_tiktok,
        name="disconnect-tiktok",
    ),
]