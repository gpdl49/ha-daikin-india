"""Daikin India cloud login and token handling.

Login goes through a Daikin-hosted proxy in front of AWS Cognito. Credentials
are wrapped in an RSA-encrypted ``code`` blob built with the public key that
ships in the app. See docs/api-spec.md, "Authentication".
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from .const import ACCOUNT_HOST, APP_CODE, CLIENT_ID, CLIENT_SECRET, CLOUD_HOST, DEVICE_MODEL
from .errors import AuthError, CommunicationError

_LOGGER = logging.getLogger(__name__)

_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAm16JWI5m4/sJsZWrq99c
PJqTpOWpscSZlTEWhuctv0ZTYgOqy1BxWmfK5qdqtPKAEBwSUSdGAOdHnDWd8oxi
V78Jwce3myHFwg5ZxSQ+Q4TbwxPOagIGiYHoQJZQr/RjOVhTl8DAGlXIQKLPYX8m
YOAzCL6V9WWIeufi9t7OdjSI8nFNI1F052C40rf7adbNbnf+v98mi56LB0ZvGEX8
T6Pymr5Pefdp0TF7tD/JlJOg4LxXefNR2t4UgRJVnVy9R3xsnskhXI3p5IeCVxTZ
0QOTnKlH6baJx1rJ1rEUPpJhL63ISUoD2ut1EeHrQwSGIDfB2+7txUrEfUUj1Ast
eq3Gzb1UjP1+rWAemqwSSqPRWqU1PiNAKrbN9RdS3iHojEKwTQjzc6RjEFbGeEZ1
0rsMHiAhkR9ivDNDoxKXLmyJrGFNh2Fn02G0/XkI1lSemKSDsNEHGtAp09r1PUNU
94ivXUv6kkj4qzpAGg+Ou/TQ4nUP6FlP6TxNVqW3dhYKs2j48cf2U6Ee34LbAQAv
RuP7TTqNvIGUibw8FJdSiTXKAIrzcU/1W/QCGJWNHCLwhTfNeNiK1T1XYn1dy/3+
TIyrpilSrIalRSmhyGhz9Z6ojc9nsErlo4IfnKiK/FOjIWCHW7FaZMIdqxMJHD+S
tKvHqDvAVxfc7wVdsWzGnAECAwEAAQ==
-----END PUBLIC KEY-----
"""

_REFRESH_MARGIN = 300  # seconds before expiry to refresh
_DEFAULT_LIFETIME = 3600
_TIMEOUT = 20

_public_key: RSAPublicKey | None = None


def encrypt_blob(payload: dict[str, Any]) -> str:
    """RSA-encrypt a JSON payload the way the app builds its ``code`` field."""
    global _public_key
    if _public_key is None:
        key = serialization.load_pem_public_key(_PUBLIC_KEY_PEM)
        assert isinstance(key, RSAPublicKey)
        _public_key = key
    plaintext = json.dumps(payload, separators=(",", ":")).encode()
    return base64.b64encode(_public_key.encrypt(plaintext, padding.PKCS1v15())).decode()


