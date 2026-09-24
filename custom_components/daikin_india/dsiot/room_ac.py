"""Room air conditioner model on top of the DSIOT property tree.

Key names and encodings follow docs/api-spec.md ("Room AC (Ra) DSIOT property
map"). Writes mirror what the app sends: the current mode's power, mode,
setpoint, fan and air direction are always rewritten together, plus the
power-transition marker ``e_3003.p_2D``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import unquote

from .codec import ascii_reversed, build_tree, flatten, le_int, le_uint, md_int, to_le_hex
from .errors import UnsupportedDeviceError
from .transport import Transport, check_rsc

_LOGGER = logging.getLogger(__name__)

INDOOR = "adr_0100.dgc_status"
OUTDOOR = "adr_0200.dgc_status"

_OP = "dgc_status.e_1002.e_3001."
_FEAT = "dgc_status.e_1002.e_3003."
_OUT = "dgc_status.e_1003."

K_POWER = "dgc_status.e_1002.e_A002.p_01"
K_MODE = _OP + "p_01"
K_POWER_CHANGE = _FEAT + "p_2D"
K_ROOM_TEMP = "dgc_status.e_1002.e_A00B.p_06"
K_ROOM_TEMP_LEGACY = "dgc_status.e_1002.e_A00B.p_01"
K_ROOM_HUMIDITY = "dgc_status.e_1002.e_A00B.p_02"
K_OUTDOOR_TEMP = _OUT + "e_A00D.p_01"
K_COMPRESSOR_HZ = _OUT + "e_2006.p_04"
K_MODEL = "dgc_status.e_1002.e_A001.p_01"
K_MODEL_TYPE = "dgc_status.e_1002.e_A001.p_07"
K_FILTER_SIGN = _OP + "p_15"
K_ERROR_FLAG = _FEAT + "p_30"
K_ERROR_CODE = _FEAT + "p_31"

K_ECONO = _FEAT + "p_24"
K_STREAMER = _FEAT + "p_20"
K_GOOD_SLEEP = _FEAT + "p_1E"
K_GOOD_SLEEP_SHIFT = _FEAT + "p_BA"
K_GOOD_SLEEP_TIMER = _FEAT + "p_BB"
K_SMELL_PROOF = _FEAT + "p_70"
K_DEW_CLEAN = _FEAT + "p_B2"
K_EYE_ENERGY_SAVER = _FEAT + "p_6E"
K_EYE_AUTO_ONOFF = _FEAT + "p_6F"
K_LED = _FEAT + "p_BC"
K_QUIET = _OUT + "e_3002.p_3D"
K_POWER_CHILL = _OUT + "e_3002.p_44"

K_WEEK_ENERGY = "week_power.datas"
K_TODAY_RUNTIME = "week_power.today_runtime"


class Mode(StrEnum):
    """Operation modes (``e_3001.p_01``)."""

    FAN = "fan"
    HEAT = "heat"
    COOL = "cool"
    AUTO = "auto"
    DRY = "dry"
    HUMIDIFY = "humidify"


# Wire value -> mode. 0x09/0x0A are cool/heat-family states the app reads as
# cool/heat but never writes.
_MODE_BY_VALUE = {
    0: Mode.FAN,
    1: Mode.HEAT,
    2: Mode.COOL,
    3: Mode.AUTO,
    5: Mode.DRY,
    8: Mode.HUMIDIFY,
    9: Mode.COOL,
    10: Mode.HEAT,
}
_VALUE_BY_MODE = {
    Mode.FAN: 0,
    Mode.HEAT: 1,
    Mode.COOL: 2,
    Mode.AUTO: 3,
    Mode.DRY: 5,
    Mode.HUMIDIFY: 8,
}


@dataclass(frozen=True)
class ModeKeys:
    """Per-mode property keys (None when the mode has no such setting)."""

    setpoint: str | None
    fan: str
    swing_v: str
    swing_h: str


MODE_KEYS = {
    Mode.COOL: ModeKeys(_OP + "p_02", _OP + "p_09", _OP + "p_05", _OP + "p_06"),
    Mode.HEAT: ModeKeys(_OP + "p_03", _OP + "p_0A", _OP + "p_07", _OP + "p_08"),
    Mode.AUTO: ModeKeys(_OP + "p_1D", _OP + "p_26", _OP + "p_20", _OP + "p_21"),
    Mode.DRY: ModeKeys(None, _OP + "p_27", _OP + "p_22", _OP + "p_23"),
    Mode.FAN: ModeKeys(None, _OP + "p_28", _OP + "p_24", _OP + "p_25"),
    Mode.HUMIDIFY: ModeKeys(None, _OP + "p_2B", _OP + "p_29", _OP + "p_2A"),
}

FAN_AUTO = "auto"
FAN_QUIET = "quiet"
FAN_LEVELS = ["1", "2", "3", "4", "5"]
FAN_MODES = [FAN_AUTO, FAN_QUIET, *FAN_LEVELS]
_FAN_BY_VALUE = {3: "1", 4: "2", 5: "3", 6: "4", 7: "5", 10: FAN_AUTO, 11: FAN_QUIET}
_VALUE_BY_FAN = {v: k for k, v in _FAN_BY_VALUE.items()}

SWING_STOP = "stop"
SWING_SWING = "swing"
SWING_AUTO = "auto"
_SWING_NAMED = {
    0: SWING_STOP,
    15: SWING_SWING,
    16: SWING_AUTO,
    19: "natural",
    20: "circulation",
    23: "comfort",
}
_VALUE_BY_SWING = {v: k for k, v in _SWING_NAMED.items()}

LED_OPTIONS = ["off", "low", "high"]

# App defaults for India when the unit gives no range (tenths not needed).
_DEFAULT_RANGE = {Mode.COOL: (18.0, 32.0), Mode.HEAT: (18.0, 30.0)}
AUTO_OFFSET_RANGE = (-2.0, 2.0)


def _on(value: Any) -> bool | None:
    if value is None:
        return None
    return le_uint(value) not in (None, 0)


class RoomAC:
    """A Daikin room AC reachable through a DSIOT transport."""

    def __init__(
        self,
        transport: Transport,
        edge_id: str | None = None,
        initial: dict[str, Any] | None = None,
    ) -> None:
        self.transport = transport
        self.edge_id = edge_id
        self.base = transport.base_for(edge_id)
        self.values: dict[str, Any] = dict(initial or {})
        self.meta: dict[str, dict[str, Any]] = {}

    # ----------------------------------------------------------------- reads

    def _targets(self) -> list[str]:
        b = self.base
        return [
            f"{b}/{INDOOR}?filter=pv,md",
            f"{b}/{OUTDOOR}?filter=pv,md",
            f"{b}.adp_i?filter=pv",
            f"{b}.adp_d?filter=pv",
            f"{b}.adp_r?filter=pv",
            f"{b}/adr_0100.i_power.week_power?filter=pv",
        ]

    async def async_update(self) -> None:
        """Read status, adapter info and energy in one batch."""
        targets = self._targets()
        responses = await self.transport.read(targets)
        values: dict[str, Any] = {}
        meta: dict[str, dict[str, Any]] = {}
        for index, (target, response) in enumerate(zip(targets, responses, strict=True)):
            if index == 0:
                # The indoor unit is required; everything else is best effort.
                check_rsc(response, target)
            elif str(response.get("rsc", 2000)) not in {"2000", "2001", "2002", "2003", "2004"}:
                _LOGGER.debug("Optional read %s failed: rsc %s", target, response.get("rsc"))
                continue
            flatten(response.get("pc"), "", values, meta)
        if K_MODE not in values and K_POWER not in values:
            raise UnsupportedDeviceError("Unit did not report room AC status")
        self.values = values
        self.meta = meta

    @property
    def is_room_ac(self) -> bool:
        """Whether the status tree looks like a room AC."""
        return K_POWER in self.values or K_MODE in self.values

    def has(self, key: str) -> bool:
        """Whether the unit reports a property."""
        return key in self.values

    # ------------------------------------------------------------- identity

    @property
    def mac(self) -> str | None:
        mac = self.values.get("adp_i.mac")
        return str(mac) if mac else None

    @property
    def name(self) -> str | None:
        name = self.values.get("adp_d.name")
        if not name:
            return None
        return unquote(str(name)).strip() or None

    @property
    def model(self) -> str | None:
        return ascii_reversed(self.values.get(K_MODEL))

    @property
    def firmware(self) -> str | None:
        ver = self.values.get("adp_i.ver")
        return str(ver).replace("_", ".") if ver else None

    @property
    def wifi_rssi(self) -> int | None:
        rssi = self.values.get("adp_r.wlan_info.rssi")
        try:
            return int(rssi) if rssi is not None else None
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------ operation

    @property
    def power(self) -> bool | None:
        return _on(self.values.get(K_POWER))

    @property
    def raw_mode(self) -> int | None:
        return le_uint(self.values.get(K_MODE))

    @property
    def mode(self) -> Mode | None:
        raw = self.raw_mode
        return _MODE_BY_VALUE.get(raw) if raw is not None else None

    @property
    def supported_modes(self) -> list[Mode]:
        """Modes the unit accepts, from the ``p_01`` capability bitmask."""
        mask = md_int(self.meta.get(K_MODE), "mx")
        if mask:
            return [m for m, v in _VALUE_BY_MODE.items() if mask & (1 << v)]
        modes = [Mode.AUTO, Mode.COOL, Mode.HEAT, Mode.DRY, Mode.FAN]
        if self.values.get(K_MODEL_TYPE) == "01":  # cooling-only model
            modes = [Mode.COOL, Mode.DRY, Mode.FAN]
        return modes

    def keys_for(self, mode: Mode | None = None) -> ModeKeys | None:
        mode = mode or self.mode
        return MODE_KEYS.get(mode) if mode else None

    # -- setpoints

    def setpoint_is_absolute(self, mode: Mode | None = None) -> bool:
        """Cool/heat use absolute setpoints; auto uses a relative offset."""
        mode = mode or self.mode
        if mode in (Mode.COOL, Mode.HEAT):
            return True
        if mode == Mode.AUTO:
            raw = le_uint(self.values.get(MODE_KEYS[Mode.AUTO].setpoint))
            # Some units report an absolute auto setpoint (°C×2 ≥ 10 °C).
            return raw is not None and 20 <= raw <= 80
        return False

    @property
    def target_temperature(self) -> float | None:
        keys = self.keys_for()
        if not keys or not keys.setpoint or not self.setpoint_is_absolute():
            return None
        raw = le_uint(self.values.get(keys.setpoint))
        return raw / 2 if raw is not None else None

    def temperature_range(self, mode: Mode | None = None) -> tuple[float, float]:
        mode = mode or self.mode or Mode.COOL
        keys = MODE_KEYS.get(mode)
        default = _DEFAULT_RANGE.get(mode, (18.0, 32.0))
        if not keys or not keys.setpoint:
            return default
        md = self.meta.get(keys.setpoint)
        low, high = md_int(md, "mi"), md_int(md, "mx")
        if low is None or high is None or not 20 <= low < high <= 80:
            return default
        return low / 2, high / 2

    @property
    def auto_offset(self) -> float | None:
        """Relative auto-mode setpoint in °C, if the unit uses one."""
        key = MODE_KEYS[Mode.AUTO].setpoint
        if key not in self.values or self.setpoint_is_absolute(Mode.AUTO):
            return None
        raw = le_int(self.values[key])
        return raw / 2 if raw is not None else None

    # -- fan and air direction

    @property
    def fan_mode(self) -> str | None:
        keys = self.keys_for()
        if not keys:
            return None
        return _FAN_BY_VALUE.get(le_uint(self.values.get(keys.fan)))

    def has_fan_control(self, mode: Mode | None = None) -> bool:
        keys = self.keys_for(mode)
        return bool(keys) and keys.fan in self.values

    def swing_options(self, horizontal: bool, mode: Mode | None = None) -> list[str]:
        """Air-direction options for a mode, from the ``md.mx`` bitmask."""
        keys = self.keys_for(mode)
        if not keys:
            return []
        key = keys.swing_h if horizontal else keys.swing_v
        if key not in self.values:
            return []
        mask = md_int(self.meta.get(key), "mx")
        if not mask:
            return [SWING_STOP, SWING_SWING]
        options = [SWING_STOP] if mask & 1 or horizontal else []
        if not horizontal:
            options += [f"position_{i}" for i in range(1, 15) if mask & (1 << i)]
        options += [name for value, name in _SWING_NAMED.items() if value and mask & (1 << value)]
        if horizontal and SWING_STOP not in options:
            options.insert(0, SWING_STOP)
        return options

    def swing(self, horizontal: bool) -> str | None:
        keys = self.keys_for()
        if not keys:
            return None
        raw = le_uint(self.values.get(keys.swing_h if horizontal else keys.swing_v))
        if raw is None:
            return None
        if raw in _SWING_NAMED:
            return _SWING_NAMED[raw]
        if 1 <= raw <= 14:
            return SWING_STOP if horizontal else f"position_{raw}"
        return None

    # -- sensors

    @property
    def room_temperature(self) -> float | None:
        if (raw := le_int(self.values.get(K_ROOM_TEMP))) is not None:
            return raw / 2
        # Older firmware reports whole degrees in p_01.
        return le_uint(self.values.get(K_ROOM_TEMP_LEGACY))

    @property
    def room_humidity(self) -> int | None:
        value = self.values.get(K_ROOM_HUMIDITY)
        if not isinstance(value, str) or len(value) != 2:
            return None
        humidity = int(value, 16)
        return humidity if 0 < humidity <= 100 else None

    @property
    def outdoor_temperature(self) -> float | None:
        raw = le_int(self.values.get(K_OUTDOOR_TEMP))
        return raw / 2 if raw is not None else None

    @property
    def compressor_frequency(self) -> int | None:
        return le_uint(self.values.get(K_COMPRESSOR_HZ))

    @property
    def filter_sign(self) -> bool | None:
        return _on(self.values.get(K_FILTER_SIGN))

    @property
    def error_code(self) -> str | None:
        """Daikin error code such as ``U4``, or None when there is no error."""
        if self.values.get(K_ERROR_FLAG) != "01":
            return None
        code = ascii_reversed(self.values.get(K_ERROR_CODE))
        return code[:2] if code else "unknown"

    @property
    def energy_today(self) -> float | None:
        """Energy used today in kWh (the app reports Wh for the rolling week)."""
        datas = self.values.get(K_WEEK_ENERGY)
        if not isinstance(datas, list) or not datas:
            return None
        try:
            return int(datas[-1]) / 1000
        except (TypeError, ValueError):
            return None

    @property
    def runtime_today(self) -> int | None:
        """Minutes of operation today."""
        try:
            return int(self.values[K_TODAY_RUNTIME])
        except (KeyError, TypeError, ValueError):
            return None

    def flag(self, key: str) -> bool | None:
        return _on(self.values.get(key))

    @property
    def led_brightness(self) -> str | None:
        raw = le_uint(self.values.get(K_LED))
        return LED_OPTIONS[raw] if raw is not None and raw < len(LED_OPTIONS) else None

    # ---------------------------------------------------------------- writes

    def build_control(
        self,
        *,
        power: bool | None = None,
        mode: Mode | None = None,
        temperature: float | None = None,
        auto_offset: float | None = None,
        fan_mode: str | None = None,
        swing_v: str | None = None,
        swing_h: str | None = None,
    ) -> dict[str, str]:
        """Build the indoor-unit control write the way the app does."""
        current_power = bool(self.power)
        new_power = current_power if power is None else power
        if new_power == current_power:
            change = "02"
        else:
            change = "00" if new_power else "01"
        flat: dict[str, str] = {K_POWER: "01" if new_power else "00"}

        target_mode = mode or self.mode
        if mode is not None:
            flat[K_MODE] = to_le_hex(_VALUE_BY_MODE[mode], 2)
        elif self.raw_mode in _VALUE_BY_MODE.values():
            flat[K_MODE] = self.values[K_MODE]
        keys = MODE_KEYS.get(target_mode) if target_mode else None

        if keys and keys.setpoint and target_mode in (Mode.COOL, Mode.HEAT):
            if temperature is not None:
                low, high = self.temperature_range(target_mode)
                value = round(min(max(temperature, low), high) * 2)
                flat[keys.setpoint] = format(value, "02x")
            elif keys.setpoint in self.values:
                flat[keys.setpoint] = self.values[keys.setpoint]
        elif keys and target_mode == Mode.AUTO and keys.setpoint in self.values:
            if auto_offset is not None and not self.setpoint_is_absolute(Mode.AUTO):
                low, high = AUTO_OFFSET_RANGE
                offset = round(min(max(auto_offset, low), high) * 2)
                flat[keys.setpoint] = to_le_hex(offset, 1)
            elif temperature is not None and self.setpoint_is_absolute(Mode.AUTO):
                flat[keys.setpoint] = format(round(temperature * 2), "02x")
            else:
                flat[keys.setpoint] = self.values[keys.setpoint]

        if keys and keys.fan in self.values:
            if target_mode == Mode.DRY:
                flat[keys.fan] = to_le_hex(_VALUE_BY_FAN[FAN_AUTO], 2)
            elif fan_mode is not None:
                flat[keys.fan] = to_le_hex(_VALUE_BY_FAN[fan_mode], 2)
            else:
                flat[keys.fan] = self.values[keys.fan]

        if keys and keys.swing_v in self.values and keys.swing_h in self.values:
            flat[keys.swing_v] = (
                self._encode_swing(swing_v, horizontal=False, key=keys.swing_v)
                if swing_v is not None
                else self.values[keys.swing_v]
            )
            flat[keys.swing_h] = (
                self._encode_swing(swing_h, horizontal=True, key=keys.swing_h)
                if swing_h is not None
                else self.values[keys.swing_h]
            )

        flat[K_POWER_CHANGE] = change
        return flat

    def _encode_swing(self, option: str, *, horizontal: bool, key: str) -> str:
        if option.startswith("position_"):
            return to_le_hex(int(option.removeprefix("position_")), 3)
        if horizontal and option == SWING_STOP:
            # Keep a fixed horizontal position rather than resetting it.
            current = le_uint(self.values.get(key))
            if current is not None and 1 <= current <= 14:
                return self.values[key]
        return to_le_hex(_VALUE_BY_SWING[option], 3)

    async def async_control(self, **changes: Any) -> None:
        """Change power, mode, setpoint, fan or air direction."""
        await self._write_indoor(self.build_control(**changes))

    async def async_set_flag(self, key: str, on: bool) -> None:
        """Toggle a feature flag."""
        if key.startswith(_OUT):
            await self._write_outdoor(self._outdoor_flags(key, on))
            return
        flat = self.build_control()
        flat[key] = "01" if on else "00"
        if key == K_GOOD_SLEEP:
            # The app always sends the shift and timer alongside good sleep.
            flat[K_GOOD_SLEEP_SHIFT] = self.values.get(K_GOOD_SLEEP_SHIFT) or "00"
            flat[K_GOOD_SLEEP_TIMER] = self.values.get(K_GOOD_SLEEP_TIMER) or "00"
        await self._write_indoor(flat)

    async def async_set_led(self, option: str) -> None:
        flat = self.build_control()
        flat[K_LED] = to_le_hex(LED_OPTIONS.index(option), 1)
        await self._write_indoor(flat)

    async def async_set_preset(self, econo: bool, power_chill: bool) -> None:
        """Set the mutually exclusive Econo / Power Chill modes."""
        if self.has(K_ECONO) and self.flag(K_ECONO) != econo:
            flat = self.build_control()
            flat[K_ECONO] = "01" if econo else "00"
            await self._write_indoor(flat)
        if self.has(K_POWER_CHILL) and self.flag(K_POWER_CHILL) != power_chill:
            await self._write_outdoor(self._outdoor_flags(K_POWER_CHILL, power_chill))

    def _outdoor_flags(self, key: str, on: bool) -> dict[str, str]:
        flat = {key: "01" if on else "00"}
        if key == K_POWER_CHILL and on and self.has(K_QUIET):
            flat[K_QUIET] = "00"  # the app turns quiet off with Power Chill
        return flat

    async def _write_indoor(self, flat: dict[str, str]) -> None:
        await self.transport.write(f"{self.base}/{INDOOR}", build_tree(flat))
        self._apply(flat)

    async def _write_outdoor(self, flat: dict[str, str]) -> None:
        await self.transport.write(f"{self.base}/{OUTDOOR}", build_tree(flat))
        self._apply(flat)

    def _apply(self, flat: dict[str, str]) -> None:
        """Optimistically reflect a successful write until the next poll."""
        for key, value in flat.items():
            if key != K_POWER_CHANGE:
                self.values[key] = value


def parse_edge(edge: dict[str, Any]) -> tuple[str, bool, dict[str, Any]]:
    """Split a cloud edge object into ``(ri, connected, flattened values)``."""
    ri = str(edge.get("ri", ""))
    try:
        connected = int(edge.get("cnst", 1)) == 1
    except (TypeError, ValueError):
        connected = True
    values: dict[str, Any] = {}
    for item in edge.get("pch") or []:
        flatten(item, "", values)
    for child in edge.get("ch") or []:
        if isinstance(child, dict):
            for item in child.get("pch") or []:
                flatten(item, "", values)
    return ri, connected, values
