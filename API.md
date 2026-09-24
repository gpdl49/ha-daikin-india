# Daikin AC (India) app 1.5.2: API notes

These notes come from reading the decompiled code; none of it has been checked against live traffic yet. Package `in.co.daikin.remoapp`. Code references are relative to `jadx/sources/`.

## Hosts

| Host | Use |
|---|---|
| `https://prod.daikinacmanager.com` | Main API: login, token refresh, device control (`/dsiot/*`, `/api/*`, `/dkapp/*`, `/premise/*`) |
| `https://prod-clubdaikin.daikinacmanager.com` | Account service (Cognito proxy): OTP, signup, password, profile |
| `https://app-weather.daikinsmartdb.jp` | City lookup and weather-linkage settings |
| `http://<adapter-ip>` | Local adapter using the same DSIOT protocol, plus `/config/*` |
| `http://192.168.127.1` | Adapter access-point address during Wi-Fi provisioning |
| `sha2.daikinonlinecontroller.com` / `test2.daikindev.com` | EU region (production / development); not used by the India build |

- **Certificate pinning: none.** The network security config trusts user CAs and allows cleartext, so mitmproxy with a user-installed CA works.
- **Headers:** always `Content-Type: application/json`, plus `Authorization` as described below. There is no request signing and no API key.

## Auth

**Constants** (`gpf/net/request/common/GPFSessionInfoController.java:171`):
- `client_id = 7k8koegnvimcqj7i5p933rov73`
- `client_secret = 1upkumrsbds2513lccgi6sfatqji5sk8m7vrb9cqfrg2i7nigu5o`

**RSA "code" blobs.** Credentials are never sent in plaintext.
- The app builds a JSON object, encrypts it with `RSA/ECB/PKCS1Padding` using `assets/rsa_4096_public_key.pem`, and base64-encodes the result with newlines stripped.
- Our own client can produce these too, since only the public key is needed.

### Password login
```
POST https://prod.daikinacmanager.com/premise/dsiot/cognito/login
{"grant_type":"authorization_code",
 "code": RSA({"phone_number":"+91XXXXXXXXXX","password":"...","model":"<Build.MODEL>","app":"CI000000","timestamp":"<epoch ms>"}),
 "client_id":"7k8k...","client_secret":"1upk...",
 "auth_type":"PASS","uuid":"<random per-install UUID>"}
```

### OTP login
1. **Trigger the OTP.** Send `POST https://prod-clubdaikin.../authentication/cognito/login_otp_trigger`. The body is the bare base64 string `RSA({"phone_number":"+91..."})`, not JSON. The response contains `result_cd:"200"` and a `session` value.
2. **Verify the OTP.** Call the same `/premise/dsiot/cognito/login` endpoint as the password login. This time set `code = RSA({"phone_number","sms_otp"})`, `"auth_type":"OTP"` and `"cd_session":"<session>"`.

### Login response
The response contains:
- `access_token`, used only as a success check and not stored
- `id_token`, `refresh_token`, `uid`
- `cd_accessToken`, `cd_refreshToken`, `cd_expiresIn` (seconds), `cd_user_uuid`
- profile fields

### Using the tokens
- **Main host:** `Authorization: Bearer <id_token>`.
- **ClubDaikin and weather hosts:** `Authorization: Bearer <cd_accessToken>`.

### Refresh
Refresh when `lastUpdateTime + cd_expiresIn <= now`. The app checks this before each request; it does not react to a 401.
```
POST https://prod.daikinacmanager.com/premise/dsiot/cognito/token
{"grant_type":"refresh_token","refresh_token":"...","cd_refreshToken":"...","cd_user_uuid":"..."}
```
The response has the same shape as the login response.

### Logout
`POST /premise/dsiot/cognito/logout` with body `{"token":"<refresh_token>"}`. No Authorization header is sent.

