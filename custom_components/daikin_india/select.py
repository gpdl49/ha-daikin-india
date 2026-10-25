"""Select entities for Daikin India room ACs."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinConfigEntry, DaikinCoordinator
from .dsiot.room_ac import K_LED, K_VARIABLE, LED_OPTIONS, VARIABLE_MODES, VARIABLE_OPTIONS
from .entity import DaikinEntity, daikin_command

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    entities: list[SelectEntity] = []
    for coordinator in entry.runtime_data.coordinators:
        if coordinator.device.has(K_LED):
            entities.append(DaikinLedSelect(coordinator))
        if coordinator.device.has(K_VARIABLE):
            entities.append(DaikinVariableSelect(coordinator))
        if coordinator.device.vane_positions():
            entities.append(DaikinVanePositionSelect(coordinator))
    async_add_entities(entities)


class DaikinLedSelect(DaikinEntity, SelectEntity):
    """Indoor-unit display brightness."""

    _attr_translation_key = "led_brightness"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = LED_OPTIONS

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        super().__init__(coordinator, "led_brightness")

    @property
    def current_option(self) -> str | None:
        return self.device.led_brightness

    @daikin_command
    async def async_select_option(self, option: str) -> None:
        await self.device.async_set_led(option)


class DaikinVariableSelect(DaikinEntity, SelectEntity):
    """Compressor capacity limit ("Variable" on the remote), cool and dry only."""

    _attr_translation_key = "variable"
    _attr_options = VARIABLE_OPTIONS

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        super().__init__(coordinator, "variable")

    @property
    def available(self) -> bool:
        return super().available and self.device.mode in VARIABLE_MODES

    @property
    def current_option(self) -> str | None:
        return self.device.variable

    @daikin_command
    async def async_select_option(self, option: str) -> None:
        await self.device.async_set_variable(option)


class DaikinVanePositionSelect(DaikinEntity, SelectEntity):
    """Fixed vertical louver position; choosing one stops the swing."""

    _attr_translation_key = "vertical_vane_position"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        super().__init__(coordinator, "vertical_vane_position")
        self._fallback_options = coordinator.device.vane_positions()

    @property
    def available(self) -> bool:
        return super().available and bool(self.device.vane_positions())

    @property
    def options(self) -> list[str]:
        return self.device.vane_positions() or self._fallback_options

    @property
    def current_option(self) -> str | None:
        position = self.device.vane_position
        return position if position in self.options else None

    @daikin_command
    async def async_select_option(self, option: str) -> None:
        await self.device.async_control(swing_v=option)
