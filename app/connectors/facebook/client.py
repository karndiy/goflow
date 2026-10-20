import httpx

GRAPH_API_BASE_URL = "https://graph.facebook.com"


class FacebookAPIError(Exception):
    def __init__(
        self,
        message: str,
        code: int | None = None,
        subcode: int | None = None,
        fbtrace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.subcode = subcode
        self.fbtrace_id = fbtrace_id


class FacebookGraphClient:
    def __init__(self, api_version: str, http_client: httpx.AsyncClient | None = None) -> None:
        self._base_url = f"{GRAPH_API_BASE_URL}/{api_version}"
        self._http_client = http_client or httpx.AsyncClient(timeout=15.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()

    async def get(self, path: str, params: dict) -> dict:
        response = await self._http_client.get(f"{self._base_url}/{path}", params=params)
        return self._parse(response)

    async def post(self, path: str, data: dict) -> dict:
        response = await self._http_client.post(f"{self._base_url}/{path}", data=data)
        return self._parse(response)

    @staticmethod
    def _parse(response: httpx.Response) -> dict:
        payload = response.json()
        if response.status_code >= 400 or "error" in payload:
            error = payload.get("error", {})
            raise FacebookAPIError(
                message=error.get("message", "Unknown Facebook API error"),
                code=error.get("code"),
                subcode=error.get("error_subcode"),
                fbtrace_id=error.get("fbtrace_id"),
            )
        return payload
