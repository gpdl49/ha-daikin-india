"""Diagnostics for Daikin India."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_INSTALL_UUID, CONF_PHONE, CONF_PIN, CONF_TOKENS
from .coordinator import DaikinConfigEntry

TO_REDACT = {
    CONF_PIN,
    CONF_PHONE,
    CONF_TOKENS,
    CONF_INSTALL_UUID,
    "host",
    "unique_id",
    "adp_i.mac",
    "adp_i.ssid",
    "adp_i.edid",
    "adp_d.name",
    "adp_d.location",
    "edge_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DaikinConfigEntry
) -> dict[str, Any]:
    """Return raw property trees so unknown units can be mapped."""
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "devices": [
            async_redact_data(
                {
                    "edge_id": c.device.edge_id,
                    "cloud": c.cloud,
                    "last_update_success": c.last_update_success,
                    "values": c.device.values,
                    "meta": c.device.meta,
                },
                TO_REDACT,
            )
            for c in entry.runtime_data.coordinators
        ],
    }