### Local adapter lock (`lpw`)
- `lpw` is the optional 4-digit child-lock PIN.
- It is sent as `Authorization: Basic <pin>`, literally, with no base64.
- The header is only sent when the lock is set. If it isn't set, the local API is unauthenticated.

## Device protocol (DSIOT / "GPF")

### Endpoint
- **Cloud:** `https://prod.daikinacmanager.com/dsiot/multireq`
- **Local:** `http://<ip>/dsiot/multireq`
- Reads use **POST**; writes use **PUT**.

### Envelope
```json
{"requests":[{"op":2,"to":"<path>"}]}                    // read
{"requests":[{"op":3,"to":"<path>","pc":{...}}]}          // write
{"responses":[{"fr":"<path>","rsc":2000,"pc":{...}}]}     // response
```

### Result codes (`rsc`)
| Code | Meaning |
|---|---|
| 2000–2004 | OK |
| 4000 | bad parameter |
| 401 / 4001 | authentication failed |
| 4003 | forbidden |
| 4004 | not found |
| 4009 | locked |
| 5107 | device offline |
| 6000 | no response (produced by the client itself) |

### Property tree
- **Container node:** `{"pn":name,"pt":1,"pch":[...]}`
- **Leaf node:** `{"pn":name,"pt":3,"pv":"<hex>","md":{...}}`
- `pv` values are **hex strings in little-endian byte order**.
- `md` holds `st` (step), `mi` (min) and `mx` (max). It is only returned when the path ends in `?filter=pv,md`.
- `md.st` is one byte. The low nibble is the mantissa and the high nibble picks the multiplier: 0–7 means 10^n, 8–15 means 10^-(16-n). Example: `0xF5` = 0.5.

### Addressing
- **Cloud base path:** `/dsiot/edges/<ri>`, where `ri` comes from the device list.
- **Local base path:** `/dsiot/edge`.
- **Adapter-level resources** hang directly off the base path: `<base>.adp_i`, `.adp_d`, `.adp_r`, `.dev_i`, and `.adp_f` (cloud only).
- **Indoor unit:** `<base>/adr_0100.dgc_status`.
- **Outdoor unit:** `<base>/adr_0200.dgc_status`.
- **Energy:**
  - `<base>/adr_0100.i_power.week_power`: `today_runtime`, plus `datas` with 7 values
  - `<base>/adr_0100.i_power.year_power`
  - `<base>/adr_0200.history.h_01.data`: monthly values

### Device list (cloud)
```json
{"requests":[{"op":2,"to":"/dsiot/edges?filter_edges=all&mask_oldedges=1&expand=ch"}]}
```
Each edge in the response has:
- `ri`: the edge ID used in paths
- `cnst`: 1 means connected
- `lt`: time last seen
- child nodes `adp_i`, `adp_d` and `dev_i`, which carry the name, MAC and firmware

### Local discovery
- Send the UDP broadcast `DAIKIN_UDP/common/basic_info` to port 30050, from a source port in the range 30000–30050.
- The reply is plain text in the form `k=v,k=v,...`.

### Room AC properties (all under `dgc_status.`)

