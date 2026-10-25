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

## Privacy and security

- **What is stored.** Home Assistant keeps the config entry in `.storage/core.config_entries`. For a local unit that is the adapter address and lock PIN. For a cloud account it is the phone number, a random per-installation ID and the session tokens. Your Daikin password and SMS codes are never stored; they are only used to log in.
- **Local traffic is unencrypted.** The adapter only speaks plain HTTP on your LAN, and the lock PIN is sent with every request, as the Daikin AC app does. Keep the ACs on a network you trust.
- **Cloud traffic** goes over HTTPS (with certificate verification) to Daikin's servers at `daikinacmanager.com`.
- **Bundled app values.** `dsiot/const.py` contains the OAuth `client_id` and `client_secret`, and `dsiot/cloud_auth.py` the RSA public key, that the Daikin AC Android app uses to log in. They were extracted from the publicly distributed app, are the same for every user of the app, and identify the app rather than you. They are not credentials for your account.
- **Diagnostics** redact the PIN, phone number, tokens, installation ID, address, MAC, SSID, edge IDs and unit names.

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

If you're helping test, please open an issue with your results. Include your AC's model, the adapter firmware (shown on the device page) and a **diagnostics download**. Include one from a local entry and one from a cloud entry if you can. For anything that fails, add debug logs (see Troubleshooting).

### Setup

- [ ] **Discovery.** Does "Find adapters on my network" find the unit? Include the unit name and IP it shows.
- [ ] **Manual IP.** Does "Enter adapter IP address" work?
- [ ] **Lock PIN.** If the unit has a lock password set in the Daikin AC app, does the integration ask for the PIN and accept it? Does a wrong PIN show an error?
- [ ] **Cloud: password login.** Does logging in with your phone number and password work? Are all your units added?
- [ ] **Cloud: SMS login.** Does logging in with your phone number and an SMS code work?
- [ ] **Cloud: phone app session.** After logging in from Home Assistant, is the Daikin AC app on your phone still logged in? (Some Daikin accounts may allow only one session.)
- [ ] **Cloud: staying logged in.** Leave the cloud entry running for more than 2 hours. Does it keep updating without asking you to log in again?

### Reading state

- [ ] **Current state.** Does the climate card show the same power, mode, set temperature, fan speed and swing as the Daikin AC app?
- [ ] **Room temperature.** Does it match the unit's display or the app? Note whether it shows half degrees (for example 23.5).
- [ ] **Humidity.** Does it match the app, if your unit has a humidity sensor?
- [ ] **Outdoor temperature and compressor frequency.** Do these look plausible? The compressor should read 0 when the unit is idle.
- [ ] **Energy and runtime.** Compare "Energy today" and "Runtime today" with the app's energy screen. Does energy reset to about 0 after midnight?
- [ ] **Changes made in the app.** When you change something in the Daikin AC app, does Home Assistant show it within about 20 s (local) or 60 s (cloud)?

### Controls

Check each of these from Home Assistant. Confirm that the unit responds (it beeps) and that the app shows the change.

- [ ] Power on and power off.
- [ ] **Each mode:** Cool, Heat (if your unit has it), Dry, Fan and Auto.
- [ ] **Set temperature** in Cool and Heat, including half-degree steps.
- [ ] **Auto mode.** Does the climate card show a set temperature, or does the "Auto mode temperature offset" slider appear? If the slider appears, does changing it work?
- [ ] **Fan speed:** Auto, Quiet and levels 1–5. In Dry mode the fan should stay on Auto, as it does in the app.
- [ ] **Vertical swing:** Swing, Auto and the fixed positions. Do the positions shown match what your unit supports?
- [ ] **Horizontal swing**, if your unit has it.
- [ ] **Presets.** Econo and Power Chill. Turning on Power Chill should turn off Econo and outdoor quiet.
- [ ] **Switches.** Each switch your unit shows (Streamer, Outdoor unit quiet, Dew clean, Odour prevention, Good sleep, Intelligent Eye). Test "Outdoor unit quiet" on its own, without changing anything else at the same time.
- [ ] **Display brightness**, if shown.
- [ ] **Local and cloud.** Do controls work the same way from both a local entry and a cloud entry?

### Known unknowns

These parts were inferred from the app's code and haven't been checked on real hardware. Please call them out in your report:

- Which room-temperature value the unit reports: precise (half degrees) or whole degrees.
- Whether Auto mode uses a relative offset (−2 to +2 °C) or an absolute temperature.
- Whether writes are accepted as sent. If a control does nothing or shows an error, include the error message and debug logs.
- Whether any mode shows as unknown. This can happen with Humidify, or while the unit is in Auto mode.
- The units of the energy figures (Wh per day is assumed).

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
