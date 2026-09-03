from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from relaydesk.config import get_settings
from relaydesk.errors import Unauthorized

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


@dataclass(frozen=True, slots=True)
class GoogleProfile:
    sub: str
    email: str
    name: str
    email_verified: bool


def authorization_url(redirect_uri: str, state: str) -> str:
    settings = get_settings()
    if not settings.google_client_id:
        raise Unauthorized("Google sign-in is not configured.")
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return f"{AUTH_ENDPOINT}?{query}"


async def exchange_code(code: str, redirect_uri: str) -> GoogleProfile:
    """Swap an authorization code for the user's profile.

    The userinfo call is a server-to-server request over TLS, so the
    ``id_token`` needs no JWKS verification and we need no JWT library.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as http:
        token_response = await http.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_response.status_code != 200:
            raise Unauthorized("Google sign-in failed.")
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise Unauthorized("Google sign-in failed.")

        profile_response = await http.get(
            USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"}
        )
        if profile_response.status_code != 200:
            raise Unauthorized("Google sign-in failed.")

    body = profile_response.json()
    return GoogleProfile(
        sub=str(body["sub"]),
        email=str(body.get("email", "")),
        name=str(body.get("name") or body.get("email", "")),
        email_verified=bool(body.get("email_verified")),
    )
