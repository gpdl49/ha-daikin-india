"""HTTP transports for DSIOT ``/dsiot/multireq`` requests.

The same request bodies work against the adapter on the LAN and against the
Daikin India cloud; only the host, auth header and base path differ.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import CLOUD_HOST, LOCAL_BASE, MULTIREQ_PATH
from .errors import (
    ApiError,
    AuthError,
    CommunicationError,
    DeviceOfflineError,
    UnsupportedDeviceError,
)

if TYPE_CHECKING:
    from .cloud_auth import CloudAuth

_LOGGER = logging.getLogger(__name__)

OP_READ = 2
OP_WRITE = 3

RSC_OK = range(2000, 2005)
RSC_AUTH = {401, 4001}
RSC_OFFLINE = 5107


class Transport(ABC):
    """Sends multireq batches and returns the ``responses`` list."""

    timeout = 10

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        # Adapters handle concurrent requests poorly; the app serialises them.
        self._lock: asyncio.Lock | _NullLock = asyncio.Lock()
        self._write_method = "PUT"

    @abstractmethod
    def base_for(self, edge_id: str | None) -> str:
        """Return the resource base path (``/dsiot/edge`` or ``/dsiot/edges/<ri>``)."""

    @abstractmethod
    async def _headers(self) -> dict[str, str]:
        """Return request headers, including authorization."""

    @abstractmethod
    def _url(self) -> str:
        """Return the multireq URL."""

    async def read(self, targets: list[str]) -> list[dict[str, Any]]:
        """Read several resources in one batch; one response per target, in order."""
        body = {"requests": [{"op": OP_READ, "to": to} for to in targets]}
        responses = await self._send("POST", body)
        if len(responses) != len(targets):
            raise CommunicationError(f"Expected {len(targets)} responses, got {len(responses)}")
        return responses

    async def write(self, to: str, pc: dict[str, Any]) -> dict[str, Any]:
        """Write one resource and raise if the result code is not OK."""
        body = {"requests": [{"op": OP_WRITE, "to": to, "pc": pc}]}
        try:
            responses = await self._send(self._write_method, body)
        except _MethodNotAllowed:
            # The app writes with PUT; some firmware only accepts POST.
            self._write_method = "POST"
            responses = await self._send("POST", body)
        if not responses:
            raise CommunicationError("Empty write response")
        check_rsc(responses[0], to)
        return responses[0]

    async def _send(self, method: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        async with self._lock:
            return await self._request(method, body)

    async def _request(
        self, method: str, body: dict[str, Any], *, retry_auth: bool = True
    ) -> list[dict[str, Any]]:
        headers = await self._headers()
        try:
            async with asyncio.timeout(self.timeout):
                async with self._session.request(
                    method, self._url(), json=body, headers=headers
                ) as resp:
                    text = await resp.text()
                    status = resp.status
        except (TimeoutError, aiohttp.ClientError) as err:
            raise CommunicationError(f"Request to {self._url()} failed: {err}") from err

        if status == 405:
            raise _MethodNotAllowed
        if status in (401, 403):
            if retry_auth and await self._on_unauthorized():
                return await self._request(method, body, retry_auth=False)
            raise AuthError(f"HTTP {status} from {self._url()}")
        if status == 404:
            raise UnsupportedDeviceError(
                "/dsiot/multireq not found; the adapter firmware may be too old"
            )
        if status >= 400:
            # The body stays out of the exception, which ends up in the UI and logs.
            _LOGGER.debug("HTTP %s from %s: %.200s", status, self._url(), text)
            raise CommunicationError(f"HTTP {status} from {self._url()}")
        try:
            data = json.loads(text)
        except ValueError as err:
            raise CommunicationError(f"Invalid JSON from {self._url()}") from err
        responses = data.get("responses") if isinstance(data, dict) else None
        if not isinstance(responses, list):
            raise CommunicationError(f"No responses in reply from {self._url()}")
        return responses

    async def _on_unauthorized(self) -> bool:
        """Hook for refreshing credentials; return True to retry once."""
        return False


class _MethodNotAllowed(Exception):
    pass


def check_rsc(response: dict[str, Any], to: str) -> None:
    """Raise an appropriate error for a non-OK per-request result code."""
    rsc = response.get("rsc", 2000)
    try:
        rsc = int(rsc)
    except (TypeError, ValueError):
        rsc = 2000
    if rsc in RSC_OK:
        return
    if rsc in RSC_AUTH:
        raise AuthError(f"Authorization rejected for {to} (rsc {rsc})")
    if rsc == RSC_OFFLINE:
        raise DeviceOfflineError(f"Unit is not connected to the cloud ({to})")
    raise ApiError(f"Request to {to} failed with rsc {rsc}", rsc)


class LocalTransport(Transport):
    """Talks to the Wi-Fi adapter over plain HTTP on the LAN."""

    def __init__(self, session: aiohttp.ClientSession, host: str, pin: str | None = None) -> None:
        super().__init__(session)
        self.host = host
        self.pin = pin or None

    def base_for(self, edge_id: str | None) -> str:
        return LOCAL_BASE

    def _url(self) -> str:
        return f"http://{self.host}{MULTIREQ_PATH}"

    async def _headers(self) -> dict[str, str]:
        # The lock PIN is sent literally, not base64-encoded.
        return {"Authorization": f"Basic {self.pin}"} if self.pin else {}


class CloudTransport(Transport):
    """Talks to the Daikin India cloud, which proxies the same trees."""

    timeout = 20

    def __init__(self, session: aiohttp.ClientSession, auth: CloudAuth) -> None:
        super().__init__(session)
        self.auth = auth
        # Different units don't need to wait on each other in the cloud.
        self._lock = _NullLock()

    def base_for(self, edge_id: str | None) -> str:
        if not edge_id:
            raise ValueError("Cloud requests need an edge id")
        return f"/dsiot/edges/{edge_id}"

    def _url(self) -> str:
        return f"https://{CLOUD_HOST}{MULTIREQ_PATH}"

    async def _headers(self) -> dict[str, str]:
        token = await self.auth.async_get_id_token()
        return {"Authorization": f"Bearer {token}"}

    async def _on_unauthorized(self) -> bool:
        await self.auth.async_refresh()
        return True

    async def list_edges(self) -> list[dict[str, Any]]:
        """Return the raw edge objects registered to the account."""
        responses = await self._send(
            "POST",
            {
                "requests": [
                    {
                        "op": OP_READ,
                        "to": "/dsiot/edges?filter_edges=all&mask_oldedges=1&expand=ch",
                    }
                ]
            },
        )
        if not responses:
            raise CommunicationError("Empty edge list response")
        check_rsc(responses[0], "/dsiot/edges")
        edges = responses[0].get("pc") or []
        if not isinstance(edges, list):
            raise CommunicationError("Unexpected edge list format")
        return edges


class _NullLock:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> None:
        return None
