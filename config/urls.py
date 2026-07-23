from pathlib import Path

from django.contrib import admin
from django.http import FileResponse
from django.urls import include, path


BASE_DIR = Path(__file__).resolve().parent.parent

VERIFICATION_FILE = (
    BASE_DIR
    / "tiktokhED9dGtav5cgUf3CqjbbQJDBZmf0kFky.txt"
)


def tiktok_verification(request):
    return FileResponse(
        open(VERIFICATION_FILE, "rb"),
        content_type="text/plain",
    )


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "tiktok/",
        include("tiktok_auth.urls"),
    ),

    path(
        "tiktokhED9dGtav5cgUf3CqjbbQJDBZmf0kFky.txt",
        tiktok_verification,
        name="tiktok-verification",
    ),
       path(
        "",
        include("pages.urls")
    ),
]
