"""Number entities for Daikin India room ACs."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinConfigEntry, DaikinCoordinator
from .dsiot import Mode
from .dsiot.room_ac import AUTO_OFFSET_RANGE, MODE_KEYS
from .entity import DaikinEntity, daikin_command

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the auto-mode offset for units with a relative auto setpoint."""
    async_add_entities(
        DaikinAutoOffset(c)
        for c in entry.runtime_data.coordinators
        if c.device.has(MODE_KEYS[Mode.AUTO].setpoint or "")
        and not c.device.setpoint_is_absolute(Mode.AUTO)
    )


class DaikinAutoOffset(DaikinEntity, NumberEntity):
    """Temperature offset used in auto mode (the app's LL…HH setting)."""

    _attr_translation_key = "auto_offset"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = AUTO_OFFSET_RANGE[0]
    _attr_native_max_value = AUTO_OFFSET_RANGE[1]
    _attr_native_step = 1.0
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        super().__init__(coordinator, "auto_offset")

    @property
    def available(self) -> bool:
        return super().available and self.device.mode == Mode.AUTO

    @property
    def native_value(self) -> float | None:
        return self.device.auto_offset

    @daikin_command
    async def async_set_native_value(self, value: float) -> None:
        await self.device.async_control(auto_offset=value)
