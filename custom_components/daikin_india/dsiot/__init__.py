"""Async client for the Daikin DSIOT protocol used by Daikin India adapters."""

from .cloud_auth import CloudAuth, Tokens, normalize_phone
from .discovery import DiscoveredAdapter, async_discover
from .errors import (
    ApiError,
    AuthError,
    CommunicationError,
    DaikinError,
    DeviceOfflineError,
    UnsupportedDeviceError,
)
from .room_ac import Mode, RoomAC, parse_edge
from .transport import CloudTransport, LocalTransport, Transport

__all__ = [
    "ApiError",
    "AuthError",
    "CloudAuth",
    "CloudTransport",
    "CommunicationError",
    "DaikinError",
    "DeviceOfflineError",
    "DiscoveredAdapter",
    "LocalTransport",
    "Mode",
    "RoomAC",
    "Tokens",
    "Transport",
    "UnsupportedDeviceError",
    "async_discover",
    "normalize_phone",
    "parse_edge",
]
