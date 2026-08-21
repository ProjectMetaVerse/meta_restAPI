"""HTTP client boundary for Meta Graph API calls."""

from typing import Any, cast

import httpx

from meta_api.core.config import Settings


class GraphAPIClient:
    """Small async client that centralizes Graph API URL and timeout policy."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=settings.request_timeout)
        self._owns_client = client is None

    async def get(self, path: str, **params: str) -> dict[str, Any]:
        """GET a Graph API resource and return its JSON object."""
        base_url = self._settings.graph_api_base_url.rstrip("/")
        url = f"{base_url}/{self._settings.graph_api_version}/{path.lstrip('/')}"
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def aclose(self) -> None:
        """Close the underlying HTTP client when this instance owns it."""
        if self._owns_client:
            await self._client.aclose()
