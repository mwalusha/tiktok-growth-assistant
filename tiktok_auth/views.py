import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from .analytics import get_account_analytics, get_daily_growth
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from .content_coach import (
    AIContentCoachError,
    generate_content_ideas,
)
from .content_generator import generate_personalized_content_ideas
from .content_calendar import (
    generate_weekly_calendar,
    next_calendar_week,
)
from .creator_score import get_creator_score
from .posting_times import get_best_posting_times
from .viral_predictor import (
    ViralPredictionError,
    score_draft,
)
from .trend_hunter import (
    get_trend_hunter,
    get_trending_hashtag_names,
)
from .peer_benchmark import build_peer_comparison
from .chat_assistant import (
    call_chat_llm,
    save_chat_exchange,
)
from .models import ChatConversation, PeerComparison
from .models import TikTokAccount
from .services import (
    TikTokAPIError,
    exchange_code_for_token,
    get_tiktok_profile,
    revoke_access,
)
from .forms import (
    ChatAssistantForm,
    ContentCoachForm,
    ContentIdeaForm,
    GeneratedIdeaSaveForm,
    ViralPredictorForm,
)
from .sync import ensure_valid_access_token, sync_tiktok_performance
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
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account first.",
        )
        return redirect("home")

    token_expired = False

    try:
        ensure_valid_access_token(account)

    except TikTokAPIError as exc:
        token_expired = True

        logger.warning(
            "TikTok token validation failed: %s",
            exc,
        )

        messages.warning(
            request,
            "Your TikTok connection needs to be renewed.",
        )

    analytics = get_account_analytics(account)
    daily_growth = get_daily_growth(account)
    creator_score = get_creator_score(account)
    best_posting_times = get_best_posting_times(account)
    weekly_report = account.weekly_reports.select_related(
        "best_video",
        "worst_video",
    ).first()

    return render(
        request,
        "tiktok_auth/dashboard.html",
        {
            "account": account,
            "analytics": analytics,
            "daily_growth": daily_growth,
            "creator_score": creator_score,
            "best_posting_times": best_posting_times,
            "weekly_report": weekly_report,
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
def viral_predictor(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account before scoring a draft.",
        )
        return redirect("home")

    prediction = None

    if request.method == "POST":
        form = ViralPredictorForm(request.POST)

        if form.is_valid():
            try:
                prediction = score_draft(
                    account,
                    form.cleaned_data["caption"],
                    form.cleaned_data["hashtags"],
                    trending_hashtags=(
                        get_trending_hashtag_names(account)
                    ),
                )
            except ViralPredictionError as exc:
                messages.error(request, str(exc))
    else:
        form = ViralPredictorForm()

    return render(
        request,
        "tiktok_auth/viral_predictor.html",
        {
            "account": account,
            "form": form,
            "prediction": prediction,
        },
    )


@require_http_methods(["GET", "POST"])
def trend_hunter(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account before viewing trends.",
        )
        return redirect("home")

    if request.method == "POST":
        opted_in = request.POST.get("participate") == "yes"
        account.allow_trend_aggregation = opted_in
        account.save(
            update_fields=[
                "allow_trend_aggregation",
                "updated_at",
            ]
        )
        messages.success(
            request,
            (
                "Anonymous trend participation enabled."
                if opted_in
                else "Anonymous trend participation disabled."
            ),
        )
        return redirect("trend-hunter")

    return render(
        request,
        "tiktok_auth/trend_hunter.html",
        {
            "account": account,
            "trend_data": get_trend_hunter(account),
        },
    )


@require_http_methods(["GET", "POST"])
def peer_benchmarks(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account before comparing peers.",
        )
        return redirect("home")

    if request.method == "POST":
        account.allow_peer_comparison = True
        account.save(
            update_fields=[
                "allow_peer_comparison",
                "updated_at",
            ]
        )
        PeerComparison.objects.create(
            requesting_account=account
        )
        messages.success(
            request,
            "Comparison invitation created.",
        )
        return redirect("peer-benchmarks")

    accepted = (
        PeerComparison.objects.filter(
            Q(requesting_account=account)
            | Q(peer_account=account),
            status=PeerComparison.Status.ACCEPTED,
            requesting_account__allow_peer_comparison=True,
            peer_account__allow_peer_comparison=True,
        )
        .select_related(
            "requesting_account",
            "peer_account",
        )
    )
    comparisons = [
        build_peer_comparison(item, account)
        for item in accepted
    ]
    pending = account.comparison_requests_sent.filter(
        status=PeerComparison.Status.PENDING
    ).order_by("-created_at")
    pending_links = [
        {
            "comparison": item,
            "url": request.build_absolute_uri(
                reverse(
                    "accept-peer-invite",
                    args=[item.invite_token],
                )
            ),
        }
        for item in pending
    ]
    return render(
        request,
        "tiktok_auth/peer_benchmarks.html",
        {
            "account": account,
            "comparisons": comparisons,
            "pending_links": pending_links,
        },
    )


@require_http_methods(["GET", "POST"])
def chat_assistant(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account before using the assistant.",
        )
        return redirect("home")

    conversation, _ = ChatConversation.objects.get_or_create(
        account=account
    )

    if request.method == "POST":
        form = ChatAssistantForm(request.POST)

        if form.is_valid():
            user_message = form.cleaned_data["message"].strip()

            try:
                assistant_message = call_chat_llm(
                    account,
                    conversation,
                    user_message,
                )
            except AIContentCoachError as exc:
                messages.error(request, str(exc))
            else:
                save_chat_exchange(
                    conversation,
                    user_message,
                    assistant_message,
                )
                return redirect("chat-assistant")
    else:
        form = ChatAssistantForm()

    return render(
        request,
        "tiktok_auth/chat_assistant.html",
        {
            "account": account,
            "chat_messages": conversation.messages.all(),
            "form": form,
        },
    )


@require_http_methods(["GET", "POST"])
def accept_peer_invite(request, token):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect the comparison TikTok account before accepting.",
        )
        return redirect("home")

    comparison = get_object_or_404(
        PeerComparison,
        invite_token=token,
        status=PeerComparison.Status.PENDING,
    )

    if comparison.requesting_account == account:
        messages.error(
            request,
            "A different connected account must accept this invitation.",
        )
        return redirect("peer-benchmarks")

    if request.method == "POST":
        account.allow_peer_comparison = True
        account.save(
            update_fields=[
                "allow_peer_comparison",
                "updated_at",
            ]
        )
        comparison.peer_account = account
        comparison.status = PeerComparison.Status.ACCEPTED
        comparison.accepted_at = timezone.now()
        comparison.save(
            update_fields=[
                "peer_account",
                "status",
                "accepted_at",
            ]
        )
        messages.success(
            request,
            "Peer comparison accepted.",
        )
        return redirect("peer-benchmarks")

    return render(
        request,
        "tiktok_auth/accept_peer_invite.html",
        {
            "account": account,
            "comparison": comparison,
        },
    )


@require_POST
def revoke_peer_comparison(request, comparison_id):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account first.",
        )
        return redirect("home")

    comparison = get_object_or_404(
        PeerComparison,
        Q(requesting_account=account) | Q(peer_account=account),
        pk=comparison_id,
        status=PeerComparison.Status.ACCEPTED,
    )
    comparison.status = PeerComparison.Status.REVOKED
    comparison.save(update_fields=["status"])
    messages.success(request, "Peer comparison revoked.")
    return redirect("peer-benchmarks")


