import secrets
from urllib.parse import urlencode

import requests

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .models import TikTokAccount
from .services import exchange_code_for_token


def connect_tiktok(request):
    """
    Start the TikTok OAuth authorization flow.
    """

    state = secrets.token_urlsafe(32)

    request.session["tiktok_oauth_state"] = state

    params = {
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "response_type": "code",
        "scope": "user.info.basic",
        "redirect_uri": settings.TIKTOK_REDIRECT_URI,
        "state": state,
    }

    authorization_url = (
        "https://www.tiktok.com/v2/auth/authorize/"
        f"?{urlencode(params)}"
    )

    return redirect(authorization_url)


def tiktok_callback(request):
    """
    Handle the response from TikTok.
    """

    returned_state = request.GET.get("state")

    saved_state = request.session.pop(
        "tiktok_oauth_state",
        None
    )

    if not returned_state or returned_state != saved_state:
        return HttpResponse(
            "Invalid OAuth state.",
            status=400
        )

    error = request.GET.get("error")

    if error:
        error_description = request.GET.get(
            "error_description",
            "TikTok authorization failed."
        )

        return HttpResponse(
            f"{error}: {error_description}",
            status=400
        )

    code = request.GET.get("code")

    if not code:
        return HttpResponse(
            "No authorization code was returned.",
            status=400
        )

    token_data = exchange_code_for_token(code)

    access_token = token_data["access_token"]

    profile_response = requests.get(
        "https://open.tiktokapis.com/v2/user/info/",
        params={
            "fields": (
                "open_id,"
                "display_name,"
                "avatar_url"
            )
        },
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        timeout=30,
    )

    profile_response.raise_for_status()

    profile_data = profile_response.json()

    user_data = profile_data["data"]["user"]

    TikTokAccount.objects.update_or_create(
        open_id=user_data["open_id"],
        defaults={
            "display_name": user_data.get(
                "display_name",
                ""
            ),
            "avatar_url": user_data.get(
                "avatar_url",
                ""
            ),
            "access_token": token_data[
                "access_token"
            ],
            "refresh_token": token_data[
                "refresh_token"
            ],
            "scope": token_data.get(
                "scope",
                ""
            ),
        },
    )

    messages.success(
        request,
        "TikTok account connected successfully!"
    )

    return redirect("tiktok-dashboard")