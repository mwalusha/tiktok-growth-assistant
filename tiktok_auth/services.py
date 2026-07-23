import requests

from django.conf import settings


TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"


class TikTokAPIError(Exception):
    """Raised when TikTok returns an unsuccessful API response."""


def exchange_code_for_token(code: str) -> dict:
    payload = {
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "client_secret": settings.TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.TIKTOK_REDIRECT_URI,
    }

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
            "TikTok could not be reached during token exchange."
        ) from exc

    if not response.ok:
        raise TikTokAPIError(
            f"TikTok token exchange failed: {response.text}"
        )

    return response.json()


def get_tiktok_profile(access_token: str) -> dict:
    try:
        response = requests.get(
            TIKTOK_USER_INFO_URL,
            params={
                "fields": "open_id,display_name,avatar_url",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise TikTokAPIError(
            "TikTok could not be reached while loading the profile."
        ) from exc

    if not response.ok:
        raise TikTokAPIError(
            f"TikTok profile request failed: {response.text}"
        )

    payload = response.json()

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