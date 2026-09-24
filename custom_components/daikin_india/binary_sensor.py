"""Binary sensors for Daikin India room ACs."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinConfigEntry, DaikinCoordinator
from .dsiot.room_ac import K_ERROR_FLAG, K_FILTER_SIGN
from .entity import DaikinEntity

PARALLEL_UPDATES = 0

FILTER = BinarySensorEntityDescription(
    key="filter_sign",
    translation_key="filter_sign",
    device_class=BinarySensorDeviceClass.PROBLEM,
)
ERROR = BinarySensorEntityDescription(
    key="error",
    translation_key="error",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    entities: list[DaikinBinarySensor] = []
    for coordinator in entry.runtime_data.coordinators:
        if coordinator.device.has(K_FILTER_SIGN):
            entities.append(DaikinBinarySensor(coordinator, FILTER))
        if coordinator.device.has(K_ERROR_FLAG):
            entities.append(DaikinBinarySensor(coordinator, ERROR))
    async_add_entities(entities)


class DaikinBinarySensor(DaikinEntity, BinarySensorEntity):
    """Filter-cleaning and error indicators."""

    def __init__(
        self, coordinator: DaikinCoordinator, description: BinarySensorEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        if self.entity_description.key == FILTER.key:
            return self.device.filter_sign
        return self.device.error_code is not None
