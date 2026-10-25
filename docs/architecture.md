# Home Assistant integration for Daikin India: architecture

Status: proposal. The design is based on the decompiled app ([api-spec.md](api-spec.md)) and the survey of existing integrations ([prior-art.md](prior-art.md)). Nothing here has been checked against live traffic yet; see the validation phase below.

## Goals

- Control Daikin India room ACs (`cdev=RA`) from Home Assistant **locally**, with no cloud dependency.
- **Cloud** access as an optional alternative, for units that can't be reached on the LAN.
- Automatic discovery, and a small config flow.

**Not goals (for now):** Wi-Fi provisioning, firmware updates, account management, air purifiers, VRV, EcoCute.

## Key facts that drive the design

1. **One device protocol, two transports.**
   - The adapter speaks DSIOT `/dsiot/multireq` over plain HTTP.
   - The cloud (`prod.daikinacmanager.com`) proxies the *same* request and response trees.
   - Only three things differ between the two transports:
     - Base path: `/dsiot/edge` locally, `/dsiot/edges/<ri>` in the cloud.
     - Auth header.
     - Host.
2. **No MQTT anywhere.** Polling over HTTP is the only option.
3. **Local auth is trivial.** The only credential is an optional 4-digit lock PIN, sent as `Authorization: Basic <pin>` (literal, not base64).
4. **Cloud auth is a custom proxy in front of Cognito.**
   - Credentials go inside an RSA-encrypted blob, built with the public key shipped in the app.
   - A hardcoded client_id and client_secret are also sent.
   - After login the client holds an `id_token`, which it refreshes proactively before `cd_expiresIn` runs out.
5. **pydaikin's `DaikinBRP084` already implements the local protocol** for the same adapter family. It has gaps: no PIN support, missing mode codes, and missing per-mode keys.
6. **Writes follow app-specific rules:**
   - Every write must include `e_3003.p_2D`, the power-transition marker.
   - Fan and swing each have a separate key for every mode.
   - Quiet and Powerful are written to `adr_0200`, in a separate request sent about 2 s later.
   - What a unit supports comes from the `md` metadata in reads: min/max and bitmask values.

## Strategy

We use two tracks that run in parallel.

- **Track A: upstream to pydaikin and HA core.** Small, low-risk fixes that make HA's built-in `daikin` integration work locally with Indian units:
  - PIN support, plus a config-flow field for it
  - a tolerant mode map (`0800`, `0900`, `0A00`)
  - fan and swing keys for dry and humidify (`p_27`, `p_2B`, `p_29`/`p_2A`)
  - room temperature read from `p_06`
  - checking the per-request `rsc` codes

  This benefits everyone and may be all that most users need.
- **Track B: our own integration, `daikin_india`, distributed through HACS.** It covers what core won't:
  - the cloud transport and India login
  - hybrid local/cloud routing
  - full support for everything the unit reports it can do
  - India-specific features: humidify, Streamer, schedules, energy history

  It ships its own small library. The library borrows pydaikin's key maps where they agree with ours, but doesn't depend on pydaikin: pydaikin's class structure is local-only and built around its legacy adapters.

The rest of this document describes Track B.

## Layout

