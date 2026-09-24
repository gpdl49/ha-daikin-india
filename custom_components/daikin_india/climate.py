"""Climate entity for Daikin India room ACs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinConfigEntry, DaikinCoordinator
from .dsiot import Mode
from .dsiot.room_ac import FAN_MODES, K_ECONO, K_POWER_CHILL
from .entity import DaikinEntity, daikin_command

PARALLEL_UPDATES = 1

HVAC_BY_MODE = {
    Mode.COOL: HVACMode.COOL,
    Mode.HEAT: HVACMode.HEAT,
    Mode.AUTO: HVACMode.AUTO,
    Mode.DRY: HVACMode.DRY,
    Mode.FAN: HVACMode.FAN_ONLY,
    # Home Assistant has no humidify mode; it is closest to dry.
    Mode.HUMIDIFY: HVACMode.DRY,
}
MODE_BY_HVAC = {
    HVACMode.COOL: Mode.COOL,
    HVACMode.HEAT: Mode.HEAT,
    HVACMode.AUTO: Mode.AUTO,
    HVACMode.DRY: Mode.DRY,
    HVACMode.FAN_ONLY: Mode.FAN,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entities."""
    async_add_entities(DaikinClimate(c) for c in entry.runtime_data.coordinators)


class DaikinClimate(DaikinEntity, ClimateEntity):
    """The main thermostat control of a room AC."""

    _attr_name = None
    _attr_translation_key = "daikin"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_precision = PRECISION_HALVES
    _attr_fan_modes = FAN_MODES

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        super().__init__(coordinator, "climate")

    @property
    def supported_features(self) -> ClimateEntityFeature:
        device = self.device
        features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if device.target_temperature is not None:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if device.has_fan_control() and device.mode != Mode.DRY:
            features |= ClimateEntityFeature.FAN_MODE
        if device.swing_options(horizontal=False):
            features |= ClimateEntityFeature.SWING_MODE
        if device.swing_options(horizontal=True):
            features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE
        if self.preset_modes:
            features |= ClimateEntityFeature.PRESET_MODE
        return features

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes = [HVACMode.OFF]
        for mode in self.device.supported_modes:
            if mode in MODE_BY_HVAC.values():
                modes.append(HVAC_BY_MODE[mode])
        return modes

    @property
    def hvac_mode(self) -> HVACMode | None:
        device = self.device
        if device.power is False:
            return HVACMode.OFF
        return HVAC_BY_MODE.get(device.mode) if device.mode else None

    @property
    def current_temperature(self) -> float | None:
        return self.device.room_temperature

    @property
    def current_humidity(self) -> float | None:
        return self.device.room_humidity

    @property
    def target_temperature(self) -> float | None:
        return self.device.target_temperature

    @property
    def min_temp(self) -> float:
        return self.device.temperature_range()[0]

    @property
    def max_temp(self) -> float:
        return self.device.temperature_range()[1]

    @property
    def fan_mode(self) -> str | None:
        return self.device.fan_mode

    @property
    def swing_modes(self) -> list[str] | None:
        return self.device.swing_options(horizontal=False) or None

    @property
    def swing_mode(self) -> str | None:
        return self.device.swing(horizontal=False)

    @property
    def swing_horizontal_modes(self) -> list[str] | None:
        return self.device.swing_options(horizontal=True) or None

    @property
    def swing_horizontal_mode(self) -> str | None:
        return self.device.swing(horizontal=True)

    @property
    def preset_modes(self) -> list[str] | None:
        presets = [PRESET_NONE]
        if self.device.has(K_ECONO):
            presets.append(PRESET_ECO)
        if self.device.has(K_POWER_CHILL):
            presets.append(PRESET_BOOST)
        return presets if len(presets) > 1 else None

    @property
    def preset_mode(self) -> str | None:
        if self.device.flag(K_POWER_CHILL):
            return PRESET_BOOST
        if self.device.flag(K_ECONO):
            return PRESET_ECO
        return PRESET_NONE

    @daikin_command
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.device.async_control(power=False)
        else:
            await self.device.async_control(power=True, mode=MODE_BY_HVAC[hvac_mode])

    @daikin_command
    async def async_set_temperature(self, **kwargs: Any) -> None:
        changes: dict[str, Any] = {"temperature": kwargs.get(ATTR_TEMPERATURE)}
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            if hvac_mode == HVACMode.OFF:
                changes["power"] = False
            else:
                changes.update(power=True, mode=MODE_BY_HVAC[hvac_mode])
        await self.device.async_control(**changes)

    @daikin_command
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self.device.async_control(fan_mode=fan_mode)

    @daikin_command
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        await self.device.async_control(swing_v=swing_mode)

    @daikin_command
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        await self.device.async_control(swing_h=swing_horizontal_mode)

    @daikin_command
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.device.async_set_preset(
            econo=preset_mode == PRESET_ECO, power_chill=preset_mode == PRESET_BOOST
        )

    @daikin_command
    async def async_turn_on(self) -> None:
        await self.device.async_control(power=True)

    @daikin_command
    async def async_turn_off(self) -> None:
        await self.device.async_control(power=False)
