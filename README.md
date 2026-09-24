# Daikin India for Home Assistant

A Home Assistant integration for Daikin air conditioners sold in India. These units are normally controlled with the **Daikin AC** app (`in.co.daikin.remoapp`).

- **Local control.** It talks directly to the unit's Wi-Fi adapter on your network over the adapter's HTTP API (called "DSIOT"). No cloud connection or account is needed.
- **Cloud control (optional).** It can also log in to your Daikin AC app account and control the units through Daikin's servers.

> **Status: early testing (v0.1).** The protocol was reverse-engineered from the Android app ([docs/api-spec.md](docs/api-spec.md)) and has not yet been confirmed against every unit. Please report what works and what doesn't. Diagnostics downloads help a lot (see below).

This project is not affiliated with or endorsed by Daikin.

## Features

| Entity | What it does |
|---|---|
| Climate | Power, mode (cool, heat, auto, dry, fan), target temperature (0.5 °C steps), fan speed (auto, quiet, levels 1–5), vertical and horizontal swing and louver positions, and presets Econo and Power Chill |
| Sensors | Room temperature and humidity, outdoor temperature, compressor frequency, energy used today (kWh; works with the Energy dashboard), runtime today, error code, Wi-Fi signal (disabled by default) |
| Switches | Streamer, outdoor-unit quiet, Dew Clean, odour prevention, Good Sleep, Intelligent Eye |
| Select | Display (LED) brightness |
| Number | Auto-mode temperature offset (−2 to +2 °C) |
| Binary sensors | Filter needs cleaning; error present |

An entity is only created if your unit reports that feature. Options such as the available modes and swing positions are also read from the unit itself.

## Installation

### HACS (recommended)

1. In HACS, open the menu (⋮) and choose **Custom repositories**.
2. Add `https://github.com/gpdl49/ha-daikin-india` with type **Integration**.
3. Install **Daikin India**, then restart Home Assistant.

### Manual

Copy `custom_components/daikin_india` into your Home Assistant `config/custom_components/` folder, then restart.

## Setup

Go to **Settings → Devices & services → Add integration → Daikin India** and pick one of:

- **Find adapters on my network.** A UDP broadcast looks for adapters on your network. Home Assistant must be on the same network or VLAN as the ACs.
- **Enter adapter IP address.** Use this when discovery doesn't work (for example across VLANs). A DHCP reservation for the AC is recommended.
- **Daikin AC app account (cloud).** Log in with your registered phone number and either your password or an SMS code. Every unit on the account is added. Units you have already added locally are skipped.

**Lock PIN.** If a lock password is set on the unit in the Daikin AC app, the integration asks for that 4-digit PIN. If you change it later, Home Assistant prompts you to re-authenticate.

**Polling.** Local units are polled every 20 s and cloud units every 60 s. A change you make shows immediately and is confirmed on the next poll.

## Troubleshooting

- **"This adapter does not support the DSIOT protocol".** The adapter's firmware predates DSIOT. Update the adapter from the Daikin AC app and try again.
- **Discovery finds nothing.** Enter the IP address instead. You can find it in your router's DHCP client list.
- **Something looks wrong.** Open the device page, choose **Download diagnostics**, and attach the file to an issue. The file contains the raw values the unit reports; personal identifiers (MAC, names, tokens, phone number) are redacted.
- **Debug logs.** Enable them with:

  ```yaml
  logger:
    logs:
      custom_components.daikin_india: debug
  ```

## Testing checklist

If you're helping test, please report:

1. How you connected (discovery, IP address or cloud) and whether a lock PIN was needed.
2. Whether the climate card's current state matches the Daikin app.
3. Power on/off, each mode, temperature changes, fan speeds and swing, and whether the unit responds (it beeps).
4. Whether the room temperature matches the unit's display.
5. Econo, Power Chill and any switches your unit shows.
6. A diagnostics download, from both a local entry and a cloud entry if you can.

## How it works

The Daikin AC app and the adapter both use DSIOT, a JSON protocol served at `/dsiot/multireq`. The cloud relays the same requests to the adapter, so the integration uses one code path for local and cloud control. The details are in:

- [docs/api-spec.md](docs/api-spec.md): the full protocol, authentication and property map
- [docs/architecture.md](docs/architecture.md): the integration's design
- [docs/prior-art.md](docs/prior-art.md): comparison with other Daikin integrations

## Development

```bash
uv venv --python 3.13
uv pip install pytest-homeassistant-custom-component ruff
uv run --no-project pytest
uv run --no-project ruff check custom_components tests
```

## License

MIT
