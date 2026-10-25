"""Tests for the room AC model."""

from __future__ import annotations

import pytest

from custom_components.daikin_india.dsiot import CloudTransport, Mode, RoomAC
from custom_components.daikin_india.dsiot.codec import flatten
from custom_components.daikin_india.dsiot.errors import ApiError
from custom_components.daikin_india.dsiot.room_ac import (
    CLOUD_WRITE_HOLD,
    K_ECONO,
    K_EYE_AUTO_ONOFF,
    K_MODE,
    K_POWER,
    K_POWER_CHILL,
    K_QUIET,
    K_STREAMER,
    parse_edge,
)

from .conftest import FakeTransport


class _Local(FakeTransport):
    def base_for(self, edge_id):
        return "/dsiot/edge"


@pytest.fixture
async def device(status) -> RoomAC:
    ac = RoomAC(_Local(status))  # type: ignore[arg-type]
    await ac.async_update()
    return ac


def _written(transport: _Local) -> dict[str, str]:
    _to, pc = transport.writes[-1]
    return flatten(pc)[0]


async def test_decode(device: RoomAC) -> None:
    assert device.is_room_ac
    assert device.power is True
    assert device.mode == Mode.COOL
    assert device.target_temperature == 23.0
    assert device.temperature_range() == (18.0, 32.0)
    assert device.fan_mode == "auto"
    assert device.swing(horizontal=False) == "swing"
    assert device.swing(horizontal=True) == "stop"
    assert device.room_temperature == 23.5
    assert device.room_humidity == 60
    assert device.outdoor_temperature == 35.0
    assert device.compressor_frequency == 58
    assert device.energy_today == 0.64
    assert device.runtime_today == 95
    assert device.mac == "AABBCCDDEEFF"
    assert device.name == "Bedroom AC"
    assert device.model == "FTKF50UV16V"
    assert device.firmware == "3.10.0"
    assert device.wifi_rssi == -58
    assert device.error_code is None
    assert device.flag(K_ECONO) is True
    assert device.led_brightness == "high"
    assert device.auto_offset == 0.0


async def test_capabilities(device: RoomAC) -> None:
    assert device.supported_modes == [Mode.FAN, Mode.HEAT, Mode.COOL, Mode.AUTO, Mode.DRY]
    assert device.swing_options(horizontal=False) == [
        "position_1",
        "position_2",
        "position_3",
        "position_4",
        "position_5",
        "swing",
        "auto",
    ]
    assert device.swing_options(horizontal=True) == ["stop", "swing", "auto"]


async def test_set_temperature_rewrites_mode_state(device: RoomAC) -> None:
    await device.async_control(temperature=24.5)
    to, _ = device.transport.writes[-1]
    assert to == "/dsiot/edge/adr_0100.dgc_status"
    assert _written(device.transport) == {
        "dgc_status.e_1002.e_A002.p_01": "01",
        "dgc_status.e_1002.e_3001.p_01": "0200",
        "dgc_status.e_1002.e_3001.p_02": "31",
        "dgc_status.e_1002.e_3001.p_09": "0A00",
        "dgc_status.e_1002.e_3001.p_05": "0F0000",
        "dgc_status.e_1002.e_3001.p_06": "000000",
        "dgc_status.e_1002.e_3003.p_2D": "02",
    }
    assert device.target_temperature == 24.5


async def test_temperature_is_clamped(device: RoomAC) -> None:
    await device.async_control(temperature=40)
    assert _written(device.transport)["dgc_status.e_1002.e_3001.p_02"] == "40"


async def test_power_transitions(device: RoomAC) -> None:
    await device.async_control(power=False)
    flat = _written(device.transport)
    assert flat["dgc_status.e_1002.e_A002.p_01"] == "00"
    assert flat["dgc_status.e_1002.e_3003.p_2D"] == "01"
    await device.async_control(power=True)
    flat = _written(device.transport)
    assert flat["dgc_status.e_1002.e_A002.p_01"] == "01"
    assert flat["dgc_status.e_1002.e_3003.p_2D"] == "00"


async def test_mode_change_uses_new_mode_keys(device: RoomAC) -> None:
    await device.async_control(mode=Mode.HEAT, fan_mode="3")
    flat = _written(device.transport)
    assert flat["dgc_status.e_1002.e_3001.p_01"] == "0100"
    assert flat["dgc_status.e_1002.e_3001.p_03"] == "2c"
    assert flat["dgc_status.e_1002.e_3001.p_0A"] == "0500"
    assert flat["dgc_status.e_1002.e_3001.p_07"] == "0F0000"
    assert "dgc_status.e_1002.e_3001.p_02" not in flat


async def test_dry_forces_auto_fan(device: RoomAC) -> None:
    await device.async_control(mode=Mode.DRY, fan_mode="5")
    flat = _written(device.transport)
    assert flat["dgc_status.e_1002.e_3001.p_01"] == "0500"
    assert flat["dgc_status.e_1002.e_3001.p_27"] == "0A00"


