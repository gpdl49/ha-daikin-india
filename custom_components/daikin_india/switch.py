"""Feature switches for Daikin India room ACs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinConfigEntry, DaikinCoordinator
from .dsiot.room_ac import (
    K_DEW_CLEAN,
    K_EYE_AUTO_ONOFF,
    K_EYE_ENERGY_SAVER,
    K_GOOD_SLEEP,
    K_QUIET,
    K_SMELL_PROOF,
    K_STREAMER,
)
from .entity import DaikinEntity, daikin_command

PARALLEL_UPDATES = 1

# Entity key -> property key. Only created when the unit reports the property.
SWITCHES: dict[str, str] = {
    "streamer": K_STREAMER,
    "outdoor_quiet": K_QUIET,
    "dew_clean": K_DEW_CLEAN,
    "smell_proof": K_SMELL_PROOF,
    "good_sleep": K_GOOD_SLEEP,
    "intelligent_eye_energy_saver": K_EYE_ENERGY_SAVER,
    "intelligent_eye_auto_on_off": K_EYE_AUTO_ONOFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up feature switches."""
    async_add_entities(
        DaikinSwitch(coordinator, key, prop)
        for coordinator in entry.runtime_data.coordinators
        for key, prop in SWITCHES.items()
        if coordinator.device.has(prop)
    )


class DaikinSwitch(DaikinEntity, SwitchEntity):
    """Turns a unit feature on or off."""

    def __init__(self, coordinator: DaikinCoordinator, key: str, prop: str) -> None:
        super().__init__(coordinator, key)
        self.entity_description = SwitchEntityDescription(key=key, translation_key=key)
        self._prop = prop

    @property
    def is_on(self) -> bool | None:
        return self.device.flag(self._prop)

    @daikin_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.device.async_set_flag(self._prop, True)

    @daikin_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.device.async_set_flag(self._prop, False)