@require_http_methods(["GET", "POST"])
def content_calendar(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account before using the calendar.",
        )
        return redirect("home")

    week_start = next_calendar_week()
    week_end = week_start + timedelta(days=6)

    if request.method == "POST":
        try:
            result = generate_weekly_calendar(
                account,
                week_start=week_start,
            )
        except AIContentCoachError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                (
                    "Your seven-day calendar was generated for "
                    f"{result['week_start']:%B %d}–"
                    f"{result['week_end']:%B %d}."
                ),
            )

        return redirect("content-calendar")

    calendar_ideas = account.content_ideas.filter(
        calendar_date__range=(week_start, week_end)
    ).order_by("calendar_date")
    return render(
        request,
        "tiktok_auth/content_calendar.html",
        {
            "account": account,
            "week_start": week_start,
            "week_end": week_end,
            "calendar_ideas": calendar_ideas,
        },
    )


@require_http_methods(["GET", "POST"])
def content_coach(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account before using the content coach.",
        )
        return redirect("home")

    analytics = get_account_analytics(account)

    if request.method == "POST":
        form = ContentCoachForm(request.POST)

        if form.is_valid():
            niche = form.cleaned_data["niche"].strip()

            if account.niche != niche:
                account.niche = niche
                account.save(
                    update_fields=["niche", "updated_at"]
                )

            if not analytics["videos_analyzed"]:
                messages.warning(
                    request,
                    "Sync your TikTok videos before using the content coach.",
                )
            else:
                ideas = generate_personalized_content_ideas(
                    account, analytics, count=5
                )
                if ideas:
                    messages.success(
                        request,
                        f"{len(ideas)} evidence-based ideas were saved.",
                    )
                else:
                    messages.info(
                        request,
                        "Your current personalized ideas are already saved.",
                    )
                return redirect("content-planner")
    else:
        form = ContentCoachForm(
            initial={"niche": account.niche}
        )

    return render(
        request,
        "tiktok_auth/content_coach.html",
        {
            "account": account,
            "form": form,
            "generated_ideas": [],
            "analytics": analytics,
        },
    )


