"""Tests for setup and entities of a local unit."""

from __future__ import annotations

import time
from datetime import timedelta

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.switch import SERVICE_TURN_ON
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.daikin_india.const import (
    CONF_CONNECTION,
    CONF_PIN,
    CONNECTION_LOCAL,
    DOMAIN,
)
from custom_components.daikin_india.coordinator import CLOUD_CONFIRM_DELAY, DaikinCoordinator
from custom_components.daikin_india.dsiot import LocalTransport, RoomAC
from custom_components.daikin_india.dsiot.codec import flatten
from custom_components.daikin_india.dsiot.errors import AuthError, CommunicationError

CLIMATE = "climate.bedroom_ac"


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
        data={CONF_CONNECTION: CONNECTION_LOCAL, CONF_HOST: "192.0.2.10", CONF_PIN: ""},
        title="Bedroom AC",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_creates_entities(hass: HomeAssistant, fake_transport) -> None:
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get(CLIMATE)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes["temperature"] == 23.0
    assert state.attributes["current_temperature"] == 23.5
    assert state.attributes["current_humidity"] == 60
    assert state.attributes["fan_mode"] == "auto"
    assert state.attributes["preset_mode"] == "eco"
    assert HVACMode.HEAT in state.attributes["hvac_modes"]

    assert hass.states.get("sensor.bedroom_ac_outdoor_temperature").state == "35.0"
    assert hass.states.get("sensor.bedroom_ac_energy_today").state == "0.64"
    assert hass.states.get("switch.bedroom_ac_streamer").state == "off"
    assert hass.states.get("select.bedroom_ac_display_brightness").state == "high"
    assert hass.states.get("binary_sensor.bedroom_ac_filter_needs_cleaning").state == "off"

    registry = er.async_get(hass)
    assert registry.async_get(CLIMATE).unique_id == "aa:bb:cc:dd:ee:ff_climate"

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_climate_commands(hass: HomeAssistant, fake_transport) -> None:
    await _setup(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    to, pc = fake_transport.writes[-1]
    assert to == "/dsiot/edge/adr_0100.dgc_status"
    assert flatten(pc)[0]["dgc_status.e_1002.e_3001.p_02"] == "32"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_FAN_MODE: "2"},
        blocking=True,
    )
    assert flatten(fake_transport.writes[-1][1])[0]["dgc_status.e_1002.e_3001.p_09"] == "0400"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    flat = flatten(fake_transport.writes[-1][1])[0]
    assert flat["dgc_status.e_1002.e_A002.p_01"] == "00"
    assert flat["dgc_status.e_1002.e_3003.p_2D"] == "01"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.bedroom_ac_streamer"},
        blocking=True,
    )
    assert flatten(fake_transport.writes[-1][1])[0]["dgc_status.e_1002.e_3003.p_20"] == "01"


async def test_setup_retries_when_offline(hass: HomeAssistant, fake_transport) -> None:
    async def _fail(targets):
        raise CommunicationError("timeout")

    fake_transport.read = _fail
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_bad_pin_starts_reauth(hass: HomeAssistant, fake_transport) -> None:
    async def _fail(targets):
        raise AuthError("rsc 4001")

    fake_transport.read = _fail
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_write_not_reverted_by_stale_poll(hass: HomeAssistant, fake_transport) -> None:
    """The unit (the fixture) never applies the write, like a lagging cloud copy."""
    entry = await _setup(hass)
    coordinator = entry.runtime_data.coordinators[0]
    reads = fake_transport.reads

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert fake_transport.reads == reads + 1  # immediate confirming poll (local)
    assert hass.states.get(CLIMATE).state == HVACMode.OFF

    # Once the hold expires the follow-up poll shows what the unit reports.
    later = coordinator.device.write_hold + 2
    start = time.monotonic()
    coordinator.device._clock = lambda: start + later
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=later))
    await hass.async_block_till_done()
    assert fake_transport.reads == reads + 2
    assert hass.states.get(CLIMATE).state == HVACMode.COOL

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_cloud_confirm_is_delayed(hass: HomeAssistant, fake_transport) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    device = RoomAC(LocalTransport(None, "192.0.2.10"))  # type: ignore[arg-type]
    coordinator = DaikinCoordinator(hass, entry, device, "edge-1", timedelta(minutes=10), True)

    await coordinator.async_after_write()
    assert fake_transport.reads == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=CLOUD_CONFIRM_DELAY + 1))
    await hass.async_block_till_done()
    assert fake_transport.reads == 1

    await coordinator.async_shutdown()
