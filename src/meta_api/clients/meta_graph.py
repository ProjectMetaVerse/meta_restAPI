"""Safe asynchronous client for the Meta Graph API."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from meta_api.exceptions.base import InvalidUpstreamPayloadError, MetaUpstreamError

logger = logging.getLogger(__name__)


class MetaGraphClient:
    """Small, defensive Graph API client with no credential-bearing logs."""

    def __init__(
        self,
        base_url: str,
        version: str,
        *,
        connect_timeout: float = 5.0,
        read_timeout: float = 10.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("graph_api_base_url must be an absolute URL without query parameters")
        self.base_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
        self.version = version.strip("/")
        self.timeout = httpx.Timeout(
            read=read_timeout, connect=connect_timeout, write=read_timeout, pool=connect_timeout
        )
        self.max_retries = max_retries
        self.transport = transport

    def _url(self, path: str) -> str:
        clean = path.strip("/")
        if (
            not clean
            or "?" in clean
            or "#" in clean
            or any(part in {".", ".."} for part in clean.split("/"))
        ):
            raise ValueError("invalid Graph API path")
        return f"{self.base_url}/{quote(self.version, safe='.')}/{quote(clean, safe='/')}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        data: Mapping[str, str] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        rid = request_id or str(uuid.uuid4())
        headers = {"Accept": "application/json", "X-Request-ID": rid}
        attempts = 0
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            while True:
                attempts += 1
                try:
                    response = await client.request(
                        method, self._url(path), params=params, data=data, headers=headers
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempts <= self.max_retries:
                        await asyncio.sleep(min(0.05 * 2 ** (attempts - 1), 0.5))
                        continue
                    logger.warning("meta_graph_transport_failure request_id=%s", rid)
                    raise MetaUpstreamError(
                        "Meta service temporarily unavailable", retryable=True
                    ) from exc
                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    if attempts <= self.max_retries:
                        await asyncio.sleep(min(0.05 * 2 ** (attempts - 1), 0.5))
                        continue
                    raise MetaUpstreamError(
                        "Meta service temporarily unavailable",
                        status_code=response.status_code,
                        retryable=True,
                    )
                try:
                    payload = response.json()
                except (ValueError, json.JSONDecodeError) as exc:
                    raise InvalidUpstreamPayloadError("Meta returned an invalid response") from exc
                if not isinstance(payload, dict):
                    raise InvalidUpstreamPayloadError("Meta returned an invalid response")
                if response.is_error or isinstance(payload.get("error"), dict):
                    raise MetaUpstreamError(
                        "Meta rejected the request", status_code=response.status_code
                    )
                return payload