| What | Key | Encoding |
|---|---|---|
| Power | `e_1002.e_A002.p_01` | `00` = off, `01` = on |
| Mode | `e_1002.e_3001.p_01` | `0000` = fan, `0100` = heat, `0200` = cool, `0300` = auto, `0500` = dry, `0800` = humidify |
| Setpoint, cool | `e_1002.e_3001.p_02` | °C × 2, hex (23 °C → `2e`) |
| Setpoint, heat | `e_1002.e_3001.p_03` | °C × 2, hex |
| Setpoint, auto | `e_1002.e_3001.p_1D` | signed offset × 0.5 |
| Setpoint, dry | `e_1002.e_3001.p_1E` | signed offset × 0.5 |
| Fan speed | `e_1002.e_3001.` `p_09` (cool), `p_0A` (heat), `p_26` (auto), `p_27` (dry), `p_28` (fan), `p_2B` (humidify) | `0A00` = auto, `0B00` = silent, `0300`–`0700` = levels 1–5 |
| Vertical / horizontal swing | `e_1002.e_3001.` `p_05`/`p_06` (cool), `p_07`/`p_08` (heat), `p_20`/`p_21` (auto), `p_22`/`p_23` (dry), `p_24`/`p_25` (fan), `p_29`/`p_2A` (humidify) | 3 bytes: `000000` = stop, `010000`–`0E0000` = position, `0F0000` = swing, `100000` = auto |
| Room temperature | `e_1002.e_A00B.p_06` | signed int16 × 0.5 |
| Room humidity | `e_1002.e_A00B.p_02` | % |
| Outdoor temperature | `e_1003.e_A00D.p_01` (outdoor unit) | signed int16 × 0.5 |
| Compressor frequency | `e_1003.e_2006.p_04` | int |
| Econo / streamer | `e_1002.e_3003.p_24` / `p_20` | flag |
| Quiet / power chill | `e_1003.e_3002.p_3D` / `p_44` | flag; written to `adr_0200` |

- Fan speed and swing each have a separate property per mode.
- Mode values `0900` and `0A00` also appear, but what they mean is unresolved.

Example write: power on, cool, 23 °C, fan auto, swing.
```json
{"requests":[{"op":3,"to":"/dsiot/edges/<ri>/adr_0100.dgc_status",
 "pc":{"pn":"dgc_status","pch":[{"pn":"e_1002","pch":[
   {"pn":"e_A002","pch":[{"pn":"p_01","pv":"01"}]},
   {"pn":"e_3001","pch":[{"pn":"p_01","pv":"0200"},{"pn":"p_02","pv":"2e"},
     {"pn":"p_09","pv":"0A00"},{"pn":"p_05","pv":"0F0000"},{"pn":"p_06","pv":"0F0000"}]}]}]}}]}
```

## Other endpoints

### Main host
- **App config:**
  - `GET /dkapp/app_config_all`: buildings, zones and edge metadata such as filter-replacement records.
  - `/dkapp/edge_meta/...`
- **Buildings and zones:** `/dsiot/buildings/{bId}[/zones|floors/{zId}/edges[/{edgeId}]]`
- **Push notifications:** `/dsiot/terminals`, `/dsiot/subscription`, `/dsiot/adm_notification/subscriptions`
- **Messages:** `/dsiot/message_info/{messages,count_info}/{uuid}/{resource_id}`
- **Terms of use:** `/dsiot/terms_info`
- **Filter-cleaning notifications:** `/dsiot/fcn/{status,reminder/set}`
- **Unit info:** `/api/locinfo`, `/api/machineinfo[/list]`, `/api/weatherinfo`, `/api/faqinfo`, `/api/supportedmodels/list`
- **Deleting a device:** multireq `op:4` on `/dsiot/edges/<id>`
- **Legacy protocol:** GET `/common/device_list_ex` and `/aircon/*` with query parameters, returning `ret=OK,k=v` text.

### Weather host
- `/city?lat=&lon=`
- `/weather-linkage-setting`

### Local adapter (`/config/*`)
Wi-Fi provisioning, in order:
1. `POST /config/system/init`
2. `POST /config/wlan/scan/start`
3. `GET /config/wlan/scan/result`
4. `POST /config/wlan/connect/start` with `{key}`
5. `POST /config/wlan/connect/permit` with `{session,rslt}`
6. `PUT /config/net/settings`

Other adapter endpoints:
- `PUT /config/adapter/lpw` with `{new_lpw}`
- `/config/adapter/{datetime,timezone,user_info}`
- `/config/adapter/look/{start,stop}`
- `POST /config/system/reboot`
- `POST /config/firmware/update` (multipart)

## Open questions
- Mode values `0900` and `0A00`.
- Units of the energy arrays.
- Whether `wlan/connect/start` really sends no SSID.
- Air purifier (`GPFCjDataConverter`) and VRV (`GPFVRVDataConverter`) properties haven't been mapped.
