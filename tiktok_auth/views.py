import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import TikTokAccount
from .services import (
    TikTokAPIError,
    exchange_code_for_token,
    get_tiktok_profile,
)

logger = logging.getLogger(__name__)

TIKTOK_AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"


def connect_tiktok(request):
    client_key = settings.TIKTOK_CLIENT_KEY.strip()

    if not client_key:
        messages.error(
            request,
            "TikTok OAuth is not configured correctly.",
        )
        return redirect("home")

    state = secrets.token_urlsafe(32)
    request.session["tiktok_oauth_state"] = state

    query = urlencode(
        {
            "client_key": client_key,
            "response_type": "code",
            "scope": "user.info.basic",
            "redirect_uri": settings.TIKTOK_REDIRECT_URI.strip(),
            "state": state,
        }
    )

    logger.info(
        "Redirecting to TikTok OAuth. client_key_prefix=%s",
        client_key[:4],
    )

    return redirect(f"{TIKTOK_AUTHORIZE_URL}?{query}")


def tiktok_callback(request):
    returned_state = request.GET.get("state")
    stored_state = request.session.pop(
        "tiktok_oauth_state",
        None,
    )

    if (
        not returned_state
        or not stored_state
        or not secrets.compare_digest(
            returned_state,
            stored_state,
        )
    ):
        messages.error(
            request,
            "TikTok authorization could not be verified.",
        )
        return redirect("home")

    oauth_error = request.GET.get("error")

    if oauth_error:
        description = request.GET.get(
            "error_description",
            "Authorization cancelled.",
        )

        logger.error(
            "TikTok OAuth returned error=%s description=%s",
            oauth_error,
            description,
        )

        messages.error(
            request,
            description,
        )

        return redirect("home")

    code = request.GET.get("code")

    if not code:
        logger.error("TikTok callback returned no code.")

        messages.error(
            request,
            "TikTok did not return an authorization code.",
        )

        return redirect("home")

    try:
        logger.info("Starting token exchange.")

        token_data = exchange_code_for_token(code)

        logger.info(
            "Token response keys: %s",
            list(token_data.keys()),
        )

        access_token = token_data.get("access_token")

        if not access_token:
            raise TikTokAPIError(
                "TikTok did not return an access token."
            )

        logger.info("Loading TikTok profile.")

        profile = get_tiktok_profile(access_token)

        logger.info(
            "Profile response keys: %s",
            list(profile.keys()),
        )

        open_id = profile.get("open_id")

        if not open_id:
            raise TikTokAPIError(
                "TikTok did not return open_id."
            )

        now = timezone.now()

        access_expires_in = int(
            token_data.get("expires_in", 0)
        )

        refresh_expires_in = int(
            token_data.get("refresh_expires_in", 0)
        )

        account, _ = TikTokAccount.objects.update_or_create(
            open_id=open_id,
            defaults={
                "display_name": profile.get(
                    "display_name",
                    "",
                ),
                "avatar_url": profile.get(
                    "avatar_url",
                    "",
                ),
                "access_token": access_token,
                "refresh_token": token_data.get(
                    "refresh_token",
                    "",
                ),
                "access_token_expires_at": (
                    now + timedelta(
                        seconds=access_expires_in
                    )
                    if access_expires_in
                    else None
                ),
                "refresh_token_expires_at": (
                    now + timedelta(
                        seconds=refresh_expires_in
                    )
                    if refresh_expires_in
                    else None
                ),
                "scope": token_data.get(
                    "scope",
                    "",
                ),
            },
        )

        request.session["tiktok_account_id"] = account.pk

        logger.info(
            "TikTok account connected successfully."
        )

        messages.success(
            request,
            "Your TikTok account was connected successfully.",
        )

        return redirect("tiktok-dashboard")

    except Exception:
        logger.exception(
            "TikTok callback failed."
        )

        messages.error(
            request,
            "TikTok connection failed. Check Render logs."
        )

        return redirect("home")


def dashboard(request):
    account_id = request.session.get(
        "tiktok_account_id"
    )

    if not account_id:
        messages.info(
            request,
            "Connect your TikTok account first.",
        )

        return redirect("home")

    account = get_object_or_404(
        TikTokAccount,
        pk=account_id,
    )

    token_expired = bool(
        account.access_token_expires_at
        and account.access_token_expires_at
        <= timezone.now()
    )

    return render(
        request,
        "tiktok_auth/dashboard.html",
        {
            "account": account,
            "token_expired": token_expired,
        },
    )


@require_POST
def disconnect_tiktok(request):
    account_id = request.session.pop(
        "tiktok_account_id",
        None,
    )

    if account_id:
        TikTokAccount.objects.filter(
            pk=account_id
        ).delete()

    messages.success(
        request,
        "TikTok account disconnected.",
    )

    return redirect("home")