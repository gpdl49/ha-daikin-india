# Daikin India for Home Assistant

A Home Assistant integration for Daikin air conditioners sold in India. These units are normally controlled with the **GO DAIKIN** app for India (`in.co.daikin.remoapp`).

- **Local control.** It talks directly to the unit's Wi-Fi adapter on your network over the adapter's HTTP API (called "DSIOT"). No cloud connection or account is needed.
- **Cloud control (optional).** It can also log in to your GO DAIKIN app account and control the units through Daikin's servers.

> **Status: early testing (v0.2).** The protocol was worked out by observing how the GO DAIKIN app talks to the adapter and has not yet been confirmed against every unit. Please report what works and what doesn't. Diagnostics downloads help a lot (see below).

This project is not affiliated with or endorsed by Daikin.

### How is this different from the GO DAIKIN integration?

The [GO DAIKIN integration](https://github.com/doubleukay/godaikin-ha) (`godaikin`) works with the GO DAIKIN cloud used in Malaysia and Southeast Asia, where you log in with an email address. Indian units use a different Daikin cloud and log in with a phone number, so that integration doesn't work with them. This integration is for Indian units, and adds:

- **Local control.** It talks to the AC over your network, with no account or internet needed, and keeps working when Daikin's servers are down.
- **India-specific features.** Streamer, Good Sleep, Dew Clean, odour prevention, Intelligent Eye and outdoor-unit quiet, where your unit has them.
- **Unit-reported capabilities.** Modes, fan speeds, airflow patterns and louver positions come from the unit itself.

## Features

| Entity | What it does |
|---|---|
| Climate | Power, mode (cool, heat, auto, dry, fan), target temperature (0.5 °C steps), fan speed (auto, quiet, low to high in five steps), vertical airflow (fixed, swing, auto, and natural/circulation/comfort where supported), horizontal swing, and presets Normal, Econo and Power Chill |
| Sensors | Room temperature and humidity, outdoor temperature, energy used today (kWh; works with the Energy dashboard) |
| Switches | Streamer, outdoor-unit quiet, Good Sleep |
| Configuration | Dew Clean, odour prevention, display (LED) brightness, vertical louver position, auto-mode temperature offset (−2 to +2 °C), Intelligent Eye energy saver and auto on/off (both disabled by default) |
| Diagnostics | Runtime today, error code, compressor frequency and Wi-Fi signal (both disabled by default) |
| Binary sensors | Filter needs cleaning; error present |

An entity is only created if your unit reports that feature. Options such as the available modes, airflow patterns and louver positions are also read from the unit itself. Entities that are disabled by default can be enabled from the device page.

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gpdl49&repository=ha-daikin-india&category=integration)

Or add it by hand:

1. In HACS, open the menu (⋮) and choose **Custom repositories**.
2. Add `https://github.com/gpdl49/ha-daikin-india` with type **Integration**.
3. Install **Daikin India**, then restart Home Assistant.

### Manual

Copy `custom_components/daikin_india` into your Home Assistant `config/custom_components/` folder, then restart.

## Setup

Go to **Settings → Devices & services → Add integration → Daikin India** and pick one of:

- **Find adapters on my network.** A UDP broadcast looks for adapters on your network. Home Assistant must be on the same network or VLAN as the ACs.
- **Enter adapter IP address.** Use this when discovery doesn't work (for example across VLANs). A DHCP reservation for the AC is recommended.
- **GO DAIKIN app account (cloud).** Log in with your registered phone number and either your password or an SMS code. Every unit on the account is added. Units you have already added locally are skipped.

**Lock PIN.** If a lock password is set on the unit in the GO DAIKIN app, the integration asks for that 4-digit PIN. If you change it later, Home Assistant prompts you to re-authenticate.

**Polling.** Local units are polled every 20 s and cloud units every 60 s. A change you make shows immediately and is confirmed on the next poll.

## Dashboard card

Home Assistant's built-in area pages show only the temperature buttons on a climate tile, so turning the AC on takes an extra tap. The integration can't change that, but on your own dashboard you can add a tile with mode buttons. Tapping the icon then turns the AC on or off:

```yaml
type: tile
entity: climate.bedroom_ac  # your AC's entity ID
icon_tap_action:
  action: toggle
features:
  - type: climate-hvac-modes
    hvac_modes: [cool, dry, fan_only, auto, "off"]
  - type: target-temperature
```

Add `climate-fan-modes`, `climate-swing-modes` or `climate-preset-modes` to the `features` list for fan speed, swing or Econo/Power Chill.

## Privacy and security

