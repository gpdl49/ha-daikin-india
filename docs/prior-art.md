# Existing Daikin integrations compared with the India backend

This compares four existing Daikin projects against the India app's protocol (see [api-spec.md](api-spec.md) and [../API.md](../API.md)), based on reading their code. Nothing has been tested against a live unit yet.

## Summary

| Project | What it targets | Match with India |
|---|---|---|
| **HA core `daikin` / [pydaikin](https://github.com/fredrike/pydaikin) `DaikinBRP084`** | Local HTTP to Daikin adapters running firmware 2.8.0+ | **Same local protocol.** Same `/dsiot/multireq` paths, message format, property keys and hex encodings |
| [doubleukay/godaikin-ha](https://github.com/doubleukay/godaikin-ha) | GO DAIKIN (Malaysia) cloud, running on AWS API Gateway and AWS IoT | None. Different backend, auth and data model |
| [jwillemsen/daikin_onecta](https://github.com/jwillemsen/daikin_onecta) | Daikin Europe Onecta cloud (OAuth2, REST `gateway-devices` / `characteristics`) | None. The older EU Residential Controller cloud uses the same model, so it doesn't match either |
| [SukramJ/go-daikin2mqtt](https://github.com/SukramJ/go-daikin2mqtt) | Onecta cloud, or Faikin (a third-party ESP32 board that replaces the adapter and speaks MQTT) | None. It never talks to a stock Daikin adapter |

## MQTT

- **The app:** never uses MQTT. It talks to the adapter over HTTP (`/dsiot/multireq`) and to the cloud over HTTPS.
- **The adapter:** `/config/adapter/user_info {method: polling|home_only}` suggests it polls the cloud over HTTP rather than keeping an MQTT session open. This is unverified.
- **Other projects:** none of them use Daikin-side MQTT. MQTT only appears in third-party bridges and in Faikin replacement hardware.

**So there is no existing Daikin MQTT channel to connect to.** The best reuse option is pydaikin, over local HTTP.

## pydaikin BRP084 compared with India

The two share:
- **Endpoints:** `POST /dsiot/multireq` for reads (`op:2`) and for writes (`op:3`). The India app uses PUT for writes; pydaikin uses POST.
- **Discovery:** UDP `DAIKIN_UDP/common/basic_info` on port 30050.
- **Keys:** the same keys for power, mode, cool/heat setpoint, per-mode fan and swing, humidity, outdoor temperature, econo, quiet, powerful and weekly energy.

### Gaps and conflicts

| Item | India app | pydaikin |
|---|---|---|
| `lpw` lock PIN | `Authorization: Basic <pin>` | **Not supported.** Setup fails if a PIN is set |
| Modes | also `0800` (humidify), `0900`, `0A00` | Unmapped. These cause an uncaught `KeyError`, which breaks setup and polling |
| Fan / swing keys for dry and humidify | fan `p_27`, `p_2B`; swing `p_29`/`p_2A` | missing |
| Room temperature | `e_A00B.p_06` (int16 × 0.5) | `e_A00B.p_01` (whole degrees) |
| Auto setpoint `p_1D` | signed offset × 0.5 | absolute °C × 2 |
| Dry offset | `p_1E` | `p_34` |
| Vane positions | `01`–`0E` positions, `10` auto | only `00`, `0F`, `17` |
| Streamer, compressor Hz, yearly energy | present | missing (open PRs #163 and #119 cover the last two) |
| Per-request `rsc` result codes | checked | ignored |
| Cloud (`/dsiot/edges/<ri>`) | yes | local only |

- **Keys pydaikin has that the India app lacks:** comfort airflow `e_3003.p_1D`, compressor and discharge temperatures `e_1003.e_A005.p_01/02`, and model strings `e_A001.p_01`.
- **Related pydaikin issues:** #153 and #155 show the same adapter family's discovery reply (`type=GPF,cdev=RA,protocol=DGC,…,lpw_flag=`). DGC adapters on firmware below 2.8.0 return 404 on `/dsiot/multireq`.

## Recommended path

1. **Test HA core `daikin` as-is.** Point it at the adapter's IP with no lock PIN set, then run a UDP discovery probe and check the reply's `protocol`, `ver` and `lpw_flag` fields. If this works, local control needs no new code.
2. **Upstream fixes to pydaikin:** `lpw` auth (plus a config-flow field in HA), a tolerant mode map with `0800`, dry and humidify fan/swing keys, `p_06` room temperature, and `rsc` checking. These are small PRs, and they help everyone else using this adapter family.
3. **Optionally, a cloud custom integration** for use away from home, or where local access is blocked: RSA and Cognito-proxy login plus multireq calls to `/dsiot/edges/<ri>/…`. The payload codec can be reused from pydaikin, since the cloud wraps the same payloads. Only the transport and base path differ.
