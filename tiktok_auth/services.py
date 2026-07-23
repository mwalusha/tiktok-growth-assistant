import requests

from django.conf import settings


TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_REVOKE_URL = "https://open.tiktokapis.com/v2/oauth/revoke/"
TIKTOK_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
TIKTOK_VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"


class TikTokAPIError(Exception):
    """Raised when TikTok returns an unsuccessful API response."""


def _client_key() -> str:
    return (settings.TIKTOK_CLIENT_KEY or "").strip()


def _client_secret() -> str:
    return (settings.TIKTOK_CLIENT_SECRET or "").strip()


def _redirect_uri() -> str:
    return (settings.TIKTOK_REDIRECT_URI or "").strip()


def _parse_json_response(response: requests.Response) -> dict:
    try:
        return response.json()
    except ValueError as exc:
        raise TikTokAPIError(
            "TikTok returned an invalid response."
        ) from exc


def _post_token_request(payload: dict) -> dict:
    try:
        response = requests.post(
            TIKTOK_TOKEN_URL,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise TikTokAPIError(
            "TikTok could not be reached."
        ) from exc

    data = _parse_json_response(response)

    if not response.ok or data.get("error"):
        description = (
            data.get("error_description")
            or data.get("message")
            or data.get("error")
            or "TikTok token request failed."
        )

        log_id = data.get("log_id")

        if log_id:
            description = f"{description} Log ID: {log_id}"

        raise TikTokAPIError(description)

    return data


def exchange_code_for_token(code: str) -> dict:
    """
    Exchange the authorization code returned by TikTok
    for an access token and refresh token.
    """

    payload = {
        "client_key": _client_key(),
        "client_secret": _client_secret(),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": _redirect_uri(),
    }

    return _post_token_request(payload)


def refresh_access_token(refresh_token: str) -> dict:
    """
    Use a refresh token to obtain a new access token.
    """

    if not refresh_token:
        raise TikTokAPIError(
            "No TikTok refresh token is available."
        )

    payload = {
        "client_key": _client_key(),
        "client_secret": _client_secret(),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token.strip(),
    }

    return _post_token_request(payload)


def get_tiktok_profile(access_token: str) -> dict:
    """
    Retrieve the connected user's basic TikTok profile.
    """

    if not access_token:
        raise TikTokAPIError(
            "No TikTok access token is available."
        )

    try:
        response = requests.get(
            TIKTOK_USER_INFO_URL,
            params={
                "fields": ",".join(
    [
        "open_id",
        "display_name",
        "avatar_url",
        "username",
        "profile_deep_link",
        "bio_description",
        "is_verified",
        "follower_count",
        "following_count",
        "likes_count",
        "video_count",
    ]
),
            },
            headers={
                "Authorization": f"Bearer {access_token.strip()}",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise TikTokAPIError(
            "TikTok could not be reached while loading the profile."
        ) from exc

    payload = _parse_json_response(response)

    if not response.ok:
        error_data = payload.get("error", {})

        message = (
            error_data.get("message")
            or payload.get("message")
            or "TikTok profile request failed."
        )

        raise TikTokAPIError(message)

    api_error = payload.get("error", {})

    if api_error.get("code") not in (None, "", "ok"):
        raise TikTokAPIError(
            api_error.get(
                "message",
                "TikTok returned an unknown profile error.",
            )
        )

    try:
        return payload["data"]["user"]
    except (KeyError, TypeError) as exc:
        raise TikTokAPIError(
            "TikTok returned an unexpected profile response."
        ) from exc


def revoke_access(access_token: str) -> None:
    """
    Revoke TikTok authorization when the user disconnects.
    """

    if not access_token:
        return

    payload = {
        "client_key": _client_key(),
        "client_secret": _client_secret(),
        "token": access_token.strip(),
    }

    try:
        response = requests.post(
            TIKTOK_REVOKE_URL,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise TikTokAPIError(
            "TikTok could not be reached while disconnecting."
        ) from exc

    if not response.ok:
        try:
            data = response.json()
        except ValueError:
            data = {}

        description = (
            data.get("error_description")
            or data.get("message")
            or "TikTok access could not be revoked."
        )

        raise TikTokAPIError(description)


def get_tiktok_videos(
    access_token: str,
    cursor: int = 0,
    max_count: int = 20,
) -> dict:
    """
    Retrieve one page of the connected user's public videos.
    """

    if not access_token:
        raise TikTokAPIError(
            "No TikTok access token is available."
        )

    fields = ",".join(
        [
            "id",
            "create_time",
            "cover_image_url",
            "share_url",
            "video_description",
            "duration",
            "title",
            "embed_link",
            "like_count",
            "comment_count",
            "share_count",
            "view_count",
        ]
    )

    try:
        response = requests.post(
            TIKTOK_VIDEO_LIST_URL,
            params={
                "fields": fields,
            },
            json={
                "max_count": max_count,
                "cursor": cursor,
            },
            headers={
                "Authorization": (
                    f"Bearer {access_token.strip()}"
                ),
                "Content-Type": "application/json",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise TikTokAPIError(
            "TikTok could not be reached while loading videos."
        ) from exc

    payload = _parse_json_response(response)
    api_error = payload.get("error", {})

    if not response.ok:
        raise TikTokAPIError(
            api_error.get("message")
            or "TikTok video request failed."
        )

    if api_error.get("code") not in (None, "", "ok"):
        raise TikTokAPIError(
            api_error.get(
                "message",
                "TikTok returned a video-list error.",
            )
        )

    return payload.get("data", {})
def get_all_tiktok_videos(
    access_token: str,
    max_pages: int = 50,
) -> list[dict]:
    """
    Retrieve all available public videos using pagination.
    """

    all_videos = []
    cursor = 0

    for _ in range(max_pages):
        data = get_tiktok_videos(
            access_token=access_token,
            cursor=cursor,
            max_count=20,
        )

        videos = data.get("videos", [])

        all_videos.extend(videos)

        if not data.get("has_more"):
            break

        next_cursor = data.get("cursor")

        if next_cursor is None or next_cursor == cursor:
            break

        cursor = next_cursor

    return all_videos