async def test_swing_and_auto_offset(device: RoomAC) -> None:
    await device.async_control(swing_v="position_3", swing_h="swing")
    flat = _written(device.transport)
    assert flat["dgc_status.e_1002.e_3001.p_05"] == "030000"
    assert flat["dgc_status.e_1002.e_3001.p_06"] == "0F0000"
    await device.async_control(mode=Mode.AUTO, auto_offset=-1)
    flat = _written(device.transport)
    assert flat["dgc_status.e_1002.e_3001.p_1D"] == "FE"


async def test_flags(device: RoomAC) -> None:
    await device.async_set_flag(K_STREAMER, True)
    assert _written(device.transport)[K_STREAMER] == "01"
    await device.async_set_flag(K_QUIET, True)
    to, pc = device.transport.writes[-1]
    assert to == "/dsiot/edge/adr_0200.dgc_status"
    assert flatten(pc)[0] == {K_QUIET: "01"}


async def test_power_chill_preset_clears_econo_and_quiet(device: RoomAC) -> None:
    await device.async_set_preset(econo=False, power_chill=True)
    indoor, outdoor = device.transport.writes[-2:]
    assert flatten(indoor[1])[0][K_ECONO] == "00"
    assert flatten(outdoor[1])[0] == {K_POWER_CHILL: "01", K_QUIET: "00"}


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(device: RoomAC) -> _Clock:
    clock = _Clock()
    device._clock = clock
    return clock


async def test_write_survives_stale_poll(device: RoomAC, clock: _Clock) -> None:
    # The unit is cooling; the user switches it off, but the confirming poll
    # still reports it on (the cloud has not caught up yet).
    await device.async_control(power=False)
    clock.now += 5
    await device.async_update()
    assert device.power is False
    assert device.mode == Mode.COOL
    # The hold expires without the unit ever reporting off: show the truth.
    clock.now += device.write_hold
    await device.async_update()
    assert device.power is True


async def test_confirmed_write_stops_holding(device: RoomAC, status, clock: _Clock) -> None:
    await device.async_control(power=False)
    _set_indoor(status, K_POWER, "00")
    await device.async_update()
    assert device.power is False
    # Later, the unit is switched on from the remote; that must show at once.
    _set_indoor(status, K_POWER, "01")
    clock.now += 1
    await device.async_update()
    assert device.power is True


async def test_mode_and_flag_writes_are_held(device: RoomAC, clock: _Clock) -> None:
    await device.async_control(power=True, mode=Mode.HEAT)
    await device.async_set_flag(K_EYE_AUTO_ONOFF, True)
    await device.async_update()
    assert device.mode == Mode.HEAT
    assert device.flag(K_EYE_AUTO_ONOFF) is True
    # A later write rebuilt from state keeps the held mode instead of the stale one.
    await device.async_set_flag(K_STREAMER, True)
    assert _written(device.transport)[K_MODE] == "0100"


async def test_failed_write_drops_hold(device: RoomAC, clock: _Clock) -> None:
    await device.async_control(power=False)

    async def _reject(to, pc):
        raise ApiError("rejected", 4000)

    device.transport.write = _reject  # type: ignore[method-assign]
    with pytest.raises(ApiError):
        await device.async_control(power=False)
    await device.async_update()
    assert device.power is True


def test_cloud_holds_longer() -> None:
    transport = CloudTransport.__new__(CloudTransport)
    assert RoomAC(transport, "edge-1").write_hold == CLOUD_WRITE_HOLD


def _set_indoor(status, key: str, value: str) -> None:
    node = status["responses"][0]["pc"]
    for part in key.split(".")[1:]:
        node = next(child for child in node["pch"] if child["pn"] == part)
    node["pv"] = value


def test_modes_09_0a_read_as_cool_heat(status) -> None:
    ac = RoomAC(_Local(status))  # type: ignore[arg-type]
    ac.values = {"dgc_status.e_1002.e_3001.p_01": "0900", "dgc_status.e_1002.e_3001.p_02": "30"}
    assert ac.mode == Mode.COOL
    assert ac.target_temperature == 24.0
    # The app never writes 0x09/0x0A back.
    assert "dgc_status.e_1002.e_3001.p_01" not in ac.build_control()


def test_parse_edge() -> None:
    ri, connected, values = parse_edge(
        {
            "ri": "edge-1",
            "cnst": 1,
            "pch": [{"pn": "adp_i", "pch": [{"pn": "mac", "pv": "001122334455"}]}],
            "ch": [
                {
                    "pch": [
                        {
                            "pn": "dgc_status",
                            "pch": [
                                {
                                    "pn": "e_1002",
                                    "pch": [{"pn": "e_A002", "pch": [{"pn": "p_01", "pv": "00"}]}],
                                }
                            ],
                        }
                    ]
                }
            ],
        }
    )
    assert ri == "edge-1"
    assert connected
    assert values == {"adp_i.mac": "001122334455", "dgc_status.e_1002.e_A002.p_01": "00"}
