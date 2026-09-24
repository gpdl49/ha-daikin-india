"""Polling coordinator for one Daikin unit."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .dsiot import AuthError, CloudAuth, DaikinError, RoomAC

_LOGGER = logging.getLogger(__name__)


@dataclass
class DaikinRuntimeData:
    """Objects shared by the platforms of one config entry."""

    coordinators: list[DaikinCoordinator] = field(default_factory=list)
    auth: CloudAuth | None = None


type DaikinConfigEntry = ConfigEntry[DaikinRuntimeData]


class DaikinCoordinator(DataUpdateCoordinator[None]):
    """Polls one room AC; entities read state from ``coordinator.device``."""

    config_entry: DaikinConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: DaikinConfigEntry,
        device: RoomAC,
        unique_id: str,
        interval: timedelta,
        cloud: bool,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {unique_id}",
            update_interval=interval,
            always_update=True,
        )
        self.device = device
        self.unique_id = unique_id
        self.cloud = cloud

    async def _async_update_data(self) -> None:
        try:
            await self.device.async_update()
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except DaikinError as err:
            raise UpdateFailed(str(err)) from err

    async def async_after_write(self) -> None:
        """Push the optimistic state and schedule a confirming poll."""
        self.async_update_listeners()
        await self.async_request_refresh()
