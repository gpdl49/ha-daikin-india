"""Exceptions raised by the DSIOT client."""

from __future__ import annotations


class DaikinError(Exception):
    """Base error for all DSIOT client failures."""


class CommunicationError(DaikinError):
    """The adapter or cloud could not be reached, or replied with garbage."""


class AuthError(DaikinError):
    """Credentials were rejected (wrong lock PIN, expired or invalid tokens)."""


class DeviceOfflineError(DaikinError):
    """The cloud reports that the unit is not connected (rsc 5107)."""


class UnsupportedDeviceError(DaikinError):
    """The adapter does not speak DSIOT (e.g. older firmware) or is not a room AC."""


class ApiError(DaikinError):
    """The adapter or cloud returned an unexpected result code."""

    def __init__(self, message: str, rsc: int | None = None) -> None:
        super().__init__(message)
        self.rsc = rsc
