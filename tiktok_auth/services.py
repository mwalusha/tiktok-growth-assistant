import requests

from django.conf import settings


TIKTOK_TOKEN_URL = (
    "https://open.tiktokapis.com/v2/oauth/token/"
)


def exchange_code_for_token(code):
    payload = {
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "client_secret": settings.TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.TIKTOK_REDIRECT_URI,
    }

    response = requests.post(
        TIKTOK_TOKEN_URL,
        data=payload,
        headers={
            "Content-Type": (
                "application/x-www-form-urlencoded"
            )
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()