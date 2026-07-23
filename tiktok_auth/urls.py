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
    path(
    "content/",
    views.content_planner,
    name="content-planner",
    ),
    path(
    "content/new/",
    views.create_content_idea,
    name="create-content-idea",
    ),
    path(
    "content/<int:idea_id>/edit/",
    views.edit_content_idea,
    name="edit-content-idea",
    ),
    path(
    "content/<int:idea_id>/delete/",
    views.delete_content_idea,
    name="delete-content-idea",
    ),
    path(
    "performance/sync/",
    views.sync_performance,
    name="sync-tiktok-performance",
    ),

    
]
