import httpx

BASE_URL = "https://open.tiktokapis.com"


class TikTokAPIError(Exception):
    def __init__(self, message: str, code: str | None = None, log_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.log_id = log_id


class TikTokClient:
    """Wraps the Content Posting API's envelope: `{"data": {...}, "error": {"code": "ok", ...}}`.

    The OAuth token endpoint (`v2/oauth/token/`) uses a different, plain OAuth2-style error
    shape -- it does NOT go through `post_json`/`_parse`; see `tiktok.oauth` for that.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client or httpx.AsyncClient(timeout=20.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()

    async def post_json(self, path: str, body: dict, access_token: str) -> dict:
        response = await self._http_client.post(
            f"{BASE_URL}/{path}",
            json=body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )
        return self._parse(response)

    async def post_form(self, path: str, data: dict) -> dict:
        """Used for the OAuth token endpoint, which shares this host but not the Content
        Posting API's response envelope -- callers parse the raw JSON themselves."""
        response = await self._http_client.post(
            f"{BASE_URL}/{path}",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return response.json()

    @staticmethod
    def _parse(response: httpx.Response) -> dict:
        payload = response.json()
        error = payload.get("error") or {}
        code = error.get("code")
        if code and code != "ok":
            raise TikTokAPIError(
                message=error.get("message", "Unknown TikTok API error"),
                code=code,
                log_id=error.get("log_id"),
            )
        return payload.get("data") or {}
