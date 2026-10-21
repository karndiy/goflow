from urllib.parse import urlencode

from app.connectors.tiktok.client import TikTokClient

AUTH_BASE_URL = "https://www.tiktok.com"

# user.info.basic: display name for the connected account. video.publish: direct-post content.
DEFAULT_SCOPES = ("user.info.basic", "video.publish")


class TikTokOAuthError(Exception):
    pass


def build_authorization_url(
    client_key: str,
    redirect_uri: str,
    state: str,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
) -> str:
    params = {
        "client_key": client_key,
        "scope": ",".join(scopes),
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{AUTH_BASE_URL}/v2/auth/authorize/?{urlencode(params)}"


def _parse_token_response(payload: dict) -> dict:
    # Standard OAuth2-style error shape, distinct from the Content Posting API's envelope.
    if "access_token" not in payload:
        message = (
            payload.get("error_description")
            or payload.get("error")
            or "TikTok token exchange failed"
        )
        raise TikTokOAuthError(str(message))
    return payload


async def exchange_code_for_token(
    client: TikTokClient, client_key: str, client_secret: str, redirect_uri: str, code: str
) -> dict:
    payload = await client.post_form(
        "v2/oauth/token/",
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )
    return _parse_token_response(payload)


async def refresh_access_token(
    client: TikTokClient, client_key: str, client_secret: str, refresh_token: str
) -> dict:
    payload = await client.post_form(
        "v2/oauth/token/",
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    return _parse_token_response(payload)


async def get_creator_info(client: TikTokClient, access_token: str) -> dict:
    return await client.post_json("v2/post/publish/creator_info/query/", {}, access_token)
