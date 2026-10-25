"""Polling coordinator for one Daikin unit."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .dsiot import AuthError, CloudAuth, DaikinError, RoomAC

_LOGGER = logging.getLogger(__name__)

# The cloud relays writes to the adapter and its status copy lags the unit, so
# confirm a cloud write after a short delay instead of straight away.
CLOUD_CONFIRM_DELAY = 8.0


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
        self._confirm_unsubs: list[CALLBACK_TYPE] = []

    async def _async_update_data(self) -> None:
        try:
            await self.device.async_update()
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except DaikinError as err:
            raise UpdateFailed(str(err)) from err

    async def async_after_write(self) -> None:
        """Push the optimistic state and schedule confirming polls.

        The device holds written values over stale polls for ``write_hold``
        seconds. Locally we confirm straight away; on the cloud we wait a
        little first. Either way, one more poll just after the hold expires
        shows the real state if the unit never applied the write.
        """
        self.async_update_listeners()
        self._cancel_confirm()
        if self.cloud:
            self._schedule_confirm(CLOUD_CONFIRM_DELAY)
        else:
            await self.async_request_refresh()
        self._schedule_confirm(self.device.write_hold + 1)

    def _schedule_confirm(self, delay: float) -> None:
        async def _confirm(_now: object) -> None:
            await self.async_request_refresh()

        self._confirm_unsubs.append(async_call_later(self.hass, delay, _confirm))

    def _cancel_confirm(self) -> None:
        while self._confirm_unsubs:
            self._confirm_unsubs.pop()()

    async def async_shutdown(self) -> None:
        """Cancel pending confirmation polls."""
        self._cancel_confirm()
        await super().async_shutdown()