```
daikin-reveng/
├── docs/                         # spec, prior art, this document
├── lib/daikin_dsiot/             # standalone async library (publishable to PyPI)
│   ├── codec.py                  # tree ⇄ flat-dict, hex LE helpers, md.st decoding
│   ├── protocol.py               # multireq envelope, rsc → exceptions
│   ├── transport/
│   │   ├── base.py               # Transport ABC: base_path(), headers(), post()/put()
│   │   ├── local.py              # http://<ip>/dsiot/multireq, Basic <pin>
│   │   └── cloud.py              # https://prod.daikinacmanager.com, Bearer id_token
│   ├── auth/cloud_session.py     # RSA blob, login (PASS/OTP), refresh, logout
│   ├── discovery.py              # UDP 30050 probe; cloud edge list
│   ├── devices/
│   │   ├── base.py               # adp_i / dev_i identity, capability parsing
│   │   └── room_ac.py            # RoomAC model: read map, write builder, capabilities
│   └── exceptions.py
├── custom_components/daikin_india/
│   ├── __init__.py               # setup; one coordinator per unit
│   ├── manifest.json
│   ├── config_flow.py            # local / cloud / discovery flows; reauth; options
│   ├── coordinator.py            # DataUpdateCoordinator; transport routing
│   ├── entity.py                 # base entity, DeviceInfo from adp_i/dev_i
│   ├── climate.py  sensor.py  switch.py  select.py  number.py  binary_sensor.py
│   ├── diagnostics.py            # redacted raw trees (for fixture collection)
│   └── strings.json / translations/
└── tests/
    ├── fixtures/                 # captured multireq responses (redacted)
    ├── lib/                      # codec, room_ac encode/decode, auth blob
    └── integration/              # pytest-homeassistant-custom-component
```

**As built (v0.1):** the library lives at `custom_components/daikin_india/dsiot/` rather than `lib/daikin_dsiot/`, so HACS installs need no PyPI package. It depends only on `aiohttp` and `cryptography`, which Home Assistant already ships. It can be split out to PyPI later.

## Library design (`daikin_dsiot`)

### Codec

- **Response parsing:** `flatten(pc)` turns a response tree into a flat dict, e.g. `{"e_1002.e_3001.p_01": "0200", ...}`. It keeps `md` as a separate dict keyed the same way.
- **Request building:** `build(flat)` turns a flat dict of writes into a nested `{"pn","pch":[...]}` tree. `pt` is never sent.
- **Value helpers:**
  - `le_int(hex, signed)` and `to_le_hex(int, nbytes)`
  - `half_degrees(hex)`
  - `step(md.st)`
  - `ascii_reversed(hex)` for strings in `dgc_status`
- It is pure and synchronous, so it is easy to test against the captured fixtures.

### Protocol

`MultiReq` builds `{"requests":[{op,to[,pc]}]}` bodies and matches each response to its request by `fr`.

The `rsc` codes map to exceptions:

| `rsc` | Meaning | Exception |
|---|---|---|
| 2000–2004 | OK | none |
| 401 / 4001 | wrong PIN or expired token | `AuthError` |
| 4009 | locked | `LockedError` |
| 5107 | unit not connected | `DeviceOfflineError` |
| 503 / 5003 | maintenance | `MaintenanceError` |
| 6000 or a network error | no response | `CommunicationError` |

For resources that are allowed to fail (`adp_*`, `dev_i`, `dgc_status`), the protocol layer returns a partial result instead of raising.

### Transport

```python
class Transport(ABC):
    def path(self, resource: str) -> str: ...   # "/dsiot/edge" + r  |  f"/dsiot/edges/{ri}" + r
    async def read(self, resources: list[str], md: bool) -> dict[str, Response]
    async def write(self, resource: str, flat: dict[str, str]) -> Response
```

**Local transport**
- Sends to `http://<ip>` using the Home Assistant aiohttp session.
- Sends the PIN header when one is set.
- Serialises requests with one asyncio lock per adapter; the app uses one thread per adapter because adapters handle concurrent requests badly.
- 10 s timeout.

**Cloud transport**
- Holds a `CloudSession` and calls `await session.ensure_valid()` before every request.
- One `CloudSession` is shared by every unit on the account. Its requests are batched: one multireq that reads all the units' `dgc_status` in a single POST.

### Cloud session

- **Stored in the HA config entry:** `phone`, `install_uuid`, and the tokens (`id_token`, `refresh_token`, `cd_*`, `issued_at`, `expires_in`). The password is never stored.
- `login_password(phone, pw)` and `login_otp_start(phone)` / `login_otp_verify(session, otp)` produce a `Tokens` object.
- `refresh()` runs proactively when less than 5 minutes remain before expiry. If the refresh fails, the integration raises `ConfigEntryAuthFailed`, which starts the HA reauth flow.
- Refreshes are single-flight: an asyncio lock, and a new refresh isn't started within 60 s of the last one (as in the app).
- The RSA public key is bundled as package data.
- The `client_id` and `client_secret` are app constants, not per-user secrets. They go in one constants module so a new app release only needs one update.

