"""Tests for cloud login, token refresh and cloud setup."""

from __future__ import annotations

import base64
import time

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.daikin_india.const import (
    CONF_CONNECTION,
    CONF_INSTALL_UUID,
    CONF_PHONE,
    CONF_TOKENS,
    CONNECTION_CLOUD,
    DOMAIN,
)
from custom_components.daikin_india.dsiot import CloudAuth, Tokens, normalize_phone
from custom_components.daikin_india.dsiot.cloud_auth import encrypt_blob

from .conftest import load_json

LOGIN = "https://prod.daikinacmanager.com/premise/dsiot/cognito/login"
TOKEN = "https://prod.daikinacmanager.com/premise/dsiot/cognito/token"
OTP = "https://prod-clubdaikin.daikinacmanager.com/authentication/cognito/login_otp_trigger"
MULTIREQ = "https://prod.daikinacmanager.com/dsiot/multireq"

LOGIN_RESPONSE = {
    "access_token": "at",
    "id_token": "id-1",
    "refresh_token": "rt-1",
    "uid": "user-1",
    "cd_accessToken": "cda",
    "cd_refreshToken": "cdr",
    "cd_expiresIn": 3600,
    "cd_user_uuid": "cu",
}


def test_encrypt_blob_is_rsa_4096() -> None:
    blob = encrypt_blob({"phone_number": "+910000000000"})
    assert len(base64.b64decode(blob)) == 512
    assert "\n" not in blob
    assert blob != encrypt_blob({"phone_number": "+910000000000"})  # random padding


def test_normalize_phone() -> None:
    assert normalize_phone("98765 43210") == "+919876543210"
    assert normalize_phone("+91 98765-43210") == "+919876543210"
    assert normalize_phone("919876543210") == "+919876543210"


async def test_password_login(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(LOGIN, json=LOGIN_RESPONSE)
    saved: list[Tokens] = []
    auth = CloudAuth(async_get_clientsession(hass), "uuid-1", on_tokens_updated=saved.append)
    # The password contains characters outside the base64 alphabet so it can
    # never appear by chance inside the base64-encoded RSA ciphertext.
    password = "not-in-b64!"
    tokens = await auth.async_login_password("+919876543210", password)
    assert tokens.id_token == "id-1"
    assert tokens.cd_access_token == "cda"
    assert saved == [tokens]
    body = aioclient_mock.mock_calls[0][2]
    assert body["grant_type"] == "authorization_code"
    assert body["auth_type"] == "PASS"
    assert body["uuid"] == "uuid-1"
    assert len(base64.b64decode(body["code"])) == 512
    assert password not in str(body)


async def test_login_rejected(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(LOGIN, status=401, json={"message": "Incorrect username or password."})
    auth = CloudAuth(async_get_clientsession(hass), "uuid-1")
    try:
        await auth.async_login_password("+919876543210", "pw")
    except Exception as err:
        assert "Incorrect" in str(err)
    else:
        raise AssertionError("expected AuthError")


async def test_otp_login(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(OTP, json={"result_cd": "200", "session": "s-1"})
    aioclient_mock.post(LOGIN, json=LOGIN_RESPONSE)
    auth = CloudAuth(async_get_clientsession(hass), "uuid-1")
    session = await auth.async_request_otp("+919876543210")
    assert session == "s-1"
    # The trigger body is the bare base64 blob.
    assert isinstance(aioclient_mock.mock_calls[0][2], str)
    await auth.async_login_otp("+919876543210", "123456", session)
    body = aioclient_mock.mock_calls[1][2]
    assert body["auth_type"] == "OTP"
    assert body["cd_session"] == "s-1"


async def test_refresh_when_expired(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(TOKEN, json={**LOGIN_RESPONSE, "id_token": "id-2", "refresh_token": ""})
    old = Tokens(
        id_token="id-1",
        refresh_token="rt-1",
        cd_refresh_token="cdr",
        cd_user_uuid="cu",
        expires_at=time.time() - 10,
    )
    auth = CloudAuth(async_get_clientsession(hass), "uuid-1", old)
    assert await auth.async_get_id_token() == "id-2"
    assert auth.tokens.refresh_token == "rt-1"  # kept when the response omits it
    body = aioclient_mock.mock_calls[0][2]
    assert body == {
        "grant_type": "refresh_token",
        "refresh_token": "rt-1",
        "cd_refreshToken": "cdr",
        "cd_user_uuid": "cu",
    }


async def test_cloud_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    status = load_json("status_local.json")["responses"]
    indoor = status[0]["pc"]
    edges = {
        "responses": [
            {
                "fr": "/dsiot/edges",
                "rsc": 2000,
                "pc": [
                    {
                        "ri": "edge-1",
                        "cnst": 1,
                        "pch": [status[2]["pc"], status[3]["pc"]],
                        "ch": [{"pch": [indoor]}],
                    }
                ],
            }
        ]
    }
    # First call lists edges, later calls poll status.
    responses = iter([edges, {"responses": status}])

    async def _reply(*args, **kwargs):
        return AiohttpClientMockResponse("POST", MULTIREQ, json=next(responses))

    aioclient_mock.post(MULTIREQ, side_effect=_reply)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="cloud_user-1",
        data={
            CONF_CONNECTION: CONNECTION_CLOUD,
            CONF_PHONE: "+919876543210",
            CONF_INSTALL_UUID: "uuid-1",
            CONF_TOKENS: Tokens(id_token="id-1", refresh_token="rt", expires_at=9e9).as_dict(),
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("climate.bedroom_ac").state == "cool"
    poll = aioclient_mock.mock_calls[1]
    assert poll[3]["Authorization"] == "Bearer id-1"
    assert poll[2]["requests"][0]["to"] == "/dsiot/edges/edge-1/adr_0100.dgc_status?filter=pv,md"
