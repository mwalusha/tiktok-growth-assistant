from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path(
        "admin/",
        admin.site.urls
    ),

    path(
        "tiktok/",
        include("tiktok_auth.urls")
    ),
]