### Room AC model (`devices/room_ac.py`)

- **Reads:**
  - `adr_0100.dgc_status?filter=pv,md` and `adr_0200.dgc_status?filter=pv,md`
  - the adapter's `adp_i` and `dev_i`, once at setup
  - `adr_0100.i_power.week_power` on a slower schedule
- **`RoomACState`** is a typed dataclass: power, mode, target temperature for each mode, fan and swing for each mode, room temperature, humidity, outdoor temperature, compressor Hz, and flags (econo, streamer, quiet, powerful, …). Values missing from a unit's response become `None`.
- **`Capabilities`** come from `md` on the first read:
  - supported modes, from the `p_01` `mx` bitmask
  - setpoint range and step
  - fan levels
  - vertical and horizontal swing positions
  - humidity support
  - which feature flags exist (a key is only supported if it appears in the tree)
- **Writes** go through a builder that enforces the app's rules:
  - It always adds `e_3003.p_2D`: `00` when turning on, `01` when turning off, `02` otherwise.
  - When the mode changes, it re-sends the target temperature, fan and swing for the new mode's keys.
  - Temperatures are encoded as `round(t*2)` in hex, clamped to the `md` range.
  - `set_quiet` and `set_powerful` go to `adr_0200` in their own request, after a 2 s delay.
  - Powerful is mutually exclusive with econo, comfort and quiet. The builder clears the others, following pydaikin's validated logic.
- **Read-after-write:** the unit's state stays stale for a short while after a write. The model applies the change to local state straight away, then asks the coordinator to refresh after about 2 s.

### Discovery

