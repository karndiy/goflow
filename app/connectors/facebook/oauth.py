from urllib.parse import urlencode

from app.connectors.facebook.client import FacebookGraphClient

AUTH_DIALOG_BASE_URL = "https://www.facebook.com"

DEFAULT_SCOPES = ("pages_show_list", "pages_manage_posts", "pages_read_engagement")


def build_authorization_url(
    api_version: str,
    app_id: str,
    redirect_uri: str,
    state: str,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
) -> str:
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": ",".join(scopes),
    }
    return f"{AUTH_DIALOG_BASE_URL}/{api_version}/dialog/oauth?{urlencode(params)}"


async def exchange_code_for_token(
    client: FacebookGraphClient, app_id: str, app_secret: str, redirect_uri: str, code: str
) -> dict:
    return await client.get(
        "oauth/access_token",
        {
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
    )


async def exchange_for_long_lived_token(
    client: FacebookGraphClient, app_id: str, app_secret: str, short_lived_token: str
) -> dict:
    return await client.get(
        "oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_lived_token,
        },
    )


async def list_pages(client: FacebookGraphClient, user_access_token: str) -> list[dict]:
    result = await client.get("me/accounts", {"access_token": user_access_token})
    return result.get("data", [])
