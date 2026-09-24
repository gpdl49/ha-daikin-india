"""Select entities for Daikin India room ACs."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinConfigEntry, DaikinCoordinator
from .dsiot.room_ac import K_LED, LED_OPTIONS
from .entity import DaikinEntity, daikin_command

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    async_add_entities(
        DaikinLedSelect(c) for c in entry.runtime_data.coordinators if c.device.has(K_LED)
    )


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