- **What is stored.** Home Assistant keeps the config entry in `.storage/core.config_entries`. For a local unit that is the adapter address and lock PIN. For a cloud account it is the phone number, a random per-installation ID and the session tokens. If you log in with a password and leave **Stay signed in** ticked, the password is stored too, so the integration can log in again by itself when Daikin ends the session. It is redacted from diagnostics. Untick it, or use SMS login, to keep the password out of storage; you will then be asked to log in again whenever the session ends. SMS codes are never stored.
- **Local traffic is unencrypted.** The adapter only speaks plain HTTP on your LAN, and the lock PIN is sent with every request, as the GO DAIKIN app does. Keep the ACs on a network you trust.
- **Cloud traffic** goes over HTTPS (with certificate verification) to Daikin's servers at `daikinacmanager.com`.
- **Bundled app values.** `dsiot/const.py` contains the OAuth `client_id` and `client_secret`, and `dsiot/cloud_auth.py` the RSA public key, that the Daikin AC Android app uses to log in. They were extracted from the publicly distributed app, are the same for every user of the app, and identify the app rather than you. They are not credentials for your account.
- **Diagnostics** redact the PIN, phone number, tokens, installation ID, address, MAC, SSID, edge IDs and unit names.

## Troubleshooting

- **"This adapter does not support the DSIOT protocol".** The adapter's firmware predates DSIOT. Update the adapter from the GO DAIKIN app and try again.
- **Cloud account asks you to log in again (`invalid_grant`).** Daikin ended the saved session, for example after a long outage or a sign-in elsewhere. With **Stay signed in** ticked, the integration logs in again by itself; otherwise open the repair prompt and log in. If it keeps happening, please open an issue with debug logs.
- **A change takes a few seconds to show.** Cloud units relay state with a delay. The integration shows your change straight away and confirms it with the unit a few seconds later.
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
- [ ] **Lock PIN.** If the unit has a lock password set in the GO DAIKIN app, does the integration ask for the PIN and accept it? Does a wrong PIN show an error?
- [ ] **Cloud: password login.** Does logging in with your phone number and password work? Are all your units added?
- [ ] **Cloud: SMS login.** Does logging in with your phone number and an SMS code work?
- [ ] **Cloud: phone app session.** After logging in from Home Assistant, is the GO DAIKIN app on your phone still logged in? (Some Daikin accounts may allow only one session.)
- [ ] **Cloud: staying logged in.** Leave the cloud entry running for more than 2 hours. Does it keep updating without asking you to log in again?

### Reading state

- [ ] **Current state.** Does the climate card show the same power, mode, set temperature, fan speed and swing as the GO DAIKIN app?
- [ ] **Room temperature.** Does it match the unit's display or the app? Note whether it shows half degrees (for example 23.5).
- [ ] **Humidity.** Does it match the app, if your unit has a humidity sensor?
- [ ] **Outdoor temperature and compressor frequency.** Do these look plausible? The compressor should read 0 when the unit is idle.
- [ ] **Energy and runtime.** Compare "Energy today" and "Runtime today" with the app's energy screen. Does energy reset to about 0 after midnight?
- [ ] **Changes made in the app.** When you change something in the GO DAIKIN app, does Home Assistant show it within about 20 s (local) or 60 s (cloud)?

### Controls

Check each of these from Home Assistant. Confirm that the unit responds (it beeps) and that the app shows the change.

- [ ] Power on and power off.
- [ ] **Each mode:** Cool, Heat (if your unit has it), Dry, Fan and Auto.
- [ ] **Set temperature** in Cool and Heat, including half-degree steps.
- [ ] **Auto mode.** Does the climate card show a set temperature, or does the "Auto mode temperature offset" slider appear? If the slider appears, does changing it work?
- [ ] **Fan speed:** Auto, Quiet and Low to High (five steps). In Dry mode the fan should stay on Auto, as it does in the app.
- [ ] **Vertical swing:** Fixed, Swing, Auto and any other airflow patterns shown. Then the "Vertical louver position" select: do the positions shown match what your unit supports, and does choosing one stop the swing?
- [ ] **Horizontal swing**, if your unit has it.
- [ ] **Presets.** Econo and Power Chill. Turning on Power Chill should turn off Econo and outdoor quiet.
- [ ] **Switches.** Each switch your unit shows (Streamer, Outdoor unit quiet, Good sleep, and under Configuration Dew clean, Odour prevention and Intelligent Eye). Test "Outdoor unit quiet" on its own, without changing anything else at the same time.
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

The GO DAIKIN app and the adapter both use DSIOT, a JSON protocol served at `/dsiot/multireq`. The cloud relays the same requests to the adapter, so the integration uses one code path for local and cloud control. The details are in:

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