@require_POST
def generate_and_save_content_ideas(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account before generating ideas.",
        )
        return redirect("home")

    analytics = get_account_analytics(account)
    if not analytics["videos_analyzed"]:
        messages.warning(
            request,
            (
                "Sync your TikTok performance before generating ideas. "
                "The generator only uses stored video history."
            ),
        )
        return redirect("tiktok-dashboard")

    generated_ideas = generate_personalized_content_ideas(
        account, analytics, count=5
    )

    if generated_ideas:
        messages.success(
            request,
            (
                f"{len(generated_ideas)} ideas generated from your "
                "TikTok results and saved to the planner."
            ),
        )
    else:
        messages.info(
            request,
            (
                "No new non-duplicate ideas were available. Your current "
                "personalized ideas are already in the planner."
            ),
        )
    return redirect("content-planner")


@require_POST
def update_content_idea_status(request, idea_id):
    account = get_connected_account(request)
    if not account:
        return redirect("home")
    idea = get_object_or_404(ContentIdea, pk=idea_id, account=account)
    allowed = {
        ContentIdea.Status.READY,
        ContentIdea.Status.FILMED,
        ContentIdea.Status.PUBLISHED,
    }
    status = request.POST.get("status", "")
    if status not in allowed:
        messages.error(request, "That planner status is not supported.")
        return redirect("content-planner")
    idea.status = status
    idea.save(update_fields=["status", "updated_at"])
    messages.success(request, f'“{idea.title}” marked {idea.get_status_display()}.')
    return redirect("content-planner")


@require_POST
def save_generated_idea(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account first.",
        )
        return redirect("home")

    form = GeneratedIdeaSaveForm(request.POST)

    if not form.is_valid():
        messages.error(
            request,
            "That generated idea could not be saved.",
        )
        return redirect("content-coach")

    ContentIdea.objects.create(
        account=account,
        title=form.cleaned_data["title"],
        category=ContentIdea.Category.OTHER,
        hook=form.cleaned_data["hook"],
        caption=form.cleaned_data["caption"],
        hashtags=form.cleaned_data["hashtags"],
        reason=form.cleaned_data["reason"],
        suggested_length=form.cleaned_data[
            "suggested_length"
        ],
        suggested_posting_time=form.cleaned_data[
            "suggested_posting_time"
        ],
        notes="Generated by the AI content coach.",
    )
    messages.success(
        request,
        "Generated idea saved to your content planner.",
    )
    return redirect("content-planner")


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

@require_POST
def sync_performance(request):
    account = get_connected_account(request)

    if not account:
        messages.info(
            request,
            "Connect your TikTok account first.",
        )
        return redirect("home")

    try:
        result = sync_tiktok_performance(
            account=account,
        )

        messages.success(
            request,
            (
                "TikTok performance synchronized successfully. "
                f"{result['videos_saved']} videos were updated."
            ),
        )

    except TikTokAPIError as exc:
        logger.exception(
            "TikTok performance synchronization failed."
        )

        messages.error(
            request,
            f"Synchronization failed: {exc}",
        )

    except Exception:
        logger.exception(
            "Unexpected performance synchronization error."
        )

        messages.error(
            request,
            "An unexpected error occurred while synchronizing TikTok data.",
        )

    return redirect("tiktok-dashboard")
