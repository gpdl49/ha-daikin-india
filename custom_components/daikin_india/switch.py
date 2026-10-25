"""Feature switches for Daikin India room ACs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
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


@dataclass(frozen=True, kw_only=True)
class DaikinSwitchDescription(SwitchEntityDescription):
    """Describes a feature switch; created only when the unit reports ``prop``."""

    prop: str


SWITCHES: tuple[DaikinSwitchDescription, ...] = (
    DaikinSwitchDescription(key="streamer", prop=K_STREAMER),
    DaikinSwitchDescription(key="outdoor_quiet", prop=K_QUIET),
    DaikinSwitchDescription(key="good_sleep", prop=K_GOOD_SLEEP),
    DaikinSwitchDescription(
        key="dew_clean", prop=K_DEW_CLEAN, entity_category=EntityCategory.CONFIG
    ),
    DaikinSwitchDescription(
        key="smell_proof", prop=K_SMELL_PROOF, entity_category=EntityCategory.CONFIG
    ),
    DaikinSwitchDescription(
        key="intelligent_eye_energy_saver",
        prop=K_EYE_ENERGY_SAVER,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    DaikinSwitchDescription(
        key="intelligent_eye_auto_on_off",
        prop=K_EYE_AUTO_ONOFF,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up feature switches."""
    async_add_entities(
        DaikinSwitch(coordinator, description)
        for coordinator in entry.runtime_data.coordinators
        for description in SWITCHES
        if coordinator.device.has(description.prop)
    )


class DaikinSwitch(DaikinEntity, SwitchEntity):
    """Turns a unit feature on or off."""

    entity_description: DaikinSwitchDescription

    def __init__(
        self, coordinator: DaikinCoordinator, description: DaikinSwitchDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def is_on(self) -> bool | None:
        return self.device.flag(self.entity_description.prop)

    @daikin_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.device.async_set_flag(self.entity_description.prop, True)

    @daikin_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.device.async_set_flag(self.entity_description.prop, False)
