"""UDP discovery of Daikin adapters on the LAN."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from dataclasses import dataclass
from urllib.parse import unquote

from .const import DISCOVERY_PAYLOAD, DISCOVERY_PORT, DISCOVERY_SOURCE_PORTS

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveredAdapter:
    """An adapter that answered the discovery broadcast."""

    host: str
    info: dict[str, str]

    @property
    def mac(self) -> str | None:
        return self.info.get("mac") or None

    @property
    def name(self) -> str:
        return unquote(self.info.get("name", "")).strip() or f"Daikin {self.host}"

    @property
    def pin_required(self) -> bool:
        return self.info.get("lpw_flag") == "1"

    @property
    def speaks_dsiot(self) -> bool:
        """Whether the adapter uses the DSIOT (GPF/DGC) protocol."""
        kind = self.info.get("type", "")
        protocol = self.info.get("protocol", "").lower()
        if kind == "GPF":
            return protocol != "rs232c"
        return protocol in ("gpf", "dgc")


def parse_reply(data: bytes) -> dict[str, str]:
    """Parse a ``k=v,k=v`` discovery reply."""
    info: dict[str, str] = {}
    for pair in data.decode("utf-8", errors="ignore").strip().split(","):
        key, sep, value = pair.partition("=")
        if sep and key and "=" not in value:
            info[key.strip()] = value.strip()
    return info


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.found: dict[str, dict[str, str]] = {}

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        info = parse_reply(data)
        if info:
            port = info.get("api_port")
            if port and not port.isdigit():
                return
            host = f"{addr[0]}:{port}" if port and port != "80" else addr[0]
            self.found[host] = info


async def async_discover(
    timeout: float = 3.0, broadcast: str = "255.255.255.255"
) -> list[DiscoveredAdapter]:
    """Broadcast a discovery probe and collect replies."""
    loop = asyncio.get_running_loop()
    transport = protocol = None
    for port in DISCOVERY_SOURCE_PORTS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("", port))
        except OSError:
            sock.close()
            continue
        sock.setblocking(False)
        transport, protocol = await loop.create_datagram_endpoint(_Protocol, sock=sock)
        break
    if transport is None or protocol is None:
        _LOGGER.warning("No free UDP port in %s for discovery", DISCOVERY_SOURCE_PORTS)
        return []
    try:
        for _ in range(3):
            with contextlib.suppress(OSError):
                transport.sendto(DISCOVERY_PAYLOAD, (broadcast, DISCOVERY_PORT))
            await asyncio.sleep(timeout / 3)
    finally:
        transport.close()
    return [DiscoveredAdapter(host, info) for host, info in protocol.found.items()]
