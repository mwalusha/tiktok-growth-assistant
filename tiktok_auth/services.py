import requests

from django.conf import settings


TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_REVOKE_URL = "https://open.tiktokapis.com/v2/oauth/revoke/"
TIKTOK_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"


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
                "fields": "open_id,display_name,avatar_url",
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