def normalize_phone(phone: str) -> str:
    """Normalise to E.164, assuming India (+91) for bare 10-digit numbers."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if phone.strip().startswith("+"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    return f"+{digits}"


def _jwt_exp(token: str | None) -> float | None:
    """Return the ``exp`` claim of a JWT without verifying it."""
    if not token or token.count(".") != 2:
        return None
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except (ValueError, KeyError, TypeError):
        return None


@dataclass
class Tokens:
    """Session tokens returned by login and refresh."""

    id_token: str
    refresh_token: str
    cd_access_token: str = ""
    cd_refresh_token: str = ""
    cd_user_uuid: str = ""
    uid: str = ""
    expires_at: float = 0.0

    @classmethod
    def from_response(cls, data: dict[str, Any], previous: Tokens | None = None) -> Tokens:
        """Build tokens from a login/refresh response body."""
        id_token = data.get("id_token")
        if not id_token:
            raise AuthError(_error_message(data) or "No id_token in response")
        try:
            lifetime = int(float(data.get("cd_expiresIn") or _DEFAULT_LIFETIME))
        except (TypeError, ValueError):
            lifetime = _DEFAULT_LIFETIME
        expires_at = time.time() + lifetime
        if (jwt_exp := _jwt_exp(id_token)) is not None:
            expires_at = min(expires_at, jwt_exp)
        prev = previous or cls(id_token="", refresh_token="")
        return cls(
            id_token=id_token,
            refresh_token=data.get("refresh_token") or prev.refresh_token,
            cd_access_token=data.get("cd_accessToken") or prev.cd_access_token,
            cd_refresh_token=data.get("cd_refreshToken") or prev.cd_refresh_token,
            cd_user_uuid=data.get("cd_user_uuid") or prev.cd_user_uuid,
            uid=data.get("uid") or prev.uid,
            expires_at=expires_at,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Tokens:
        """Restore tokens saved with :meth:`as_dict`."""
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})

    def as_dict(self) -> dict[str, Any]:
        """Serialise for storage in a config entry."""
        return asdict(self)

    @property
    def needs_refresh(self) -> bool:
        """Whether the id token is expired or about to expire."""
        return time.time() >= self.expires_at - _REFRESH_MARGIN


def _error_message(data: dict[str, Any]) -> str | None:
    for key in ("message", "body", "error_description", "error"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


class CloudAuth:
    """Logs in to the Daikin India cloud and keeps the session fresh."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        install_uuid: str,
        tokens: Tokens | None = None,
        on_tokens_updated: Callable[[Tokens], None] | None = None,
    ) -> None:
        self._session = session
        self._install_uuid = install_uuid
        self.tokens = tokens
        self._on_tokens_updated = on_tokens_updated
        self._refresh_lock = asyncio.Lock()
        self._last_refresh = 0.0

    @property
    def install_uuid(self) -> str:
        """Per-installation identifier sent with every login."""
        return self._install_uuid

    async def async_login_password(self, phone: str, password: str) -> Tokens:
        """Log in with phone number and password."""
        code = encrypt_blob(
            {
                "phone_number": phone,
                "password": password,
                "model": DEVICE_MODEL,
                "app": APP_CODE,
                "timestamp": str(int(time.time() * 1000)),
            }
        )
        return await self._login({"auth_type": "PASS", "code": code})

    async def async_request_otp(self, phone: str) -> str:
        """Send an SMS one-time password; returns the OTP session string."""
        blob = encrypt_blob({"phone_number": phone})
        # The body is the bare base64 blob even though the content type says JSON.
        data = await self._post(
            f"https://{ACCOUNT_HOST}/authentication/cognito/login_otp_trigger",
            data=blob,
        )
        if str(data.get("result_cd")) != "200" or not data.get("session"):
            raise AuthError(_error_message(data) or "OTP request was rejected")
        return str(data["session"])

    async def async_login_otp(self, phone: str, otp: str, otp_session: str) -> Tokens:
        """Complete an OTP login started with :meth:`async_request_otp`."""
        code = encrypt_blob({"phone_number": phone, "sms_otp": otp})
        return await self._login({"auth_type": "OTP", "code": code, "cd_session": otp_session})

    async def _login(self, fields: dict[str, Any]) -> Tokens:
        body = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "uuid": self._install_uuid,
            **fields,
        }
        data = await self._post(f"https://{CLOUD_HOST}/premise/dsiot/cognito/login", json=body)
        self._set_tokens(Tokens.from_response(data))
        assert self.tokens is not None
        return self.tokens

    async def async_get_id_token(self) -> str:
        """Return a valid id token, refreshing it first if needed."""
        if self.tokens is None:
            raise AuthError("Not logged in")
        if self.tokens.needs_refresh:
            await self.async_refresh()
        return self.tokens.id_token

    async def async_refresh(self) -> None:
        """Refresh the session using the stored refresh tokens."""
        async with self._refresh_lock:
            if self.tokens is None:
                raise AuthError("Not logged in")
            # Another caller may have refreshed while we waited for the lock.
            if time.monotonic() - self._last_refresh < 60 and not self.tokens.needs_refresh:
                return
            body = {
                "grant_type": "refresh_token",
                "refresh_token": self.tokens.refresh_token,
                "cd_refreshToken": self.tokens.cd_refresh_token,
                "cd_user_uuid": self.tokens.cd_user_uuid,
            }
            data = await self._post(
                f"https://{CLOUD_HOST}/premise/dsiot/cognito/token",
                json=body,
                headers={"Authorization": f"Bearer {self.tokens.id_token}"},
            )
            self._set_tokens(Tokens.from_response(data, previous=self.tokens))
            self._last_refresh = time.monotonic()

    async def async_logout(self) -> None:
        """Invalidate the refresh token on the server (best effort)."""
        if self.tokens is None:
            return
        try:
            await self._post(
                f"https://{CLOUD_HOST}/premise/dsiot/cognito/logout",
                json={"token": self.tokens.refresh_token},
            )
        except (AuthError, CommunicationError) as err:
            _LOGGER.debug("Logout failed: %s", err)

    def _set_tokens(self, tokens: Tokens) -> None:
        self.tokens = tokens
        if self._on_tokens_updated:
            self._on_tokens_updated(tokens)

    async def _post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        data: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        all_headers = {"Content-Type": "application/json", **(headers or {})}
        try:
            async with asyncio.timeout(_TIMEOUT):
                async with self._session.post(
                    url, json=json, data=data, headers=all_headers
                ) as resp:
                    status = resp.status
                    text = await resp.text()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise CommunicationError(f"Request to {url} failed: {err}") from err
        try:
            body = _json_loads(text)
        except ValueError:
            body = {}
        if status in (400, 401, 403):
            raise AuthError(_error_message(body) or f"HTTP {status}")
        if status >= 400:
            raise CommunicationError(f"HTTP {status} from {url}")
        rsc = body.get("rsc")
        if rsc is not None and str(rsc) in {"401", "4001", "4003"}:
            raise AuthError(_error_message(body) or f"rsc {rsc}")
        responses = body.get("responses")
        if isinstance(responses, list) and responses and "rsc" in responses[0]:
            if str(responses[0]["rsc"]) in {"401", "4001", "4003"}:
                raise AuthError(f"rsc {responses[0]['rsc']}")
        return body


def _json_loads(text: str) -> dict[str, Any]:
    value = json.loads(text) if text else {}
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value
