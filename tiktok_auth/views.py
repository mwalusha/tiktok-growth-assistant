import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from .models import TikTokAccount
from .services import (
    TikTokAPIError,
    exchange_code_for_token,
    get_tiktok_profile,
    refresh_access_token,
    revoke_access,
)
from .forms import ContentIdeaForm
from .models import ContentIdea, TikTokAccount
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
            "scope": ",".join(
                [
                    "user.info.basic",
                    "video.list",
                    "user.info.profile",
                    "user.info.stats",
                ]
            ),

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
    """
    Handle TikTok's OAuth callback.

    This view:
    1. Validates the OAuth state.
    2. Exchanges the authorization code for tokens.
    3. Retrieves the TikTok profile and statistics.
    4. Creates or updates the TikTokAccount record.
    5. Stores the connected account ID in the session.
    """

    oauth_error = request.GET.get("error")
    oauth_error_description = request.GET.get(
        "error_description",
        "",
    )

    if oauth_error:
        logger.warning(
            "TikTok OAuth authorization failed. Error=%s Description=%s",
            oauth_error,
            oauth_error_description,
        )

        messages.error(
            request,
            oauth_error_description
            or "TikTok authorization was cancelled or denied.",
        )

        return redirect("home")

    returned_state = request.GET.get("state")
    saved_state = request.session.pop(
        "tiktok_oauth_state",
        None,
    )

    if not saved_state:
        logger.warning(
            "TikTok callback received without a saved OAuth state."
        )

        messages.error(
            request,
            "Your TikTok connection session expired. Please try again.",
        )

        return redirect("home")

    if not returned_state or returned_state != saved_state:
        logger.warning(
            "TikTok OAuth state mismatch. Returned=%s",
            returned_state,
        )

        messages.error(
            request,
            "TikTok connection could not be verified. Please try again.",
        )

        return redirect("home")

    authorization_code = request.GET.get("code")

    if not authorization_code:
        logger.warning(
            "TikTok callback did not contain an authorization code."
        )

        messages.error(
            request,
            "TikTok did not return an authorization code.",
        )

        return redirect("home")

    try:
        token_data = exchange_code_for_token(
            authorization_code,
        )

        logger.info(
            "TikTok token response received. Keys=%s",
            list(token_data.keys()),
        )

        access_token = token_data.get("access_token")

        if not access_token:
            raise TikTokAPIError(
                token_data.get("error_description")
                or "TikTok did not return an access token."
            )

        profile = get_tiktok_profile(
            access_token,
        )

        logger.info(
            "TikTok profile response received. Keys=%s",
            list(profile.keys()),
        )

        open_id = profile.get("open_id")

        if not open_id:
            raise TikTokAPIError(
                "TikTok did not return an account identifier."
            )

        now = timezone.now()

        access_expires_in = int(
            token_data.get("expires_in") or 0
        )

        refresh_expires_in = int(
            token_data.get("refresh_expires_in") or 0
        )

        access_token_expires_at = (
            now + timedelta(seconds=access_expires_in)
            if access_expires_in
            else None
        )

        refresh_token_expires_at = (
            now + timedelta(seconds=refresh_expires_in)
            if refresh_expires_in
            else None
        )

        account, created = TikTokAccount.objects.update_or_create(
            open_id=open_id,
            defaults={
                "display_name": profile.get(
                    "display_name",
                    "",
                ),
                "username": profile.get(
                    "username",
                    "",
                ),
                "avatar_url": profile.get(
                    "avatar_url",
                    "",
                ),
                "profile_deep_link": profile.get(
                    "profile_deep_link",
                    "",
                ),
                "bio_description": profile.get(
                    "bio_description",
                    "",
                ),
                "is_verified": bool(
                    profile.get(
                        "is_verified",
                        False,
                    )
                ),
                "follower_count": int(
                    profile.get("follower_count") or 0
                ),
                "following_count": int(
                    profile.get("following_count") or 0
                ),
                "likes_count": int(
                    profile.get("likes_count") or 0
                ),
                "video_count": int(
                    profile.get("video_count") or 0
                ),
                "access_token": access_token,
                "refresh_token": token_data.get(
                    "refresh_token",
                    "",
                ),
                "scope": token_data.get(
                    "scope",
                    "",
                ),
                "access_token_expires_at": (
                    access_token_expires_at
                ),
                "refresh_token_expires_at": (
                    refresh_token_expires_at
                ),
            },
        )

        request.session["tiktok_account_id"] = account.pk

        request.session.modified = True

        if created:
            messages.success(
                request,
                "Your TikTok account was connected successfully.",
            )
        else:
            messages.success(
                request,
                "Your TikTok account connection was updated successfully.",
            )

        logger.info(
            "TikTok account saved successfully. Account ID=%s Created=%s",
            account.pk,
            created,
        )

        return redirect("tiktok-dashboard")

    except TikTokAPIError as exc:
        logger.warning(
            "TikTok API error during callback: %s",
            exc,
        )

        messages.error(
            request,
            str(exc),
        )

        return redirect("home")

    except (TypeError, ValueError) as exc:
        logger.exception(
            "TikTok returned invalid numerical or token data."
        )

        messages.error(
            request,
            "TikTok returned invalid account data. Please reconnect.",
        )

        return redirect("home")

    except Exception:
        logger.exception(
            "Unexpected TikTok callback failure."
        )

        messages.error(
            request,
            "An unexpected error occurred while connecting TikTok.",
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

def get_connected_account(request):
    account_id = request.session.get("tiktok_account_id")

    if not account_id:
        return None

    return TikTokAccount.objects.filter(
        pk=account_id
    ).first()


def content_planner(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account before using the content planner.",
        )
        return redirect("home")

    ideas = ContentIdea.objects.filter(
        account=account
    )

    status_filter = request.GET.get("status", "").strip()

    if status_filter:
        ideas = ideas.filter(
            status=status_filter
        )

    return render(
        request,
        "tiktok_auth/content_planner.html",
        {
            "account": account,
            "ideas": ideas,
            "status_filter": status_filter,
            "status_choices": ContentIdea.Status.choices,
        },
    )


@require_http_methods(["GET", "POST"])
def create_content_idea(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account first.",
        )
        return redirect("home")

    if request.method == "POST":
        form = ContentIdeaForm(request.POST)

        if form.is_valid():
            content_idea = form.save(commit=False)
            content_idea.account = account
            content_idea.save()

            messages.success(
                request,
                "Content idea saved successfully.",
            )

            return redirect("content-planner")
    else:
        form = ContentIdeaForm()

    return render(
        request,
        "tiktok_auth/content_idea_form.html",
        {
            "form": form,
            "page_title": "Create content idea",
            "button_text": "Save idea",
        },
    )


@require_http_methods(["GET", "POST"])
def edit_content_idea(request, idea_id):
    account = get_connected_account(request)

    if not account:
        return redirect("home")

    idea = get_object_or_404(
        ContentIdea,
        pk=idea_id,
        account=account,
    )

    if request.method == "POST":
        form = ContentIdeaForm(
            request.POST,
            instance=idea,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Content idea updated successfully.",
            )

            return redirect("content-planner")
    else:
        form = ContentIdeaForm(
            instance=idea
        )

    return render(
        request,
        "tiktok_auth/content_idea_form.html",
        {
            "form": form,
            "page_title": "Edit content idea",
            "button_text": "Save changes",
            "idea": idea,
        },
    )


@require_POST
def delete_content_idea(request, idea_id):
    account = get_connected_account(request)

    if not account:
        return redirect("home")

    idea = get_object_or_404(
        ContentIdea,
        pk=idea_id,
        account=account,
    )

    idea.delete()

    messages.success(
        request,
        "Content idea deleted.",
    )

    return redirect("content-planner")