"""Tests for the config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.daikin_india.config_flow import normalize_host
from custom_components.daikin_india.const import (
    CONF_CONNECTION,
    CONF_INSTALL_UUID,
    CONF_PHONE,
    CONF_PIN,
    CONF_TOKENS,
    CONNECTION_CLOUD,
    CONNECTION_LOCAL,
    DOMAIN,
)
from custom_components.daikin_india.dsiot import DiscoveredAdapter, Tokens
from custom_components.daikin_india.dsiot.errors import AuthError, CommunicationError

SETUP = "custom_components.daikin_india.async_setup_entry"


async def _start(hass: HomeAssistant, option: str):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": option}
    )


async def test_local_flow(hass: HomeAssistant, fake_transport) -> None:
    result = await _start(hass, "local")
    assert result["step_id"] == "local"
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.10"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom AC"
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert result["data"] == {
        CONF_CONNECTION: CONNECTION_LOCAL,
        CONF_HOST: "192.0.2.10",
        CONF_PIN: "",
    }


async def test_local_flow_errors(hass: HomeAssistant, fake_transport) -> None:
    result = await _start(hass, "local")
    for error, key, pin in (
        (AuthError("x"), "pin_required", None),
        (AuthError("x"), "invalid_pin", "1234"),
        (CommunicationError("x"), "cannot_connect", None),
    ):
        fake_transport.read = AsyncMock(side_effect=error)
        data = {CONF_HOST: "192.0.2.10"} | ({CONF_PIN: pin} if pin else {})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": key}


async def test_local_flow_already_configured(hass: HomeAssistant, fake_transport) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="aa:bb:cc:dd:ee:ff", data={}).add_to_hass(hass)
    result = await _start(hass, "local")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.10"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_with_pin(hass: HomeAssistant, fake_transport) -> None:
    adapter = DiscoveredAdapter(
        "192.0.2.20",
        {"type": "GPF", "cdev": "RA", "mac": "112233445566", "name": "Hall", "lpw_flag": "1"},
    )
    with patch("custom_components.daikin_india.config_flow.async_discover", return_value=[adapter]):
        result = await _start(hass, "discover")
    assert result["step_id"] == "discover"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"adapter": "192.0.2.20"}
    )
    assert result["step_id"] == "pin"
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: "4321"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PIN] == "4321"
    assert result["data"][CONF_HOST] == "192.0.2.20"


async def test_discovery_none_found(hass: HomeAssistant) -> None:
    with patch("custom_components.daikin_india.config_flow.async_discover", return_value=[]):
        result = await _start(hass, "discover")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


TOKENS = Tokens(id_token="id", refresh_token="rt", uid="user-1", expires_at=9e9)


async def test_cloud_password_flow(hass: HomeAssistant) -> None:
    result = await _start(hass, "cloud")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cloud_password"}
    )
    with patch(
        "custom_components.daikin_india.config_flow.CloudAuth.async_login_password",
        side_effect=AuthError("bad"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PHONE: "98765 43210", CONF_PASSWORD: "x"}
        )
    assert result["errors"] == {"base": "invalid_auth"}
    with (
        patch(
            "custom_components.daikin_india.config_flow.CloudAuth.async_login_password",
            return_value=TOKENS,
        ) as login,
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PHONE: "98765 43210", CONF_PASSWORD: "secret"}
        )
    login.assert_awaited_once_with("+919876543210", "secret")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "cloud_user-1"
    assert result["data"][CONF_CONNECTION] == CONNECTION_CLOUD
    assert result["data"][CONF_TOKENS]["id_token"] == "id"
    assert result["data"][CONF_PASSWORD] == "secret"


async def test_cloud_password_flow_without_storing(hass: HomeAssistant) -> None:
    result = await _start(hass, "cloud")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cloud_password"}
    )
    with (
        patch(
            "custom_components.daikin_india.config_flow.CloudAuth.async_login_password",
            return_value=TOKENS,
        ),
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PHONE: "98765 43210", CONF_PASSWORD: "secret", "store_password": False},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_PASSWORD not in result["data"]


async def test_cloud_otp_flow(hass: HomeAssistant) -> None:
    result = await _start(hass, "cloud")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cloud_otp"}
    )
    with patch(
        "custom_components.daikin_india.config_flow.CloudAuth.async_request_otp",
        return_value="sess",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PHONE: "+919876543210"}
        )
    assert result["step_id"] == "cloud_otp_verify"
    with (
        patch(
            "custom_components.daikin_india.config_flow.CloudAuth.async_login_otp",
            return_value=TOKENS,
        ) as login,
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"otp": " 123456 "}
        )
    login.assert_awaited_once_with("+919876543210", "123456", "sess")
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_local_reauth(hass: HomeAssistant, fake_transport) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
        data={CONF_CONNECTION: CONNECTION_LOCAL, CONF_HOST: "192.0.2.10", CONF_PIN: "1111"},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: "2222"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PIN] == "2222"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("192.0.2.10", "192.0.2.10"),
        (" http://192.0.2.10/ ", "192.0.2.10"),
        ("ac.local:8080", "ac.local:8080"),
        ("[fe80::1]", "[fe80::1]"),
        ("192.0.2.10/dsiot", None),
        ("user@192.0.2.10", None),
        ("192.0.2.10:99999", None),
        ("https://192.0.2.10", None),
        ("", None),
    ],
)
def test_normalize_host(value: str, expected: str | None) -> None:
    assert normalize_host(value) == expected


async def test_local_flow_invalid_host(hass: HomeAssistant, fake_transport) -> None:
    result = await _start(hass, "local")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.10/x?y"}
    )
    assert result["errors"] == {"base": "invalid_host"}
    assert fake_transport.reads == 0


def _local_entry(hass: HomeAssistant, unique_id: str = "aa:bb:cc:dd:ee:ff") -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data={CONF_CONNECTION: CONNECTION_LOCAL, CONF_HOST: "192.0.2.10", CONF_PIN: ""},
    )
    entry.add_to_hass(hass)
    return entry


async def test_reconfigure(hass: HomeAssistant, fake_transport) -> None:
    entry = _local_entry(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.11", CONF_PIN: "1234"}
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.0.2.11"
    assert entry.data[CONF_PIN] == "1234"


async def test_reconfigure_wrong_device(hass: HomeAssistant, fake_transport) -> None:
    entry = _local_entry(hass, unique_id="11:22:33:44:55:66")
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.11"}
    )
    assert result["reason"] == "wrong_device"
    assert entry.data[CONF_HOST] == "192.0.2.10"


async def test_reconfigure_without_mac(hass: HomeAssistant, fake_transport, status) -> None:
    status["responses"][2]["pc"]["pch"] = []  # no adp_i.mac
    entry = _local_entry(hass, unique_id="192.0.2.10")
    result = await entry.start_reconfigure_flow(hass)
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.11"}
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.0.2.11"


async def test_cloud_title_hides_phone(hass: HomeAssistant) -> None:
    result = await _start(hass, "cloud")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cloud_password"}
    )
    with (
        patch(
            "custom_components.daikin_india.config_flow.CloudAuth.async_login_password",
            return_value=TOKENS,
        ),
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PHONE: "+919876543210", CONF_PASSWORD: "secret"}
        )
    assert "9876543210" not in result["title"]
    assert result["data"][CONF_PASSWORD] == "secret"  # stored by default


async def test_cloud_reauth(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="cloud_user-1",
        data={
            CONF_CONNECTION: CONNECTION_CLOUD,
            CONF_PHONE: "+919876543210",
            CONF_INSTALL_UUID: "uuid-1",
            CONF_TOKENS: TOKENS.as_dict(),
            CONF_PASSWORD: "old",
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reauth_cloud"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cloud_password"}
    )
    other = Tokens(id_token="x", refresh_token="y", uid="user-2")
    with patch(
        "custom_components.daikin_india.config_flow.CloudAuth.async_login_password",
        return_value=other,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PHONE: "+919876543210", CONF_PASSWORD: "secret"}
        )
    assert result["reason"] == "wrong_account"

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cloud_password"}
    )
    with (
        patch(
            "custom_components.daikin_india.config_flow.CloudAuth.async_login_password",
            return_value=TOKENS,
        ),
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PHONE: "+919876543210", CONF_PASSWORD: "new", "store_password": False},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert CONF_PASSWORD not in entry.data
    assert entry.data[CONF_INSTALL_UUID] == "uuid-1"