- **Local:** UDP broadcast `DAIKIN_UDP/common/basic_info` to port 30050 from a source port in the range 30000–30050. We keep replies with `type=GPF` or `protocol=DGC` and `cdev=RA`. Each reply gives `mac`, `name`, `ver`, `lpw_flag` and the IP.
- **Cloud:** multireq `op:2` on `/dsiot/edges?filter_edges=all&mask_oldedges=1&expand=ch`. It returns `ri`, `cnst` (connected) and the adapter identity for each unit.
- **Linking a local unit to its cloud edge:** first by MAC (`adp_i.mac` locally matched against the edge's adapter info). If that fails, locally `GET /config/adapter/user_info` returns `resource_id`, which equals the cloud `ri`.

## Home Assistant integration

### Config flows

1. **Local (manual).** The user enters a host and an optional PIN. The flow validates by reading `adp_i` and `dgc_status`. The unique ID is the MAC.
2. **Local (discovered).**
   - An integration-level UDP scan finds units when the user adds the integration.
   - Zeroconf `_dkapi._tcp.local.` is registered only if we confirm Indian adapters advertise it.
   - If `lpw_flag=1`, the flow asks for the PIN.
3. **Cloud account.**
   - The user enters a phone number (with the +91 default) and a password. OTP is offered as an alternative step.
   - One config entry covers the whole account, and its units become devices under it.
   - If the account includes a unit that's already configured locally (matched by MAC or `ri`), that unit is linked rather than duplicated.
4. **Reauth:** a PIN change, or a failed token refresh, triggers `async_step_reauth`.
5. **Options:**
   - Polling interval: local 15 s, cloud 60 s.
   - Transport preference: `local`, `cloud` or `auto`.

### Coordinators and routing

- **One coordinator per unit.**
- **Fetching:**
  - Local-only units fetch directly.
  - Units on a cloud account also have a shared account-level coordinator. It fetches every edge in a single batched multireq and fans the data out to each unit.
- **`auto` mode:** local is used first. After N consecutive local failures, requests fall back to cloud, and local is retried every 5 minutes. The active transport is shown as a diagnostic sensor.
- **Energy:** `week_power` and `year_power` are polled separately, every 15–30 minutes.

### Entities (per room AC)

| Platform | Entity | Source |
|---|---|---|
| climate | main | power, mode (`off`, `cool`, `heat`, `dry`, `fan_only`, `heat_cool`/`auto`), target temp for the active mode, current temp (`p_06`), current humidity, fan modes (auto, silence, 1–5), swing modes (from capabilities), presets (`none`, `eco`, `boost`, `comfort`, `quiet`…) |
| sensor | room temp, room humidity, outdoor temp, compressor frequency, today's runtime, energy today/week/year (kWh, `state_class: total_increasing` where valid) | `e_A00B`, `e_A00D`, `e_2006`, `i_power` |
| switch | Streamer, Econo, Intelligent Eye, Dew Clean, Good Sleep, LED (if not a select), smell-proof | `e_3003.*` (only if present) |
| select | vertical/horizontal louver position (fine positions beyond swing), LED brightness, humidify level | per-mode swing keys, `p_BC`, humidity keys |
| binary_sensor | filter sign, cloud connected (`cnst`) | `e_3001.p_15`, edge list |
| diagnostic | adapter firmware, RSSI (if exposed in `adp_r`), active transport | `adp_i`, `adp_r` |

**How humidify mode is shown:** HA has no humidify HVAC mode, so it becomes a preset (`humidify`) on the climate entity. The unit's `0800` mode maps to that preset with `hvac_mode: dry`, which is the closest match. This needs a live test.

### Diagnostics and fixture capture

`diagnostics.py` dumps the raw flattened trees and the `md` for each unit. It redacts MAC, SSID, tokens, `ri` and names. The output is also the format we collect test fixtures in.

## Validation phase (before writing much code)

1. **Probe script:** send a UDP broadcast, then a local multireq read of `adp_i` and both `dgc_status`, with and without the PIN. Record the replies.
2. **mitmproxy capture of the phone app:** the app does no certificate pinning and trusts user CAs. Capture:
   - a password login, an OTP login and a refresh, to confirm the bodies and `cd_expiresIn`
   - a cloud edge list and a status read
   - one write of each kind: power, mode, temperature, fan, swing, quiet
3. **Settle the spec's open questions:**
   - `p_06` vs `p_01` for room temperature
   - whether `p_1D` is an offset or an absolute value
   - `0900` / `0A00`
   - what `p_2D` does
   - whether the adapter accepts both PUT and POST for writes
   - energy units
   - whether logging in from HA logs out the phone app
4. **Try HA core's `daikin` integration** against the unit. This tells us how far Track A alone gets.

## Phases

| Phase | Deliverable |
|---|---|
| 0 | Validation above; fixtures committed (redacted) |
| 1 | `daikin_dsiot` codec, protocol, local transport, room AC read/write, discovery, with unit tests |
| 2 | HA integration: local config flow, coordinator, climate + sensors; HACS-installable |
| 3 | Cloud session + transport; cloud config flow; reauth |
| 4 | Hybrid routing and local ↔ cloud linking |
| 5 | Extras: switches/selects, energy, weekly schedule (`scdl_t`) service, diagnostics polish |
| ∥ | Track A PRs to pydaikin / HA core |

## Risks

- **App and backend changes:** the backend may be changed, or it may start rejecting a client_id taken from the app. Mitigation: local-first design; keep the constants in one place; the adapter's local API doesn't depend on the app.
- **Legal and terms-of-service ambiguity** of using the cloud API. It is optional and off by default, and it uses only the user's own account.
- **Session conflicts:** logging in from the integration might log out the phone app. Check this in phase 0 before committing to cloud as a default.
- **Firmware differences:** pydaikin has issues reporting `KeyError: 'pn'` on newer 3.x firmware. Mitigation: a defensive codec and support determined per unit from `md` rather than from hardcoded model tables.
- **Unknown semantics:** `p_2D`, `p_1D`, and 3-byte vs 4-byte louver values. Keep writes minimal and mirror the app's exact bodies, as captured in phase 0.
