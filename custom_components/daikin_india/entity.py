"""Base entity for Daikin India."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DaikinCoordinator
from .dsiot import AuthError, DaikinError, RoomAC


class DaikinEntity(CoordinatorEntity[DaikinCoordinator]):
    """Entity bound to one room AC."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DaikinCoordinator, key: str) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{coordinator.unique_id}_{key}"
        connections = {(CONNECTION_NETWORK_MAC, format_mac(device.mac))} if device.mac else set()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            connections=connections,
            manufacturer="Daikin",
            model=device.model,
            name=device.name or device.model or "Daikin AC",
            sw_version=device.firmware,
        )

    @property
    def device(self) -> RoomAC:
        return self.coordinator.device


def daikin_command[E: DaikinEntity, **P](
    func: Callable[Concatenate[E, P], Awaitable[Any]],
) -> Callable[Concatenate[E, P], Coroutine[Any, Any, None]]:
    """Translate library errors and refresh after a write."""

    @wraps(func)
    async def wrapper(self: E, *args: P.args, **kwargs: P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except AuthError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except DaikinError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_after_write()

    return wrapper
