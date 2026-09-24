"""The Daikin India integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CLOUD_SCAN_INTERVAL,
    CONF_CONNECTION,
    CONF_INSTALL_UUID,
    CONF_PIN,
    CONF_TOKENS,
    CONNECTION_CLOUD,
    DOMAIN,
    LOCAL_SCAN_INTERVAL,
)
from .coordinator import DaikinConfigEntry, DaikinCoordinator, DaikinRuntimeData
from .dsiot import (
    AuthError,
    CloudAuth,
    CloudTransport,
    DaikinError,
    LocalTransport,
    RoomAC,
    Tokens,
    parse_edge,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: DaikinConfigEntry) -> bool:
    """Set up Daikin India from a config entry."""
    if entry.data.get(CONF_CONNECTION) == CONNECTION_CLOUD:
        runtime = await _async_setup_cloud(hass, entry)
    else:
        runtime = await _async_setup_local(hass, entry)
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_setup_local(hass: HomeAssistant, entry: DaikinConfigEntry) -> DaikinRuntimeData:
    transport = LocalTransport(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data.get(CONF_PIN)
    )
    device = RoomAC(transport)
    assert entry.unique_id is not None
    coordinator = DaikinCoordinator(
        hass, entry, device, entry.unique_id, LOCAL_SCAN_INTERVAL, cloud=False
    )
    await coordinator.async_config_entry_first_refresh()
    return DaikinRuntimeData(coordinators=[coordinator])


async def _async_setup_cloud(hass: HomeAssistant, entry: DaikinConfigEntry) -> DaikinRuntimeData:
    @callback
    def _save_tokens(tokens: Tokens) -> None:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_TOKENS: tokens.as_dict()}
        )

    session = async_get_clientsession(hass)
    auth = CloudAuth(
        session,
        entry.data[CONF_INSTALL_UUID],
        Tokens.from_dict(entry.data[CONF_TOKENS]),
        on_tokens_updated=_save_tokens,
    )
    transport = CloudTransport(session, auth)
    try:
        edges = await transport.list_edges()
    except AuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except DaikinError as err:
        raise ConfigEntryNotReady(str(err)) from err

    # Units already set up locally are skipped so they don't appear twice.
    local_ids = {
        other.unique_id
        for other in hass.config_entries.async_entries(DOMAIN)
        if other.data.get(CONF_CONNECTION) != CONNECTION_CLOUD
    }
    runtime = DaikinRuntimeData(auth=auth)
    for edge in edges:
        ri, _connected, values = parse_edge(edge)
        if not ri:
            continue
        device = RoomAC(transport, edge_id=ri, initial=values)
        if values and not device.is_room_ac:
            _LOGGER.debug("Skipping edge %s: not a room air conditioner", ri)
            continue
        unique_id = format_mac(device.mac) if device.mac else ri
        if unique_id in local_ids:
            _LOGGER.debug("Skipping edge %s: already configured locally", ri)
            continue
        coordinator = DaikinCoordinator(
            hass, entry, device, unique_id, CLOUD_SCAN_INTERVAL, cloud=True
        )
        # An offline unit shouldn't block the rest of the account.
        await coordinator.async_refresh()
        if isinstance(coordinator.last_exception, ConfigEntryAuthFailed):
            raise coordinator.last_exception
        runtime.coordinators.append(coordinator)
    return runtime


async def async_unload_entry(hass: HomeAssistant, entry: DaikinConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
