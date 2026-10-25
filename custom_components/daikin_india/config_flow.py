"""Config flow for Daikin India."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CONNECTION,
    CONF_INSTALL_UUID,
    CONF_PHONE,
    CONF_PIN,
    CONF_TOKENS,
    CONNECTION_CLOUD,
    CONNECTION_LOCAL,
    DOMAIN,
)
from .dsiot import (
    AuthError,
    CloudAuth,
    CommunicationError,
    DaikinError,
    DiscoveredAdapter,
    LocalTransport,
    RoomAC,
    Tokens,
    UnsupportedDeviceError,
    async_discover,
    normalize_phone,
)

_LOGGER = logging.getLogger(__name__)

CONF_OTP = "otp"
CONF_ADAPTER = "adapter"
CONF_STORE_PASSWORD = "store_password"

PIN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

_HOST_RE = re.compile(
    r"^(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)(?::(\d{1,5}))?$"
)


def normalize_host(value: str) -> str | None:
    """Return ``host[:port]`` without a scheme or trailing slash, or None if invalid."""
    host = value.strip().removeprefix("http://").rstrip("/")
    match = _HOST_RE.match(host)
    if not match or (match[2] and not 0 < int(match[2]) < 65536):
        return None
    return host


class DaikinIndiaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a Daikin AC locally or through a Daikin India account."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, DiscoveredAdapter] = {}
        self._host: str | None = None
        self._phone: str | None = None
        self._otp_session: str | None = None
        self._auth: CloudAuth | None = None

    # ------------------------------------------------------------------ entry

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose how to connect."""
        return self.async_show_menu(step_id="user", menu_options=["discover", "local", "cloud"])

    # ------------------------------------------------------------------ local

    async def _async_validate_local(self, host: str, pin: str | None) -> RoomAC:
        device = RoomAC(LocalTransport(async_get_clientsession(self.hass), host, pin))
        await device.async_update()
        return device

    async def _async_local_errors(
        self, host: str, pin: str | None
    ) -> tuple[RoomAC | None, dict[str, str]]:
        try:
            return await self._async_validate_local(host, pin), {}
        except AuthError:
            return None, {"base": "invalid_pin" if pin else "pin_required"}
        except UnsupportedDeviceError:
            return None, {"base": "unsupported_device"}
        except CommunicationError:
            return None, {"base": "cannot_connect"}
        except DaikinError:
            _LOGGER.exception("Unexpected error talking to %s", host)
            return None, {"base": "unknown"}

    async def _async_create_local(
        self, device: RoomAC, host: str, pin: str | None
    ) -> ConfigFlowResult:
        data = {CONF_CONNECTION: CONNECTION_LOCAL, CONF_HOST: host, CONF_PIN: pin or ""}
        if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            entry = (
                self._get_reauth_entry()
                if self.source == SOURCE_REAUTH
                else self._get_reconfigure_entry()
            )
            # Without a MAC the unique id is the old address, so it can't be compared.
            if device.mac:
                await self.async_set_unique_id(format_mac(device.mac))
                self._abort_if_unique_id_mismatch(reason="wrong_device")
            return self.async_update_reload_and_abort(entry, data_updates=data)
        await self.async_set_unique_id(format_mac(device.mac) if device.mac else host)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return self.async_create_entry(
            title=device.name or device.model or f"Daikin {host}", data=data
        )

    async def async_step_local(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Enter an adapter address manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            pin = user_input.get(CONF_PIN) or None
            if (host := normalize_host(user_input[CONF_HOST])) is None:
                errors["base"] = "invalid_host"
            else:
                device, errors = await self._async_local_errors(host, pin)
                if device:
                    return await self._async_create_local(device, host, pin)
        return self.async_show_form(
            step_id="local",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): TextSelector(),
                        vol.Optional(CONF_PIN): PIN_SELECTOR,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Find adapters with a UDP broadcast."""
        if user_input is not None:
            adapter = self._discovered[user_input[CONF_ADAPTER]]
            self._host = adapter.host
            if adapter.pin_required:
                return await self.async_step_pin()
            device, errors = await self._async_local_errors(adapter.host, None)
            if device:
                return await self._async_create_local(device, adapter.host, None)
            if errors.get("base") == "pin_required":
                return await self.async_step_pin()
            return self.async_abort(reason=errors["base"])

        configured = {e.unique_id for e in self._async_current_entries()}
        adapters = await async_discover()
        self._discovered = {
            a.host: a
            for a in adapters
            if a.speaks_dsiot and not (a.mac and format_mac(a.mac) in configured)
        }
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")
        options = [
            SelectOptionDict(value=host, label=f"{a.name} ({host})")
            for host, a in self._discovered.items()
        ]
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADAPTER): SelectSelector(SelectSelectorConfig(options=options))}
            ),
        )

    async def async_step_pin(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the adapter's lock PIN."""
        errors: dict[str, str] = {}
        assert self._host is not None
        if user_input is not None:
            pin = user_input[CONF_PIN]
            device, errors = await self._async_local_errors(self._host, pin)
            if device:
                return await self._async_create_local(device, self._host, pin)
        return self.async_show_form(
            step_id="pin",
            data_schema=vol.Schema({vol.Required(CONF_PIN): PIN_SELECTOR}),
            description_placeholders={"host": self._host},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address or PIN of a local adapter."""
        entry = self._get_reconfigure_entry()
        if entry.data.get(CONF_CONNECTION) == CONNECTION_CLOUD:
            return self.async_abort(reason="reconfigure_cloud")
        errors: dict[str, str] = {}
        if user_input is not None:
            pin = user_input.get(CONF_PIN) or None
            if (host := normalize_host(user_input[CONF_HOST])) is None:
                errors["base"] = "invalid_host"
            else:
                device, errors = await self._async_local_errors(host, pin)
                if device:
                    return await self._async_create_local(device, host, pin)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): TextSelector(),
                        vol.Optional(CONF_PIN): PIN_SELECTOR,
                    }
                ),
                user_input or {CONF_HOST: entry.data[CONF_HOST]},
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------ cloud

    def _cloud_auth(self) -> CloudAuth:
        if self._auth is None:
            install_uuid = (
                self._get_reauth_entry().data[CONF_INSTALL_UUID]
                if self.source == SOURCE_REAUTH
                else str(uuid.uuid4())
            )
            self._auth = CloudAuth(async_get_clientsession(self.hass), install_uuid)
        return self._auth

    async def async_step_cloud(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose password or SMS login."""
        return self.async_show_menu(step_id="cloud", menu_options=["cloud_password", "cloud_otp"])

    async def async_step_cloud_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in with phone number and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            phone = normalize_phone(user_input[CONF_PHONE])
            try:
                tokens = await self._cloud_auth().async_login_password(
                    phone, user_input[CONF_PASSWORD]
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except CommunicationError:
                errors["base"] = "cannot_connect"
            else:
                password = (
                    user_input[CONF_PASSWORD] if user_input.get(CONF_STORE_PASSWORD) else None
                )
                return await self._async_create_cloud(phone, tokens, password)
        return self.async_show_form(
            step_id="cloud_password",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_PHONE): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.TEL)
                        ),
                        vol.Required(CONF_PASSWORD): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.PASSWORD)
                        ),
                        vol.Optional(CONF_STORE_PASSWORD, default=True): BooleanSelector(),
                    }
                ),
                {CONF_PHONE: self._reauth_phone() or "+91"},
            ),
            errors=errors,
        )

    async def async_step_cloud_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Request an SMS one-time password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            phone = normalize_phone(user_input[CONF_PHONE])
            try:
                self._otp_session = await self._cloud_auth().async_request_otp(phone)
            except AuthError:
                errors["base"] = "otp_rejected"
            except CommunicationError:
                errors["base"] = "cannot_connect"
            else:
                self._phone = phone
                return await self.async_step_cloud_otp_verify()
        return self.async_show_form(
            step_id="cloud_otp",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_PHONE): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.TEL)
                        )
                    }
                ),
                {CONF_PHONE: self._reauth_phone() or "+91"},
            ),
            errors=errors,
        )

    async def async_step_cloud_otp_verify(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the SMS one-time password."""
        errors: dict[str, str] = {}
        assert self._phone is not None and self._otp_session is not None
        if user_input is not None:
            try:
                tokens = await self._cloud_auth().async_login_otp(
                    self._phone, user_input[CONF_OTP].strip(), self._otp_session
                )
            except AuthError:
                errors["base"] = "invalid_otp"
            except CommunicationError:
                errors["base"] = "cannot_connect"
            else:
                return await self._async_create_cloud(self._phone, tokens)
        return self.async_show_form(
            step_id="cloud_otp_verify",
            data_schema=vol.Schema({vol.Required(CONF_OTP): TextSelector()}),
            description_placeholders={"phone": self._phone},
            errors=errors,
        )

    async def _async_create_cloud(
        self, phone: str, tokens: Tokens, password: str | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(f"cloud_{tokens.uid or phone}")
        assert self._auth is not None
        data = {
            CONF_CONNECTION: CONNECTION_CLOUD,
            CONF_PHONE: phone,
            CONF_INSTALL_UUID: self._auth.install_uuid,
            CONF_TOKENS: tokens.as_dict(),
        }
        if password:
            # Lets the integration log in again if Daikin rejects the refresh token.
            data[CONF_PASSWORD] = password
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            # Replace the data so a stale stored password doesn't survive a reauth.
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
        self._abort_if_unique_id_configured()
        # Only the last digits, so the number doesn't end up in logs that mention the title.
        return self.async_create_entry(title=f"Daikin account …{phone[-4:]}", data=data)

    def _reauth_phone(self) -> str | None:
        if self.source == SOURCE_REAUTH:
            return self._get_reauth_entry().data.get(CONF_PHONE)
        return None

    # ----------------------------------------------------------------- reauth

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle rejected credentials."""
        if entry_data.get(CONF_CONNECTION) == CONNECTION_CLOUD:
            return await self.async_step_reauth_cloud()
        self._host = entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to log in to the Daikin account again."""
        return self.async_show_menu(
            step_id="reauth_cloud", menu_options=["cloud_password", "cloud_otp"]
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new lock PIN."""
        errors: dict[str, str] = {}
        assert self._host is not None
        if user_input is not None:
            pin = user_input.get(CONF_PIN) or None
            device, errors = await self._async_local_errors(self._host, pin)
            if device:
                return await self._async_create_local(device, self._host, pin)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PIN): PIN_SELECTOR}),
            description_placeholders={"host": self._host},
            errors=errors,
        )
