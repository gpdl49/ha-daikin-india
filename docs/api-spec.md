# Daikin AC (India) app 1.5.2: backend API specification

Target: building a Home Assistant integration for units controlled by the Daikin India "Daikin AC" app (package `in.co.daikin.remoapp`, v1.5.2).

**Provenance.** Everything here is derived from static analysis of the decompiled APK. **None of it has been verified against live traffic.** Items marked **[inferred]** are reasoned from code paths but not directly proven.

**Citation conventions.** `file:line` citations are relative to `jadx/sources/`, with `dknetlib/` = `jp/co/daikin/dknetlib/` and `wwapp/` = `jp/co/daikin/wwapp/`. Obfuscated helpers (`E4/K.java`, `E4/C0030e.java`, `p032e5/*.java`, …) are cited by their jadx path. Smali citations are relative to `decompiled/smali/`; `RaSmali` = `jp/co/daikin/dknetlib/gpf/data/GPFRaDataConverter.smali`. Line numbers for code jadx could not decompile are approximate.

This document supersedes `API.md` (repo root) except for the authentication details, which are still only in `API.md` (see [Authentication](#authentication)).

## Table of contents

- [Quick start for a Home Assistant integration](#quick-start-for-a-home-assistant-integration)
- [Hosts](#hosts)
- [Authentication](#authentication)
- [DSIOT ("GPF") device protocol](#dsiot-gpf-device-protocol)
  - [Transport](#transport)
  - [Request envelope](#request-envelope)
  - [Response envelope](#response-envelope)
  - [Result codes (`rsc`)](#result-codes-rsc)
  - [Path grammar](#path-grammar)
  - [Batching](#batching)
  - [Value encoding](#value-encoding)
- [Adapter-level property maps](#adapter-level-property-maps)
  - [`adp_i` (adapter info, read-only)](#adp_i-adapter-info-read-only)
  - [`adp_d` (adapter settings, read/write)](#adp_d-adapter-settings-readwrite)
  - [`adp_r` (adapter runtime status, read-only)](#adp_r-adapter-runtime-status-read-only)
  - [`adp_f` (firmware settings; requested on the cloud only)](#adp_f-firmware-settings-requested-on-the-cloud-only)
  - [`dev_i` (attached-unit info, read-only)](#dev_i-attached-unit-info-read-only)
  - [Other adapter-level identifiers the app handles](#other-adapter-level-identifiers-the-app-handles)
- [Device discovery](#device-discovery)
  - [Cloud edge list](#cloud-edge-list)
  - [Local UDP discovery](#local-udp-discovery)
  - [Protocol and device-type determination](#protocol-and-device-type-determination)
- [Local adapter `/config/*` API](#local-adapter-config-api)
  - [Wi-Fi provisioning sequence](#wi-fi-provisioning-sequence)
  - [Cloud registration (remote method)](#cloud-registration-remote-method)
  - [Local authentication (`lpw`)](#local-authentication-lpw)
- [Room AC (Ra) DSIOT property map (`dgc_status`)](#room-ac-ra-dsiot-property-map-dgc_status)
  - [Where the data lives](#where-the-data-lives)
  - [Value encoding conventions](#value-encoding-conventions)
  - [Operation mode enum (`e_1002.e_3001.p_01`)](#operation-mode-enum-e_1002e_3001p_01)
  - [`e_1002.e_A002`: power](#e_1002e_a002-power)
  - [`e_1002.e_3001`: operation (mode, setpoints, fan, air direction, humidity)](#e_1002e_3001-operation-mode-setpoints-fan-air-direction-humidity)
  - [Fan speed (`p_09`, `p_0A`, `p_26`, `p_27`, `p_28`, `p_2B`)](#fan-speed-p_09-p_0a-p_26-p_27-p_28-p_2b)
  - [Air direction](#air-direction)
  - [Humidity mode and value](#humidity-mode-and-value)
  - [`e_1002.e_3003`: feature flags and special modes](#e_1002e_3003-feature-flags-and-special-modes)
  - [`e_1002.e_A00B`: indoor sensors](#e_1002e_a00b-indoor-sensors)
  - [`e_1002.e_A001`, `e_A006`, `e_A011`, `e_2016`: identity, capability and status](#e_1002e_a001-e_a006-e_a011-e_2016-identity-capability-and-status)
  - [`e_1003`: outdoor unit (`adr_0200`)](#e_1003-outdoor-unit-adr_0200)
  - [Capability and model-info map](#capability-and-model-info-map)
  - [Error codes](#error-codes)
  - [How the app writes control changes](#how-the-app-writes-control-changes)
  - [Example writes](#example-writes)
  - [Corrections to the existing API.md table](#corrections-to-the-existing-apimd-table)
  - [Remaining unknowns](#remaining-unknowns)
- [Room AC (Ra) auxiliary features over DSIOT](#room-ac-ra-auxiliary-features-over-dsiot)
  - [How the app builds write bodies (applies to every write below)](#how-the-app-builds-write-bodies-applies-to-every-write-below)
  - [Where the data comes from: `expand=ch` versus per-resource reads](#where-the-data-comes-from-expandch-versus-per-resource-reads)
  - [Capability flags (from model info or expand=ch)](#capability-flags-from-model-info-or-expandch)
- [Weekly schedule timer (`scdl_t`)](#weekly-schedule-timer-scdl_t)
  - [Resources](#resources)
  - [`scdl_t.info`](#scdl_tinfo)
  - [`scdl_t.body`](#scdl_tbody)
- [Ventilation (models with a ventilation unit)](#ventilation-models-with-a-ventilation-unit)
- [Patrol (temperature patrol / monitoring)](#patrol-temperature-patrol--monitoring)
- [Energy consumption](#energy-consumption)
- [Electricity unit price and cost target](#electricity-unit-price-and-cost-target)
- [Sensor info, model info, filter sign (resource list)](#sensor-info-model-info-filter-sign-resource-list)
  - [Room AC auxiliary features: open questions](#room-ac-auxiliary-features-open-questions)
- [Device-type identification](#device-type-identification)
- [Air purifier (Cj, `DeviceType.AirCleaner`)](#air-purifier-cj-devicetypeaircleaner)
  - [Identification](#identification)
  - [Resources and requests](#resources-and-requests)
  - [Control properties (`adr_0100.dgc_status`)](#control-properties-adr_0100dgc_status)
  - [Sensors and status (read only)](#sensors-and-status-read-only)
  - [Air-quality history (`adr_0100.history`)](#air-quality-history-adr_0100history)
  - [Schedule timer (`adr_0100.scdl_t`)](#schedule-timer-adr_0100scdl_t)
  - [Legacy (DK) path](#legacy-dk-path)
- [VRV / packaged AC (`PA` edges over GPF)](#vrv--packaged-ac-pa-edges-over-gpf)
  - [Identification: "VRV" means a PA edge, handled as a room AC](#identification-vrv-means-a-pa-edge-handled-as-a-room-ac)
  - [Key map (`adr_0100.dgc_status.` prefix unless noted)](#key-map-adr_0100dgc_status-prefix-unless-noted)
  - [Enums defined for VRV (`dknetlib/core/data/vrvcontrol/`)](#enums-defined-for-vrv-dknetlibcoredatavrvcontrol)
- [Eq: Eco-Cute heat-pump water heater (GPF/DSIOT)](#eq-eco-cute-heat-pump-water-heater-gpfdsiot)
- [Vh: total heat exchanger / ventilation unit (GPF/DSIOT)](#vh-total-heat-exchanger--ventilation-unit-gpfdsiot)
- [Rd: air dryer (legacy Daikin HTTP only, read-only)](#rd-air-dryer-legacy-daikin-http-only-read-only)
- [Cc: circulator fan (legacy Daikin HTTP only)](#cc-circulator-fan-legacy-daikin-http-only)
- [Legacy "Daikin" HTTP protocol (pre-DSIOT adapters)](#legacy-daikin-http-protocol-pre-dsiot-adapters)
  - [When the app uses legacy and when it uses GPF](#when-the-app-uses-legacy-and-when-it-uses-gpf)
  - [Transport](#transport-1)
  - [Cloud legacy device list](#cloud-legacy-device-list)
  - [Local `basic_info` / UDP reply keys](#local-basic_info--udp-reply-keys)
  - [Endpoints](#endpoints)
  - [RA legacy value encodings (`dknetlib/dk/data/DKRaDataConverter.java`)](#ra-legacy-value-encodings-dknetlibdkdatadkradataconverterjava)
- [Other cloud endpoints](#other-cloud-endpoints)
  - [Transport conventions (apply to every call below)](#transport-conventions-apply-to-every-call-below)
  - [Buildings, zones, floors and edge metadata (`GPFMetaDataController`)](#buildings-zones-floors-and-edge-metadata-gpfmetadatacontroller)
  - [Weather host (`app-weather.daikinsmartdb.jp`, `Bearer cd_accessToken`)](#weather-host-app-weatherdaikinsmartdbjp-bearer-cd_accesstoken)
  - [Push notification registration](#push-notification-registration)
  - [Equipment notices / message inbox](#equipment-notices--message-inbox)
  - [Terms of use (`GPFTermOfUseInfoController`)](#terms-of-use-gpftermofuseinfocontroller)
  - [Filter-cleaning notification (FCN), RA only](#filter-cleaning-notification-fcn-ra-only)
  - [`/api/*` (main host)](#api-main-host)
  - [Device name, icon, erase, out-of-home, time](#device-name-icon-erase-out-of-home-time)
  - [Account transfer (legacy account → new account)](#account-transfer-legacy-account--new-account)
  - [Gift codes](#gift-codes)
  - [Firmware updates](#firmware-updates)
  - [Other URL literals](#other-url-literals)
- [Consolidated open questions](#consolidated-open-questions)

## Quick start for a Home Assistant integration

1. **Transport.** Everything device-related goes through one JSON endpoint, `/dsiot/multireq` ("DSIOT", called "GPF" in the app), either on the cloud (`https://prod.daikinacmanager.com`, `Authorization: Bearer <id_token>`) or directly on the adapter (`http://<ip>`, no auth, or `Authorization: Basic <4-digit PIN>` when a lock PIN is set). See [DSIOT ("GPF") device protocol](#dsiot-gpf-device-protocol).
2. **Discovery.** Cloud: `op:2` on `/dsiot/edges?filter_edges=all&mask_oldedges=1&expand=ch`, which returns every edge with its full state. Local: UDP `DAIKIN_UDP/common/basic_info` broadcast to port 30050. See [Device discovery](#device-discovery).
3. **Classify.** `dev_i.type`: `RA` room AC, `PA` VRV/packaged AC, `1D` air purifier, `1C` heat exchanger, `EQ` EcoCute. Legacy (`ret=OK,…` text) protocol only when the local reply's `protocol` is missing/`daikin`/`RS232C`, or the unit appears in the cloud `device_list_ex`. See [Protocol and device-type determination](#protocol-and-device-type-determination).
4. **Poll.** One `op:2` read of `<base>/adr_0100.dgc_status?filter=pv,md` + `<base>/adr_0200.dgc_status?filter=pv,md` (or `expand=ch` on the edge). The app polls every 60 s and after each write.
5. **Control.** `op:3` (HTTP PUT) to `<base>/adr_0100.dgc_status` with the keys from the [Room AC property map](#room-ac-ra-dsiot-property-map-dgc_status), always including `e_1002.e_3003.p_2D` (power-change trigger). Outdoor-unit keys (quiet, power chill) go in a separate PUT to `adr_0200`.
6. **Local ↔ cloud id.** `GET http://<ip>/config/adapter/user_info` returns `resource_id` = the cloud edge `ri`.

## Hosts

| Host | Scheme | Use | Ref |
|---|---|---|---|
| `prod.daikinacmanager.com` | https | Main host: login/refresh/logout (`/premise/dsiot/cognito/*`), `/dsiot/*` (multireq, buildings, notifications…), `/api/*`, `/dkapp/*`, legacy `/common/*`, `/aircon/*` proxy | `dknetlib/dk/data/DKServerInfo.java:32` |
| `prod-clubdaikin.daikinacmanager.com` | https (hard-coded) | Account service (`/authentication/cognito/*`, `/multicountry/*`) | `dknetlib/gpf/net/GPFHttpController.java:447-454` |
| `app-weather.daikinsmartdb.jp` | https (hard-coded) | City lookup, weather-linkage settings | `GPFHttpController.java:456-463` |
| `<adapter-ip>` | http | Local DSIOT (`/dsiot/multireq`), `/config/*`, legacy `/aircon/*`, `/common/*` | `GPFHttpController.java:99-123` |
| `192.168.127.1` | http | Hard-coded only for `POST /config/system/init` (Wi-Fi module reset) | `GPFHttpController.java:115-117` |
| `sha2.daikinonlinecontroller.com` / `test2.daikindev.com` | https | EU prod / EU dev; not used by the India build | `DKServerInfo.java:37-41` |

- **Region selection:** `E4/C0030e` reads SharedPreferences `RemoApp_Preferences` key `region` (default `"in"`) → `DKServerInfo(region, isProduction=true)` (`E4/C0030e.java:148-151,168`). Only `in` → `prod.daikinacmanager.com` and `eu` → `sha2…` are mapped; other regions (`lk, bd, np, bt, cn, th, us`) leave the URL `null` (`DKServerInfo.java:27-43`). The account and weather hosts are not region-dependent.
- **Scheme rule:** requests to a node whose address is `prod.daikinacmanager.com` are https, anything else http (`GPFHttpController.java:99-123`).
- **HTTP client:** `java.net.HttpURLConnection`; headers are only `Content-Type: application/json` plus an optional `Authorization`. No custom User-Agent, API key or request signing. Timeouts 10 s (40 s for `PUT /config/adapter/user_info`, 90 s for firmware upload). A body passed to a GET is silently dropped (`GPFHttpController.java:54-97,125-137,332-445`).
- **Certificate pinning:** none. The network security config trusts user CAs and allows cleartext (`jadx/resources/res/xml/network_security_config.xml`), so mitmproxy with a user-installed CA works.

## Authentication

Login is a Daikin-hosted proxy in front of AWS Cognito. The app never talks to Cognito directly, and no user-pool, identity-pool or region configuration ships in the APK. The username is the phone number in E.164 form, which the UI builds as dial code + number (`+91XXXXXXXXXX`; `LoginFragment.java:2704`).

### Static client values

| Name | Value | Ref |
|---|---|---|
| `client_id` | `7k8koegnvimcqj7i5p933rov73` | `gpf/net/request/common/GPFSessionInfoController.java:171,184,201` |
| `client_secret` | `1upkumrsbds2513lccgi6sfatqji5sk8m7vrb9cqfrg2i7nigu5o` | same, `:173,187,203` |
| `app` (inside encrypted blobs) | `CI000000` | `GPFClubDaikinAutentification.java:62` |
| `uuid` | random UUID generated once per install and stored in prefs key `uuid` | `E4/C0030e.java:159-161` |

### The encrypted `code` blob

Credentials are sent inside an RSA-encrypted blob rather than as plain JSON fields.

1. Build a JSON object. The fields depend on the call; see the table below.
2. Serialize it to UTF-8.
3. Encrypt it with `RSA/ECB/PKCS1Padding` using the 4096-bit public key in `assets/rsa_4096_public_key.pem`. The ciphertext is 512 bytes, so the plaintext must be 501 bytes or less.
4. Base64-encode it (Android `Base64.DEFAULT`) and **strip every `\n`**.

Refs: `gpf/data/RsaCipherHelper.java:30-58`; newline stripping, e.g. `GPFClubDaikinAutentification.java:73`.

PKCS#1 v1.5 padding is randomized, so each blob is different even for identical input. Only the public key is needed to produce valid blobs.

Public key (`assets/rsa_4096_public_key.pem`):
```
-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAm16JWI5m4/sJsZWrq99c
PJqTpOWpscSZlTEWhuctv0ZTYgOqy1BxWmfK5qdqtPKAEBwSUSdGAOdHnDWd8oxi
V78Jwce3myHFwg5ZxSQ+Q4TbwxPOagIGiYHoQJZQr/RjOVhTl8DAGlXIQKLPYX8m
YOAzCL6V9WWIeufi9t7OdjSI8nFNI1F052C40rf7adbNbnf+v98mi56LB0ZvGEX8
T6Pymr5Pefdp0TF7tD/JlJOg4LxXefNR2t4UgRJVnVy9R3xsnskhXI3p5IeCVxTZ
0QOTnKlH6baJx1rJ1rEUPpJhL63ISUoD2ut1EeHrQwSGIDfB2+7txUrEfUUj1Ast
eq3Gzb1UjP1+rWAemqwSSqPRWqU1PiNAKrbN9RdS3iHojEKwTQjzc6RjEFbGeEZ1
0rsMHiAhkR9ivDNDoxKXLmyJrGFNh2Fn02G0/XkI1lSemKSDsNEHGtAp09r1PUNU
94ivXUv6kkj4qzpAGg+Ou/TQ4nUP6FlP6TxNVqW3dhYKs2j48cf2U6Ee34LbAQAv
RuP7TTqNvIGUibw8FJdSiTXKAIrzcU/1W/QCGJWNHCLwhTfNeNiK1T1XYn1dy/3+
TIyrpilSrIalRSmhyGhz9Z6ojc9nsErlo4IfnKiK/FOjIWCHW7FaZMIdqxMJHD+S
tKvHqDvAVxfc7wVdsWzGnAECAwEAAQ==
-----END PUBLIC KEY-----
```

Reference implementation (Python, `cryptography`):
```python
import base64, json, time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

PUBKEY = serialization.load_pem_public_key(open("rsa_4096_public_key.pem", "rb").read())

def encrypt_blob(obj: dict) -> str:
    # Compact JSON is fine; the app uses org.json's toString(), also compact.
    plaintext = json.dumps(obj, separators=(",", ":")).encode()
    return base64.b64encode(PUBKEY.encrypt(plaintext, padding.PKCS1v15())).decode()

def password_code(phone: str, password: str, model: str = "Pixel 7") -> str:
    return encrypt_blob({"phone_number": phone, "password": password, "model": model,
                         "app": "CI000000", "timestamp": str(int(time.time() * 1000))})
```
`base64.b64encode` never inserts newlines, so no stripping step is needed.

Plaintext for each blob (`GPFClubDaikinAutentification.java`):

| Builder (line) | Used by | Plaintext JSON |
|---|---|---|
| `createAuthorizationBody` (50) | password login, account transfer | `{phone_number, password, model, app:"CI000000", timestamp:"<epoch ms>"}` |
| `createNumOTPBody` (163) | OTP login step 1 | `{phone_number}` |
| `createNumOTPVerifyBody` (186) | OTP login step 2 | `{phone_number, sms_otp}` |
| `createRegisterBody` (212) | signup | `{phone_number, email, first_name, last_name, password}` |
| `createVerifyOtpBody` (305) / `createVerifyEmailOtpBody` (279) | signup verification | `{phone_number, otp}` / `{phone_number, email, otp}` |
| `createAuthorizationBodySendOtp` (80) / `verifyPasswordOtp` (673) | forgot password | `{identifier}` / `{identifier, otp}` |
| `createBodyVerifyOtp` (102) | forgot password: set new password | `{username, new_password}` |
| `changePassword` (24) | change password | `{phone_number, current_password, new_password}` |
| `getProfileInfo` (364) | profile | `{internal_id, model, app, timestamp}` |

### Login: password (`auth_type: "PASS"`)

`GPFSessionInfoController.login()` (`:144-206`); called from `LoginFragment.d2("PASS")` (`LoginFragment.java:2245`).
```
POST https://prod.daikinacmanager.com/premise/dsiot/cognito/login
Content-Type: application/json

{"grant_type":"authorization_code",
 "code":"<encrypt_blob({phone_number,password,model,app,timestamp})>",
 "client_id":"7k8koegnvimcqj7i5p933rov73",
 "client_secret":"1upkumrsbds2513lccgi6sfatqji5sk8m7vrb9cqfrg2i7nigu5o",
 "auth_type":"PASS",
 "uuid":"<install uuid>"}
```
The UI always sets `isClubDAIKIN="true"`. The alternative branch, `{"grant_type":"password","user_id":..,"password":..}` in plaintext, is dead code in this build.

### Login: OTP (`auth_type: "OTP"`, then `"VERIFY"`)

**Step 1: trigger the SMS.** The body is the **bare base64 blob, not JSON**, even though the `Content-Type` header says JSON (`configNew` → `postAuth`; `GPFSessionInfoController.java:165-178`). The JSON map built next to it is discarded.
```
POST https://prod-clubdaikin.daikinacmanager.com/authentication/cognito/login_otp_trigger
Content-Type: application/json

<encrypt_blob({"phone_number":"+91XXXXXXXXXX"})>
```
Success is `result_cd == "200"`, and the response includes a `session` string (`LoginFragment.java:2667`; `RunnableC0810v0.java:63`).

**Step 2: verify** (`:180-191`):
```
POST https://prod.daikinacmanager.com/premise/dsiot/cognito/login
{"grant_type":"authorization_code",
 "code":"<encrypt_blob({phone_number, sms_otp})>",
 "client_id":"…","client_secret":"…",
 "auth_type":"OTP","cd_session":"<session from step 1>","uuid":"<install uuid>"}
```

### Login response

- **Success:** the app treats the presence of `access_token` as success (`LoginFragment.java:2586`).
- **Stored:** `GPFSessionInfo.createSessionInfo` (`gpf/data/GPFSessionInfo.java:29-35`) keeps these fields:

| Field | Use |
|---|---|
| `id_token` | `Authorization: Bearer` for the main host |
| `refresh_token` | refresh and logout |
| `uid` | user id; `/dsiot/terms_info/{uid}` |
| `cd_accessToken` | `Authorization: Bearer` for the account and weather hosts |
| `cd_refreshToken`, `cd_user_uuid` | refresh |
| `cd_expiresIn` | lifetime in seconds (parsed with `Integer.parseInt`, so it is an integer or an integer string) |

- **Profile fields:** `firstName`, `lastName`, `email`, `telephoneNumber` and `internal_id` are also read (`LoginFragment.java:2588-2592`). `access_token` itself is never stored.
- **Errors:** the message is in `body` or `message` (`LoginFragment.java:2670-2676`). `rsc` 401 or 4001 means `ACCOUNT_NG`, 4105 means `ACCOUNT_MIGRATED` (see [Result codes](#result-codes-rsc)).

Example (shape only):
```json
{"access_token":"…","id_token":"<JWT>","refresh_token":"…","uid":"…",
 "cd_accessToken":"…","cd_refreshToken":"…","cd_expiresIn":3600,"cd_user_uuid":"…",
 "firstName":"…","lastName":"…","email":"…","telephoneNumber":"+91…","internal_id":"…"}
```

### Token refresh

`GPFRefreshSessionTokenController.refreshToken()` (`:127-167`):
```
POST https://prod.daikinacmanager.com/premise/dsiot/cognito/token
Authorization: Bearer <current id_token>
{"grant_type":"refresh_token","refresh_token":"…","cd_refreshToken":"…","cd_user_uuid":"…"}
```
- **Response:** the same fields as the login response. The app replaces the whole session with it. If the response has no `uid`, the previous one is kept (`E4/J.java:33-44`).
- **When it refreshes:** proactively, whenever `lastUpdateTime + cd_expiresIn <= now`. The check runs before each cloud request; requests are queued and replayed after a successful refresh (`E4/K.java:104-118`, `E4/J.java`).
- **No reactive refresh:** a 401 does not trigger a refresh.
- **Duplicates:** a second refresh within 60 s is suppressed.

### Logout

```
POST https://prod.daikinacmanager.com/premise/dsiot/cognito/logout
{"token":"<refresh_token>"}
```
It is sent without an `Authorization` header (`GPFSessionInfoController.java:208-216`; `MainActivity.java:664-678`).

### Other account endpoints (account host; body is a bare encrypted blob)

All of these are `POST https://prod-clubdaikin.daikinacmanager.com/authentication/cognito/<name>`, with `Authorization: Bearer <cd_accessToken>` when logged in:
- **Signup:** `signup`, `signup_verify_mobileotp`, `signup_verify_emailotp`, `signup_update_email_trigger_otp`
- **Forgot password:** `forgot_password_trigger_otp`, `forgot_password_verify_otp`, `forgot_password_update_pass`
- **Account changes:** `update_password`, `update_profile_name` (JSON `{first_name,last_name}`)
- **Account deletion OTP:** `mobile_otp_trigger`
- **Contact changes:** `email_mobile_trigger_otp`, `email_mobile_verify_otp`, `new_email_trigger_otp`, `new_email_verify_otp`, `new_mobile_trigger_otp`, `new_mobile_verify_otp`

Two GET endpoints on the same host: `get_user_profile`, and `/multicountry/get_supported_countries`.

Account deletion is `POST /premise/dsiot/cognito/delete` on the main host with `{cd_phoneNumber, otp, cd_accessToken, token:<refresh_token>, reason}`.

### Integration notes

- **Login mode:** a Home Assistant integration only needs password login plus refresh. OTP login is an optional alternative config flow.
- **Other session usage:** Daikin may limit concurrent sessions per account; this is unverified. Test whether logging in from HA logs out the phone app.
- **Cloud linking on the adapter:** the adapter's own cloud link (`PUT /config/adapter/user_info {method, id_token}`) is a separate concern. See [Cloud registration](#cloud-registration-remote-method).

### Token and credential usage

How the rest of this spec uses each token or credential (verified in the sections cited):

| Target | Header | Ref |
|---|---|---|
| Main host `prod.daikinacmanager.com` (GPF stack: `/dsiot/*`, `/api/*`, `/dkapp/*`) | `Authorization: Bearer <id_token>` | `GPFHttpController.java:54-73` |
| Main host, legacy `/common/*`, `/aircon/*` proxy | `Authorization: <id_token>` (raw, **no** `Bearer ` prefix), plus literal query `id=ID&spw=SPW` | `dknetlib/dk/net/http/a.java:73-79` |
| Account host / weather host | `Authorization: Bearer <cd_accessToken>` | `GPFHttpController.java:75,447,456` |
| Local adapter (DSIOT and `/config/*`) | `Authorization: Basic <PIN>` (literal PIN, not base64), only when a lock PIN is set | `GPFHttpController.java:54-73` |
| Local adapter, legacy protocol | query parameter `lpw=<PIN>` when set; no headers | `dknetlib/dk/net/http/a.java:66-72` |
| Adapter cloud registration | Cognito `id_token` in the body of `PUT /config/adapter/user_info` | [Cloud registration](#cloud-registration-remote-method) |

- A per-install random UUID is kept in prefs key `uuid` (`E4/C0030e.java:159`).
- HTTP 401 on the cloud is surfaced as `rsc` 401 (`ACCOUNT_NG`); see [Result codes](#result-codes-rsc).

## DSIOT ("GPF") device protocol

Code references are relative to `jadx/sources`. `dknetlib/` means `jp/co/daikin/dknetlib/` and `wwapp/` means `jp/co/daikin/wwapp/`. Items marked **[inferred]** are reasoned from the code but not verified directly.

The app calls this protocol "GPF". Classes live under `dknetlib/gpf/**`, and `ProtocolType.GPF` is spelled `gpf` or `DGC` on the wire. The same JSON protocol serves two places:

- the cloud, through `https://prod.daikinacmanager.com`
- the adapter itself on the LAN, through `http://<ip>`

The only differences are the base path and the authentication.

### Transport

| | Cloud | Local adapter |
|---|---|---|
| URL | `https://prod.daikinacmanager.com/dsiot/multireq` | `http://<adapter-ip>/dsiot/multireq` |
| Base path in `to` | `/dsiot/edges/<ri>` | `/dsiot/edge` |
| Auth header | `Authorization: Bearer <id_token>` | `Authorization: Basic <lpw>`, only when a lock PIN is set (see [Local auth](#local-authentication-lpw)) |
| Scheme choice | `https` only when the host string contains `prod.daikinacmanager.com`; everything else is `http` | |

Sources: `GPFBaseController.setup()` in `dknetlib/gpf/net/GPFBaseController.java:797-843`, and `GPFHttpController.createUri()` / `createHeader()` in `dknetlib/gpf/net/GPFHttpController.java:54-123`.

**Headers.** Every request carries `Content-Type: application/json` plus at most one `Authorization` header (`GPFHttpController.java:54-73`).

- If the node's auth map holds both `id_token` and `lpw`, the header built last wins, because it is a HashMap put. In practice cloud nodes only carry `id_token` and local nodes only carry `lpw`.
- There is no `Accept`, no `User-Agent` override and no request signing.

**Request methods.** The HTTP method depends on which helper builds the request, not on `op` (`GPFBaseController.java:520-789`).

| Helper | HTTP method | Used for |
|---|---|---|
| `multiGet` | **POST** `/dsiot/multireq` | every `op:2` read |
| `multiSet` / `set` | **PUT** `/dsiot/multireq` | every `op:3` write; also PUT on `/config/*` |
| `config` | **POST** | `op:4` delete of an edge (`GPFEraseDeviceController`), plus POST on `/config/*` |
| `get` | **GET** | `/config/*` reads |
| `delete` | **DELETE** | only non-multireq REST paths such as `/dsiot/buildings/.../edges/<id>` (`gpf/ctrl/GPFMetaDataController.java:617`) |

**Timeouts, threads and retries** (`GPFHttpController.java:125-174, 320-445, 465-491`):

- Connect and read timeouts are both 10 000 ms by default. `PUT /config/adapter/user_info` uses 40 000 ms (`GPFRemoteMethodSettingController.java:71`). The firmware multipart upload uses 90 000 ms.
- Requests to `prod.daikinacmanager.com` go through a shared fixed thread pool.
- Each local adapter address gets its own **single-thread executor**, so the app never has two requests in flight to one adapter. Clients should do the same **[inferred: firmware likely handles only one connection at a time]**.
- There is **no automatic retry** at the HTTP layer.

**Synthesized error responses.** The app never raises an HTTP error to callers. It always hands a JSON string to the parser (`GPFHttpController.java:362-445`):

- **HTTP 200:** the body is used as-is.
- **HTTP 401, 404, 500, 503:** the body is replaced with `{"responses":[{"rsc": <http status>}]}`.
- **Other non-200 status:** the error-stream body is used; if it is empty, the app uses `{"responses":[{"rsc": <status>}]}`.
- **Exception or timeout with no status:** `{"responses":[{"rsc": 6000}]}`. The code 6000 is purely client-side.

### Request envelope

Each HTTP request carries exactly one JSON object with a `requests` array. The app batches several reads into one POST; see [Batching](#batching). JSON is written by Gson with HTML escaping disabled and **nulls omitted** (`GPFBaseController.java:458-465, 583-588`).

```json
{"requests":[{"op":2,"to":"/dsiot/edges/<ri>.adp_i?filter=pv"}]}
```

| Field | Type | Meaning |
|---|---|---|
| `op` | int | Operation, from the table below |
| `to` | string | Target resource path; see [Path grammar](#path-grammar) |
| `pc` | object | Payload ("primitive content"). Writes only |
| `rqi` | string | Request id. Only sent by the delete request, as the literal `"1"`. It is declared on writes but always null, so it is omitted |

Op codes. Only three are used anywhere in the app, and there is **no op 1 (create)**:

| `op` | Meaning | HTTP method | Where |
|---|---|---|---|
| 2 | Retrieve | POST `/dsiot/multireq` | `GPFBaseController.createJson(..., true)` `:580-588`, and every `Requests(2, …)` |
| 3 | Update | PUT `/dsiot/multireq` | `createJson(..., false)` `:577-578`. The default op of `RequestsWithParam` is 3 (`:883`) |
| 4 | Delete | POST `/dsiot/multireq` | `GPFEraseDeviceController.DeleteRequest` (`:84` defaults `op=4`, `rqi="1"`) |

**Write payload.** The code takes a flat map of dotted keys and turns it into a tree (`createMap` `:217-266`, `createPch` `:268-281`, `getJsonForRequest` `:438-466`).

- Each dot-separated segment becomes a node of `{"pn":…, "pch":[…]}`, and each leaf becomes `{"pn":…, "pv":…}`.
- **`pt` is never sent in requests.** It is declared but null.
- There is one `requests[]` entry per top-level segment, and all of them share the same `to`. In practice there is always exactly one top-level segment, such as `dgc_status` or `adp_d`, so the payload has one entry.
- A leaf `pv` is a JSON string, or a JSON number when the controller converted it with `Integer.parseInt`. The number case applies to the adapter-level integer keys marked "int" in the tables below.

```json
{"requests":[{"op":3,"to":"/dsiot/edge.adp_d",
  "pc":{"pn":"adp_d","pch":[{"pn":"notify","pch":[
     {"pn":"auto_off_flg","pv":1},{"pn":"auto_off_tm","pv":"0200"}]}]}}]}
```

That example is `GPFNotifyInfoController.set` (`gpf/net/request/common/GPFNotifyInfoController.java:47-79`); the `auto_off_tm` value is illustrative. The device-status write has the same shape, with `to` = `<base>/adr_0100.dgc_status` and `pc.pn` = `"dgc_status"`.

**Delete request** (`GPFEraseDeviceController.java:43-47, 63-107`). The body is POSTed to `/dsiot/multireq` on the cloud host:

```json
{"requests":[{"op":4,"to":"/dsiot/edges/<ri>","rqi":"1"}]}
```

This removes the edge from the user's account. It is also sent automatically after switching the adapter to `home_only`; see [Cloud registration](#cloud-registration-remote-method).

### Response envelope

```json
{"responses":[
  {"fr":"/dsiot/edge.adp_i","rsc":2000,
   "pc":{"pn":"adp_i","pt":1,"pch":[
      {"pn":"mac","pt":3,"pv":"AABBCCDDEEFF"},
      {"pn":"func","pt":1,"pch":[{"pn":"en_scdltmr","pt":3,"pv":1}]}]}}]}
```

The values in this example are illustrative.

| Field | Meaning |
|---|---|
| `fr` | "from", which echoes the `to` path |
| `rsc` | Response status code; must be an int |
| `pc` | Content node (`pn`, `pt`, and either `pv` or `pch`) |
| `pn` | Property name |
| `pt` | Property type (see below). **Required on every response node** |
| `pv` | Value. Only on leaves |
| `pch` | Child array. Only on containers |
| `md` | Metadata. Only on leaves, and only when requested with `filter=…md` |

**`pt` values.** The parser treats `pt == 1` as a container and recurses into `pch`. It treats **2 and 3** as leaves and reads `pv` (`parsePch` `:488-518`). Inside `createPchElementMap`, any `pt` other than 1 is read as a leaf (`:318`). No other `pt` values are referenced. Presumably 2 and 3 are two leaf kinds, for example read-only vs read/write or string vs binary **[inferred]**. The app does not distinguish them.

**`md` metadata.** The parser copies every `md` field into the flat map as `<path>.md.<field>` (`:338-411`). `md` must itself contain `pt`; otherwise the parse fails.

| Field | Meaning |
|---|---|
| `md.pt` | Required; value unused |
| `md.st` | Step. A **JSON integer 0–255** in decimal, parsed with `Integer.parseInt` in `GPFDataConverter.decodeStepValue` (`dknetlib/gpf/data/GPFDataConverter.java:814-831`). See [md.st](#mdst-step-encoding) |
| `md.mi`, `md.mx` | Min and max, as **hex strings in the same little-endian encoding as `pv`**. For example, the RA converter parses `md.mx` with `Integer.parseInt(convertByteData(v),16)`, where `convertByteData` reverses byte order (`GPFRaDataConverter.java:1211-1259`) |
| `md.type`, `md.point`, `md.cycle`, `md.path` | History descriptors. Only used by the air-purifier `history` resources (`GPFCjDataConverter.java:514-531`): `type`, `point` and `cycle` are ints; `path` is a string |

**Flattening.** The app never uses the tree directly (`GPFBaseController.getMapForResponse(String)` `:905-1080`; the jadx output is garbled there, so this was read from smali, `decompiled/smali/.../GPFBaseController.smali:2167-2733`).

- It flattens every response into one `HashMap<String,String>`, with keys joined by `.` starting from `pc.pn`. For example `dgc_status.e_1002.e_3001.p_01` and `adp_i.func.en_scdltmr`.
- **`fr` is not part of the key.** When one batch reads both `adr_0100.dgc_status` and `adr_0200.dgc_status`, their subtrees merge into one `dgc_status.*` namespace. Indoor uses `e_1002…` and outdoor uses `e_1003…`, so the keys do not collide.
- A `pv` that is a JSON array or object is stored as its JSON text. `null` is stored as `""`.

**Overall result code.** The flattener computes one result code for the whole batch and stores it as `map["rsc"]`:

1. The running result starts at `"2000"`.
2. A response whose `rsc` is missing, null or not an int sets the result to `INVALID_DATA`.
3. A response with `rsc` starting `"200"` is parsed and merged.
4. A response with `rsc == 4004` whose `fr` does not contain `adp_i`, `adp_d`, `dev_i`, `adp_r` or `dgc_status` is still parsed, so optional resources can be absent without failing the batch.
5. Any other non-`200x` `rsc` sets the running result to that code.
   - **Quirk:** if the failing response's `fr` contains `adp_r`, the running result is **reset to `2000`**, so an `adp_r` failure never fails a batch.
6. A malformed `pc` sets `INVALID_DATA`.

**Top-level `rsc` without `responses`.** If the body has no `responses` key, which is the case for `/config/*`, the top-level `rsc` is used and every other top-level key is copied into the map as `String.valueOf(value)`. Nested objects become JSON text.

**Edge objects** (`expand=ch`, see [Device discovery](#device-discovery)) use `getMapForResponse(JsonElement)` (`:667-697`). It flattens the edge's `pch[]` and then every `ch[i].pch[]`. If either `pch` or `ch` is missing, the result is `INVALID_DATA`.

### Result codes (`rsc`)

These come from `ResultType.toTypeFromGPFCode` (`dknetlib/core/data/ResultType.java:108-152`). The second argument is `isRemote`.

| `rsc` | `ResultType` | Notes |
|---|---|---|
| 2000, 2001, 2002, 2003, 2004 | OK | The parser treats any string beginning with `200` as success |
| 4000 | PARAM_NG | Bad parameter. The client also produces this when JSON parsing fails (`GPFBaseController.java:557`) |
| 401, 4001 | ACCOUNT_NG (cloud) / LPW_NG (local) | Bad token (cloud) or bad lock PIN (local) |
| 4003 | FORBIDDEN | |
| 404, 4004 | NOT_FOUND | Tolerated for optional resources (see above) |
| 4009 | LOCK_NG | |
| 4105 | ACCOUNT_MIGRATED | |
| 4109 | NOT_EXISTS | |
| 4110 | REACH_MAX | e.g. too many registered edges or terminals **[inferred]** |
| 4234 | AUTO_UPDATING | The adapter is doing a firmware auto-update |
| 500 | INTERNAL_SERVER_ERROR | HTTP status mapped through |
| 503 | SERVER_MAINTENANCE | HTTP status mapped through |
| 5000 | INTERNAL_NG | |
| 5107 | DEVICE_NOT_CONNECTED | The cloud cannot reach the adapter |
| 6010 | SERIAL_IF_FAILURE | Adapter to indoor-unit serial link failed |
| 6000 | UNKNOWN | Client-side: no HTTP response |
| `INVALID_DATA` | INVALID_DATA | Client-side: the response did not parse |
| anything else | UNKNOWN | |

The edge-list search also looks at the prefix of `responses[0].rsc`: `500…`, `503…` and `401…` produce the matching error, and anything else ends the search (`gpf/net/GPFRemoteSearchController.java:447-512`).

### Path grammar

```
to        := base [ "/" object ] "." resource [ "." sub ]* [ "?" query ]
base      := "/dsiot/edges/" ri        ; cloud
           | "/dsiot/edge"             ; local
object    := "adr_0100"                ; indoor unit
           | "adr_0200"                ; outdoor unit
resource  := "adp_i" | "adp_d" | "adp_r" | "adp_f" | "dev_i"      ; adapter-level (no object)
           | "dgc_status" | "i_power" | "history" | "price" | "target"
           | "scdl_t" | "patrol"                                   ; unit-level
query     := "filter=" ("pv" | "pv,md")
```

Other forms:

- The whole edge is addressed as `to: "/dsiot/edges/<ri>?expand=ch"` on the cloud, or `to: "/dsiot/edge"` locally (`gpf/net/request/GPFExpandChController.java:27-37`).
- The account's edge list is `/dsiot/edges?filter_edges=all&mask_oldedges=1&expand=ch` (`GPFRemoteSearchController.java:537`).

**Addresses.** Only two object addresses exist in the app, and both are hard-coded.

- Every `GPFDevice` gets `GPFObject(<ri or "">, "adr_0100")` and `GPFObject(<ri or "">, "adr_0200")` (`GPFRemoteSearchController.java:248-249, 389-390`; `p032e5/b.java:471-472, 518-519`).
- `setup()` picks the "indoor" object as the first address starting `adr_01` and the "outdoor" one as the first starting `adr_02` (`GPFBaseController.java:833-841`).
- No other `adr_XXXX` is requested anywhere.

| Address | Meaning | Resources used by the app |
|---|---|---|
| (none) | adapter/edge | `adp_i`, `adp_d`, `adp_r`, `adp_f` (cloud only), `dev_i` |
| `adr_0100` | indoor unit | `dgc_status`, `i_power.week_power`, `i_power.year_power`, `price`, `target`, `scdl_t.body`, `scdl_t.info`, `patrol.{setting,status,spec,notify}`, `history` (air purifier) |
| `adr_0200` | outdoor unit | `dgc_status`, `history.h_01.data` (monthly energy) |

Sources for the unit-level resources: `gpf/net/request/**`, including `airconditioner/GPFPowerConsumptionOf{Week,Year,Month}.java:24`, `GPFElectricityUnitPriceController.java:28`, `GPFTargetElectricityPriceController.java:28`, `common/GPFScheduleTimerController.java:30-43`, `airconditioner/GPFPatrolController.java:55-65`, and `GPFCjAirQualityController.java:25`.

**Query options.** Only `?filter=pv` and `?filter=pv,md` appear.

- `filter=pv` returns values only.
- `filter=pv,md` adds `md`.
- A read with no query, such as `/dsiot/edge.adp_d` in `GPFNotifyInfoController.java:30`, is also valid. It probably returns the full node **[inferred]**.
- The list-level parameters `filter_edges=all`, `mask_oldedges=1` and `expand=ch` are only used on `/dsiot/edges`.

### Batching

A batch is one POST carrying several `op:2` entries. Some real batches:

| Controller | Entries |
|---|---|
| `GPFBasicInfoController` | `.adp_i?filter=pv`, `.adp_d?filter=pv`, `.adp_r?filter=pv`, `.dev_i?filter=pv`, `/adr_0100.dgc_status?filter=pv`, plus `.adp_f?filter=pv` on the cloud only (`common/GPFBasicInfoController.java:31-39`) |
| `GPFModelInfoController` | `.adp_i`, `.dev_i`, `/adr_0100.dgc_status?filter=pv,md`, `/adr_0200.dgc_status?filter=pv,md` (`airconditioner/GPFModelInfoController.java:30`) |
| `GPFControlInfoController` (get) | both `dgc_status?filter=pv,md` (`:50`) |
| Cj / Eq | the five-entry "basic" set with `dgc_status?filter=pv,md` |
| Vh | the same set plus outdoor `dgc_status` |

```json
{"requests":[
 {"op":2,"to":"/dsiot/edge.adp_i?filter=pv"},
 {"op":2,"to":"/dsiot/edge.adp_d?filter=pv"},
 {"op":2,"to":"/dsiot/edge.adp_r?filter=pv"},
 {"op":2,"to":"/dsiot/edge.dev_i?filter=pv"},
 {"op":2,"to":"/dsiot/edge/adr_0100.dgc_status?filter=pv"}]}
```

Writes are never batched with reads, and each write request targets exactly one resource.

### Value encoding

**`dgc_status` and other unit-level `p_XX` values** are hex strings, **little-endian**.

- `GPFDataConverter.convertEndian` and `convertByteData` reverse the byte pairs before `Integer.parseInt(…,16)` (`GPFDataConverter.java:424-467`). For example `"2e"` is 46, and `"0A00"` is 0x000A.
- Signed values are two's-complement on the field width; the per-property handling is in the RA/VRV converters.

**Strings inside `dgc_status`** (model name `e_1002.e_A001.p_01`, model number `p_02`) are ASCII.

- **The hex bytes are reversed before decoding.** Each non-`00` byte becomes one `char`, and the result is trimmed (`convertHexToStringWithoutNull`, `:496-508`, used by `decodeBasicInfo` `:596-617`).
- So a string is stored little-endian like a number, NUL-padded, and only 7-bit/Latin-1 characters survive.
- Error codes use the same scheme, and a trailing `-` is stripped (`convertErrorCode` `:469-494`).

**Adapter-level values** (`adp_*`, `dev_i`) are **not** hex. The app copies `pv` through unchanged (`GPFDataConverter.decode` `:1114-1131`), and writes send plain JSON strings or ints. Types per key are in the [adapter property maps](#adapter-level-property-maps).

- `adp_d.name` is **URL-decoded (UTF-8) on read** (`GPFRemoteSearchController.java:360`, `p032e5/b.java:360-375`), but the rename flow writes the raw text (`wwapp/view/unitlist/EditUnitInfoFragment.java:1029-1035`). Writers should percent-encode for compatibility **[inferred]**.

#### md.st step encoding

`st` is one byte, given as a decimal JSON int (`GPFDataConverter.java:374-411, 814-831`).

- The low nibble `m` is the mantissa.
- The high nibble `e` picks the multiplier: `e` = 0–7 gives ×10^e, and `e` = 8–15 gives ×10^-(16-e). So 8 is 1e-8 and 15 is 0.1.
- For example `st = 0xF5 = 245` means 5 × 0.1 = **0.5**, and `st = 0x01` means **1**.
- Decode with `raw × step`, rounding down (`decodeByStepValue` `:620-631`). Encode with `value ÷ step`, rounding down (`encodeByStepValue` `:944-954`).
- A step of 0 or a non-integer leaves the value unchanged.

## Adapter-level property maps

**Sources.**

- Names come from `dknetlib/gpf/data/GPFConvertValue.java:9-64`, which is the DSIOT key ↔ legacy "DK" key table. The legacy names are what the rest of the app uses, and they match the legacy `/common/basic_info` keys.
- Extra keys come from `GPFRaConvertValue.java:44,124-125`, `GPFCjConvertValue.java:59`, `GPFVRVConvertValue.java:43,123-124` and `GPFRaDataConverter.java:7937-7961`.

**How they are read.** They are read with `?filter=pv` in the basic-info batch. On the cloud they also arrive in the edge list (`expand=ch`).

**How they are written.** Writes use `op:3` / PUT to `<base>.adp_d` or `<base>.adp_f`, with `pc.pn` equal to the resource name. Values are plain JSON: a string unless the table says **int**, in which case the controller sends a JSON number.

### `adp_i` (adapter info, read-only)

| Key | DK name | Meaning / encoding |
|---|---|---|
| `adp_i.kind` | `adp_kind` | Adapter hardware generation, a string code: `"0"` GainSpan, `"1"` STMicroWired, `"2"` STMicroWireless, `"3"` MarvellWireless, `"4"` Generation4 (the India adapters **[inferred]**), other values → Others (`dknetlib/dk/data/DKAdapterType.java:7-39`). Firmware upload is only offered for `"4"` (`GPFFWUploadController.java:112`) |
| `adp_i.ver` | `ver` | Firmware version with `_` separators, e.g. `3_10_0` (the bundled OTA lives in `assets/Generation4/3_10_0/DKWL4G_OTA_CS_V3_10_0.bin`). Parsed by `DKVersionInfo` and shown with `.` (`dknetlib/k.java:62`) |
| `adp_i.rev` | `rev` | Firmware revision |
| `adp_i.reg` | `reg` | Region code. Lower-cased by the app; defaults to `in` when missing (`GPFBasicInfoController.java:42-53`). The discovery filter requires it to equal the app region (`in`) |
| `adp_i.mac` | `mac` | Adapter MAC (format not checked by the app) |
| `adp_i.ssid` | `ssid` | The adapter's own AP SSID, `DaikinAP*****` **[inferred from `res/values/strings.xml` `ssid_output`]** |
| `adp_i.enlv` | `enlver` | ECHONET Lite version |
| `adp_i.edid` | `edid` | Edge id. Used to match a LAN-discovered Generation4 adapter to its cloud edge (`DKNode.isSame`, `dknetlib/dk/data/DKNode.java:245-275`). Relation to `ri` not confirmed **[inferred]** |
| `adp_i.func.en_scdltmr` | `en_scdltmr` | `1` = schedule timer supported (`GPFRaDataConverter.decode` case 1) |
| `adp_i.func.en_ipower` | — | `1` = power (kWh) metering supported; gates `elec` (`GPFRaDataConverter.java:7937`) |
| `adp_i.func.en_ipw_sep` | — | `1` = separate cool/heat power counters (`GPFRaDataConverter.java:7961`) |

### `adp_d` (adapter settings, read/write)

| Key | DK name | R/W | Meaning / encoding | Writer |
|---|---|---|---|---|
| `adp_d.name` | `name` | RW | Unit name. URL-decoded on read (see above) | `GPFDeviceNameController` → PUT multireq `.adp_d` (`:52`) |
| `adp_d.icon` | `icon` | RW, **int** | Icon index | `GPFDeviceIconController` (`:52-58`) |
| `adp_d.location` | `location` | R | Location (install place) | — |
| `adp_d.led` | `led` | RW, **int** | Adapter LED enabled (`1`) | `GPFAdapterLedSettingController` (`:52-58`) |
| `adp_d.disp_ssid` | `disp_ssid` | R (written via `/config`) | "SSID (DaikinAP***) output" while connected to a router. Per the UI code, `"1"` shows the switch OFF and `"0"` shows it ON (`wwapp/view/settings/UnitSettingsFragment.java:240-247, 471`). Written with `PUT /config/wlan/setting_ssid` | `GPFSsidOutputSettingController` |
| `adp_d.holiday` | `en_hol` | R | Holiday mode enabled | — |
| `adp_d.datetime` | `cur` | R | Adapter clock | — |
| `adp_d.timz.dst` | `dst` | R | DST flag | written via `/config/adapter/timezone` |
| `adp_d.timz.zone` | `zone` | R | Time-zone index (India = 396; see below) | same |
| `adp_d.notify.auto_off_flg` | `auto_off_flg` | RW, **int** | Auto-off notification enabled | `GPFNotifyInfoController` (`:60-79`) |
| `adp_d.notify.auto_off_tm` | `auto_off_tm` | RW | Auto-off time | same |
| `adp_d.group.ena` | `en_grp` | R | Grouping enabled | — |
| `adp_d.group.name` | `grp_name` | R | Group name | — |
| `adp_d.method` | `method` | R | Remote-access method: `polling` = cloud / out-of-home enabled; `home_only` = LAN only. Written with `PUT /config/adapter/user_info`. The app treats `method=="polling"` as "out-of-home enabled" (`p032e5/b.java:335-342`) | `GPFRemoteMethodSettingController` |
| `adp_d.lpw_flag` | `lpw_flag` | R | `1` = a local lock PIN is set (`wwapp/view/unitlist/BaseCreateUnitElement.java:455`) | — |
| `adp_d.adp_mode` | `adp_mode` | R | `run` (station), `ap` (AP only) or `ap_run` (`p032e5/b.java:209-315`; `wwapp/view/setupwizard/WlanConnectionsFragmentForSTMicro.java:90`) | — |

### `adp_r` (adapter runtime status, read-only)

| Key | DK name | Meaning |
|---|---|---|
| `adp_r.wlan_info.rssi` | `rssi` | Wi-Fi RSSI (dBm) |
| `adp_r.err_info.con_ltime` | `con_ltime` | Last time the adapter connected to the unit (RA/VRV) |
| `adp_r.err_info.discon_ltime` | `discon_ltime` | Last time the adapter disconnected from the unit |

Errors on `adp_r` are ignored when computing the batch `rsc` (see above).

### `adp_f` (firmware settings; requested on the cloud only)

| Key | DK name | R/W | Meaning |
|---|---|---|---|
| `adp_f.auto_update` | `auto_update` | RW, **int** | Automatic firmware update enabled. If the key is absent, the app hides the option (`GPFRemoteSearchController.java:311-316`). Written by `GPFFwAutoUpdateController` → PUT multireq `.adp_f` (`:52-58`) |

### `dev_i` (attached-unit info, read-only)

| Key | DK name | Meaning |
|---|---|---|
| `dev_i.type` | `type` | **Device-type code. This decides the device class on the cloud**; see [Device type](#protocol-and-device-type-determination). Known values: `RA`, `PA` (room AC), `1D` (air purifier), `1C` (all-heat exchanger), `EQ` (EcoCute), `NA` (common adapter), `GPF` |
| `dev_i.pver` | `pv` | Protocol version. The app ignores the value and hard-codes `pv=3.40`, `cpv=3`, `cpv_minor=40` (`GPFDataConverter.decodeProtocolVersion` `:807-812`) |
| `dev_i.comm_err` | `err` | Adapter to unit communication error. RA and VRV override the decoding in `decodeError` (`GPFRaDataConverter.java:9285+`); the base class forces `err=0` |

### Other adapter-level identifiers the app handles

| Key | Where | Meaning |
|---|---|---|
| `dgc_status.e_1002.e_A001.p_01` / `p_02` | indoor `dgc_status` | Model name and model number, as reversed-hex ASCII (`GPFConvertValue.java:63-64`) |
| `isLock` | request param only | `1` → `POST /config/adapter/look/start`, else `…/stop` (`E4/K.java:842-850`) |
| `new_lpw` | `/config/adapter/lpw` body | New lock PIN |
| `wifi_setting.*`, `nw_setting.*`, `wifi_scan.*` | GPFConvertValue only | Legacy aliases. The `/config/*` bodies actually use the bare names (`ssid`, `key`, `auto_ip`, …) because the GPF encoder passes `DKNetNetworkInfo` maps through untouched (`GPFDataConverter.encode` case 45, `:870-898`) |

## Device discovery

### Cloud edge list

The app runs this search when logged in (`GPFRemoteSearchController.search`, `:514-545`).

```
POST https://prod.daikinacmanager.com/dsiot/multireq
Authorization: Bearer <id_token>
{"requests":[{"op":2,"to":"/dsiot/edges?filter_edges=all&mask_oldedges=1&expand=ch"}]}
```

The response is `responses[0].pc`, a **JSON array** of edge objects (`:447-470`). The fields are:

```json
{"responses":[{"fr":"/dsiot/edges","rsc":2000,"pc":[
  {"ri":"<edge id>","cnst":1,"lt":"<last-seen timestamp>",
   "pch":[ {"pn":"adp_i","pt":1,"pch":[…]}, {"pn":"adp_d","pt":1,"pch":[…]},
           {"pn":"adp_r","pt":1,"pch":[…]}, {"pn":"adp_f","pt":1,"pch":[…]},
           {"pn":"dev_i","pt":1,"pch":[…]} ],
   "ch":[ {"pch":[{"pn":"dgc_status","pt":1,"pch":[…]}, …]},
          {"pch":[{"pn":"dgc_status","pt":1,"pch":[…]}, …]} ]}
]}]}
```

The exact members of `pch` and `ch` are **[inferred]**. The app only requires that `pch` and `ch` exist and flattens them without caring about their order.

| Edge field | Parsed at | Meaning |
|---|---|---|
| `ri` | `:219` | Resource id of the edge. Used as `<ri>` in `/dsiot/edges/<ri>`, and stored as auth `port` / `resource_id` |
| `cnst` | `:237-245` | Connection state. `1` (or missing / unparseable) = connected; any other int = offline |
| `lt` | `:460` | Last-transition time. Stored as the node's "disconnect time" and shown for offline units. Format not checked |
| `pch[]` | `GPFBaseController.java:673-680` | Adapter-level resources, flattened to `adp_i.*`, `adp_d.*`, `adp_r.*`, `adp_f.*`, `dev_i.*` |
| `ch[].pch[]` | `:681-691` | Child objects (`adr_0100`, `adr_0200` **[inferred]**). Their resources are flattened too, e.g. `dgc_status.*`. The child's own id/address fields are not read |

**Building nodes from the edge list** (`:451-466`, `createNode` `:255-398`):

1. For each edge the flat map is renamed to DK keys with `GPFDataConverter.decode`.
2. A `DKNode` is built with `protocol=GPF`, `remote=true`, `mode=RUN`, and host `prod.daikinacmanager.com`.
3. The node's auth map holds `id="CLUB-DAIKIN-ACCOUNT"`, `spw`, `uid`, `port=ri`, `resource_id=ri` and `id_token`.
4. The node gets:
   - `DeviceType.toType(type)`, where `type` comes from `dev_i.type`; `CommonAdapter` becomes `RoomAirConditioner`
   - `DKAdapterType.toType(adp_kind)`, the version from `ver`, the region from `reg`, and the SSID from `ssid`
   - `led=="1"` and `auto_update=="1"`, with `auto_update` absent meaning "no auto-update feature"
   - `icon` (default 14 for `PA`, else 0), `instform`, `err` and the URL-decoded `name`
   - an option device from `option` and `opt_sv`
   - two `GPFObject(ri, adr_0100 / adr_0200)` objects
5. The same map is then pushed through the device converter as the unit's first status, using `DataType.DKExpandCh`.

**Single-edge refresh** (`GPFExpandChController`):

- cloud: `{"op":2,"to":"/dsiot/edges/<ri>?expand=ch"}`
- local: `{"op":2,"to":"/dsiot/edge"}`

The response `pc` is one edge object of the same shape. It is parsed with the same `pch` / `ch` flattener (`:46-79`), and `4004` is tolerated.

**Cloud metadata.** Building, zone and edge metadata (`/dkapp/app_config_all`, `/dkapp/edge_meta/...`, `/dsiot/buildings/...`) is handled separately by `gpf/ctrl/GPFMetaDataController.java` and runs in parallel with the search (`DeviceManager$search$1.java:1377-1379`). It does not affect device classification. Details are in the cloud-endpoints section.

### Local UDP discovery

Source: `p032e5/d.java`.

| Item | Value |
|---|---|
| Destination | IPv4 subnet broadcast of the interface whose name contains `wlan` (`InterfaceAddress.getBroadcast()`); falls back to `255.255.255.255` (`d.java:70-147`) |
| Destination port | **UDP 30050** |
| Payload | ASCII `DAIKIN_UDP/common/basic_info`. This is the only probe; there is no GPF-specific packet (`d.java:176-178`) |
| Source port | First free port in **30000–30050**, bound with `SO_BROADCAST` and `SO_REUSEADDR` (`d.java:154-170`). The adapter replies to the source port |
| Sends | 3 packets, 200 ms apart, then a 300 ms receive window with 100 ms `soTimeout`; this cycle repeats 3 times (`d.java:179-221, 267-270`). Total is about 2.7 s |
| Deduplication | By reply source IP (`d.java:246-249`) |
| Reply | Plain text `k=v,k=v,…`, split on `,` then `=`. Pairs without exactly one `=` are dropped. The source IP is added as `ip` (`d.java:222-245`) |

The local search only runs when Wi-Fi is on and the search mode is Local or Both (`DeviceManager$search$1$localeJob$1.java:44-56`).

**Reply keys** used by the node builder `p032e5/b.java`:

| Key | Meaning |
|---|---|
| `type` | Device type (see below) |
| `protocol` | `daikin`, `RS232C`, `gpf`, `DGC` or `echonet`; decides the protocol together with `type` and `cdev` |
| `cdev` | Connected device type. Used when `type=GPF` or the type is unknown |
| `api_port` | Optional HTTP port; the address becomes `ip:api_port` |
| `ver` | Firmware version, e.g. `3_10_0` |
| `reg` | Region; defaults to `in` |
| `adp_kind` | Adapter type code (see `adp_i.kind`). If absent, it is inferred from `ver` |
| `adp_mode` | `run`, `ap` or `ap_run`. If absent, it is inferred from kind and IP (e.g. STMicroWireless at 192.168.0.100 → AP) |
| `id`, `pw`, `port` | Legacy cloud credentials; stored as auth `id`, `apw`, `port` |
| `lpw_flag`, `led`, `auto_update`, `disp_ssid`, `en_hol` | Flags, as in the adapter tables |
| `method` | `polling` → out-of-home enabled |
| `edid` | Edge id, used to match to the cloud edge |
| `ssid`, `name` (URL-encoded), `icon`, `instform`, `err` / `comm_err`, `option`, `opt_sv` | As in the cloud node |

The whole map is also stored as `DKBasicInfo` (`b.java:521`). An auth entry `lpw=""` is created (`b.java:318-334`) and filled in later from the user's saved PIN.

**Discovery filter** (`W4/b.java:23-59`):

- `reg` must equal the app region (`in`).
- RA accepts any adapter except Others.
- Air purifier, circulator, common adapter and dryer require Marvell or Generation4.
- EcoCute and all-heat exchanger require Generation4.

After discovery, a GPF node is read over HTTP with the basic-info multireq batch shown above; it is never probed further by UDP.

### Protocol and device-type determination

**Local** (`p032e5/b.java:94-172`):

1. `type` goes through `DeviceType.toType` first.
2. For RA, cleaner, circulator, dryer and common-adapter types, `protocol` defaults to `daikin` if absent.
3. **For `type=GPF`:**
   - If `protocol=="RS232C"` and `cdev` is `RA` or `PA`, the node becomes a **legacy Daikin** `CommonAdapter`.
   - Otherwise `protocol="gpf"`, and the real type is taken from `cdev` (`RA`, `1D`, `1C`, `EQ`, …).
4. For an unknown `type`, the type is taken from `cdev`.
5. `CommonAdapter` with `protocol=DGC` is forced to Daikin. Otherwise `ProtocolType.toType(protocol)` is used: `gpf` or `DGC` → GPF; `daikin` or `RS232C` → Daikin; `echonet`; default Daikin.
6. A `GPFDevice` is created with `adr_0100` and `adr_0200` for any GPF node (`b.java:469-520`). EcoCute and all-heat exchanger are always `GPFDevice`.

**Cloud.** Every edge from `/dsiot/edges` is GPF (`GPFRemoteSearchController.java:303-306`). The type comes from `dev_i.type`.

`DeviceType.toType` (`dknetlib/core/data/DeviceType.java`):

| Input string(s) | DeviceType | App name | Converter |
|---|---|---|---|
| `aircon`, `RA`, `PA` | RoomAirConditioner | ra (`RA`) / vrv (`PA`) | `GPFRaDataConverter`. When the decoded `type` is `PA`, it hands control and model info to `GPFVRVDataConverter` (`GPFRaDataConverter.java:664-668, 7876-7878`), so **`PA` is the VRV/packaged-AC variant**. The converter is chosen in `C3/V.java:100-131` |
| `cleaner`, `1D` | AirCleaner | cj | `GPFCjDataConverter` |
| `all_heat_exchanger`, `1C` | AllHeatExchanger | vh | `GPFVhDataConverter` |
| `ecocute`, `EQ` | EcoCute | eq | `GPFEqDataConverter` |
| `circulator` | Circulator | cc | legacy only |
| `dryer` | RoomDryer | rd | legacy only |
| `common_adp`, `NA` | CommonAdapter | | treated as RA on the cloud |
| `GPF` | Gpf | | resolved through `cdev` |
| `Floor Heater`, `Water Heater` | FloorHeater, WaterHeater | | echonet |
| `UNKNOWN` / other | Unknown / Others | | |

The dispatcher reads `getNodeInfo()`, which contains `node_type` (`adapter`, `device` or `server`), `protocol` (`daikin` or `gpf`) and `device_type` (`dknetlib/dk/data/DKNode.java:117-124`). From these it chooses the GPF controllers or the legacy `/aircon/*` handlers (`E4/K.java:137-148, 710-722`). For a basic-info GET the controller is:

- AirCleaner → `GPFCjControlInfoController`
- EcoCute → `GPFEqModelInfoController`
- AllHeatExchanger → `GPFVhModelInfoController`
- everything else → `GPFBasicInfoController`

(`E4/K.java:149-165`)

**Local vs cloud choice.** In this build `DKCommonInfo.isOperateOutSideHome()` always returns `true` (`dknetlib/dk/data/DKCommonInfo.java:323-325`). So the unit list always searches in `Both` mode and **displays the cloud list** (`wwapp/view/unitlist/UnitSearch.java:714`, `dknetlib/p.java:233-234`). Setup and settings screens search Local explicitly.

A local node and a cloud node are treated as the same unit when any of these holds (`DKNode.isSame`):

- their unique keys are equal
- they are local nodes with the same address
- they are Generation4 adapters with the same non-empty `edid`
- their auth `id` and `port` are equal

MAC is not used for matching.

**Housekeeping after discovery** (`dknetlib/k.java:80-160`). For each **local** GPF adapter, the app:

- sends `GET /config/adapter/user_info` when out-of-home is enabled, to learn `resource_id`
- sends `GET /config/adapter/datetime` when a PIN is known
- sends `PUT /config/adapter/datetime` `{"date":"yyyy/MM/dd","time":"HH:mm:ss","zone":"GMT"}` (UTC) when the adapter reports its clock is unset

## Local adapter `/config/*` API

All of these are plain HTTP to `http://<adapter-ip>` and are never proxied by the cloud.

- Bodies are flat JSON objects built by `createConfigBody` (`GPFBaseController.java:560-573`). Values are strings, or JSON ints where marked.
- Responses are flat JSON: `{"rsc":2000, …keys}`. They do not use the `responses` wrapper, and the app reads `rsc` from the top level.
- Headers are `Content-Type: application/json`, plus `Authorization: Basic <lpw>` when a PIN is set.

| Method | Path | Request body | Response keys (besides `rsc`) | Controller |
|---|---|---|---|---|
| POST | `/config/wlan/scan/start` | empty string | — | `GPFWifiScanController.startWifiScan` (`:64`) |
| GET | `/config/wlan/scan/result` | — | `cnt` (int), `result01` … `resultNN`: objects `{"ssid","sec","radio"}` | `GPFWifiScanController.getWifiScanResult` (`:27`); decoded in `GPFDataConverter.decodeWifiScanResult` (`:833-866`) |
| GET | `/config/wlan/settings` | — | current Wi-Fi settings: `ssid`, `link` (`"1"` = associated; checked in `p079l5/a0.java:46-48`), and probably `security` and `key` (parsed by `N4/a.java:c()`) | `GPFWifiInfoController` (`:25`) |
| POST | `/config/wlan/connect/start` | `{"key":"<passphrase>"}` | `session` | `GPFWifiConnectionSettingController.startWifiConnection` (`:72-84`) |
| POST | `/config/wlan/connect/permit` | `{"session":"<session>","rslt":0 or 1}` (`rslt` is int) | `idx` | `…permitWifiConnection` (`:37-68`) |
| GET | `/config/net/settings` | — | `auto_ip`, `auto_dns`, `ipaddr`, `netmask`, `gateway`, `dns1`, `dns2`, `use_proxy`, `proxy`, `proxy_port` | `GPFNetworkSettingController.get` (`:29`) |
| PUT | `/config/net/settings` | `{"session"?, "auto_ip":int, "auto_dns":int, "ipaddr","netmask","gateway","dns1","dns2", "use_proxy":int, "proxy","proxy_port"}` | — | `GPFNetworkSettingController.set` (`:47-90`) |
| PUT | `/config/wlan/setting_ssid` | `{"disp_ssid":int}` | — | `GPFSsidOutputSettingController` (`:51`) |
| GET | `/config/adapter/user_info` | — | `resource_id` (the cloud edge `ri`, read at `wwapp/view/settings/OutOfHomeSettingsFragment.java:362-381`); `method` **[inferred]** | `GPFRemoteMethodSettingController.get` (`:28`) |
| PUT | `/config/adapter/user_info` | `{"method":"polling","id_token":"<Cognito id_token>"}` or `{"method":"home_only","id_token":""}`; 40 s timeout | — | `GPFRemoteMethodSettingController.set` (`:71`), `GPFOutOfHomeController` (`:57-58, 141, 156`) |
| PUT | `/config/adapter/lpw` | `{"new_lpw":"<4-digit PIN>"}`; `""` clears the lock | — | `GPFLockPwController` (`:51`) |
| GET | `/config/adapter/datetime` | — | `date` (`Y/M/D`), `time` (`H:M:S`), `sta` | `GPFDateTimeController.get` (`:34`). Decoded to `cur="<date> <time>"` (`GPFDataConverter.decodeDatetime` `:357-372`) |
| PUT | `/config/adapter/datetime` | `{"date":"yyyy/MM/dd","time":"HH:mm:ss","zone":"GMT"}` (UTC) | — | `GPFNotifyDateTimeController` (`:52`); called from `dknetlib/k.java:137-151` |
| PUT | `/config/adapter/timezone` | `{"dst":0,"zone":<int>}`, where zone = 396 India, 86 Sri Lanka, 106 Bangladesh, 177 Nepal, 356 Bhutan (from the app region) | ignored | `GPFDateTimeController.setTimeZone` (`:60-89`). Always sent just before the datetime GET (`E4/K.java:259-262`) |
| POST | `/config/adapter/look/start` | empty | — | `GPFLookAdapterController` (`:43`). Identify / "look" at the adapter (blinks the LED **[inferred]**) |
| POST | `/config/adapter/look/stop` | empty | — | same (`:51`) |
| POST | `/config/system/reboot` | empty | — | `GPFRebootController` (`:44`). Also sent after a failed firmware upload |
| POST | `http://192.168.127.1/config/system/init` | empty | — | `GPFSessionInfoController.resetWifiModule` (`:315`). **This resets the Wi-Fi module; it is not a provisioning step.** The host is hard-coded (`GPFHttpController.java:115-117`), and the UI only allows it while the phone is on the adapter AP (`wwapp/view/settings/M.java:176-199`) |
| POST (multipart) | `/config/firmware/update` | `multipart/form-data`: part `app1`, `filename=<asset name>`, `Content-Type: application/octet-stream`, plus an optional `checkBoxApp1` part. User-Agent `HTTPMultiPart/1.0.0 (Linux; Android;)`; 90 s timeout | `rsc` | `GPFFWUploadController.execute` (`:90-160`); multipart builder `dknetlib/dk/net/http/b.java` (smali `b.smali:505-1300`). Only for `adp_kind=="4"` and `type` ∈ {`RA`, `PA`, `1C`, `1D`, `EQ`, `NA`, `GPF`}. The image comes from app assets `Generation4/<ver>/DKWL4G_OTA*` |

On the cloud, `GPFDateTimeController.get` does not ask the adapter for the time. It does `GET https://prod.daikinacmanager.com/premise/dsiot/system_info/version` and reads the HTTP `Date` header (`GPFHttpController.getHeaderDate`, `:197-311`).

### Wi-Fi provisioning sequence

The India app onboards a room AC (GPF, Generation4/Marvell adapter) through the adapter's own access point. **WPS** is also offered but consists only of on-screen instructions and sends no HTTP (`wwapp/view/addUnit/wps/AddUnitWps*.java`). After WPS the flow jumps to step 6 below.

**UI path.** Screens are listed in order; paths are under `wwapp/view/`.

1. The user starts at `unitlist` "Add Unit", which opens `addUnit/AddUnitQRCodeScanFragment`. That screen reads the model list from the cloud: `GET /api/supportedmodels/list?country_code=…` (`GPFSessionInfoController.java:108`).
2. `addUnit/AddUnitConfirmationFragment` counts down 30 s. Every second it checks the phone's own Wi-Fi, then after 2 s it moves on. VRV models go to `WWAppConnectSetupCG03_00`. RA models go to `addUnit/WpsSettingFragment`; choosing "No WPS" there leads to `RemoteSetupFragment`, then `AddUnitWpsStep2`, then `CG03_00` (`R1/A.java:1076-1089`).
3. **Join the adapter AP.** `CG03_00` only opens Android's Wi-Fi settings (`Intent("android.settings.WIFI_SETTINGS")`, `WWAppConnectSetupCG03_00.java:162,195`). The user joins **`DaikinAP*****`** by hand, using the SSID and key printed on the adapter label (`res/values/strings.xml:913, 2094`). The app has no hard-coded AP password and makes no `WifiNetworkSpecifier` call.
4. **Find the adapter.** `CG03_00` runs a *Local* UDP search. It accepts only a node that is in AP mode and has adapter kind 3 (Marvell) or 4 (Generation4) (`CG03_00.java:237, 332-333, 476-481`). AP mode means the adapter reports AP/AP_RUN, or its address is `192.168.127.1` or `192.168.0.100` (`dknetlib/dk/data/DKAdapterInfo.java:95-104`). **The adapter's AP address is normally `192.168.127.1` [inferred from these checks]**, but the app always uses the address the adapter replied from.

The app then sends these HTTP requests to `http://<adapter-ip>` (screens `WWAppConnectSetupSL01` and `SP00`):

| # | Request | Purpose |
|---|---|---|
| 1 | `GET /config/net/settings` | Cache the current IP settings. They are sent back unchanged in step 5c (`WWAppConnectSetupSL01.java:148-166`) |
| 2 | `GET /config/wlan/settings` | Current Wi-Fi settings (`p079l5/P.java:38-45`) |
| 3 | `POST /config/wlan/scan/start` (empty body) | Start a Wi-Fi scan on the adapter (`P.java:60`, `SL01.java:101-110`) |
| 4 | `GET /config/wlan/scan/result`, sent 5 s after step 3 | Get the scan list. If `cnt==0`, wait 5 s, POST scan/start again and retry, about 6 attempts in total (`P.java:83`; `p079l5/V.java:91-99`). On `LOCK_NG` (4009), re-GET every 5 s with no limit (`V.java:36-38`) |
| 5a | `POST /config/wlan/connect/start` `{"key":"<passphrase>"}` | Returns `session` (`GPFNetworkController.java:190-235`) |
| 5b | `POST /config/wlan/connect/permit` `{"session":"<s>","rslt":0 or 1}`, repeated | Select the network (see below) |
| 5c | `PUT /config/net/settings` `{"session":"<s>","auto_ip":…,"auto_dns":…,"ipaddr":"…","netmask":"…","gateway":"…","dns1":"…","dns2":"…","use_proxy":0,"proxy":"","proxy_port":""}` | Commit. `auto_ip`, `auto_dns` and `use_proxy` are JSON ints (`GPFNetworkController.java:89-180`, `GPFNetworkSettingController.java:47-90`) |
| 6 | 20 s later: `GET /config/wlan/settings` | Success when `link=="1"` and `ssid` equals the chosen SSID. On failure, retry every 3 s, up to about 8 times; `AUTO_UPDATING` (4234) has its own message (`E4/C0029d.java:302-313`, `p079l5/a0.java:30-50`). This 20 s follow-up is only scheduled when the app region is `in` (`E4/C0030e.java:274-276`) |

**How the network is chosen.** The SSID is **never sent**. The network is chosen by its position in the adapter's scan list (`GPFNetworkController.java:36-69, 190-212`).

- The app numbers the scan results `result01…resultNN` as **1-based** `idx` values. The user's pick is the target idx (`CreateSsidList.java:88`, `p079l5/V.java:56-74`).
- After `connect/start`, the app sends `permit` with `rslt=1` if the target is `1`, otherwise `rslt=0`.
- Each `permit` response carries `idx`, the adapter's current candidate. When `idx` equals the target, the app sends `rslt=1`. Presumably `rslt=0` means "skip to the next entry" and `rslt=1` means "use this one" **[inferred]**.
- Once a `rslt=1` permit returns `2000`, the app sends step 5c.
- There is no delay and no iteration limit in this loop.

**The Wi-Fi key** is sent as **plaintext**: the raw text field value as a JSON string (`WWAppConnectSetupSP00.java:215-228`). It is not URL-encoded, hashed or encrypted.

- `security` is cached, but it is never sent to a GPF adapter.
- For GPF the request data type is `DKNetNetworkInfo`, which the GPF encoder passes through unchanged (`GPFDataConverter.java:870-898`, case 45).

**Scan-result fields** (`GPFDataConverter.decodeWifiScanResult` `:833-866`; `wwapp/view/setupwizard/CreateSsidList.java:58-79`):

| Field | Meaning |
|---|---|
| `resultNN.ssid` | SSID. Not URL-decoded for GPF |
| `resultNN.sec` | `"1"` = secured (the app asks for a key), anything else = open |
| `resultNN.radio` | RSSI in dBm. The UI shows ≥ -65 as strong, ≥ -80 as medium, and below that as weak |

- `resultNN` may be a nested object or a JSON string; the app parses `String.valueOf(value)` as JSON.
- SSIDs starting with `DaikinAP` are hidden from the list (`p079l5/V.java:80`).

After step 6 the user is told to switch the phone back to the home router (`WWAppConnectSetupOHG00.java:47-79`). The next screen, `PremisesUnitListFragment` (`GUIDANCE_RA_LAST`), runs a Local search on the home LAN and continues with cloud registration.

Example (local, adapter in AP mode):

```http
POST /config/wlan/connect/start HTTP/1.1
Host: 192.168.127.1
Content-Type: application/json

{"key":"MyHomePassphrase"}
```
```json
{"rsc":2000,"session":"<opaque>"}
```

The response shape is **[inferred]**; the parser only needs top-level `rsc` and `session`.

### Cloud registration (remote method)

Linking an adapter to the user's cloud account is done **on the adapter, over the LAN**. The adapter registers itself using the user's Cognito `id_token`. There is no cloud API call that "adds an edge".

1. The user turns on "Out-of-home / Activate" for the unit in `PremisesUnitListFragment` (`wwapp/view/premises/PremisesAdapter.java:473-516`). The app sends `DKNetOutOfHomeOn` (`HttpCommunicationManager.java:112-125`), which `E4/K.java:758-760` dispatches to `GPFOutOfHomeController.settingOn`.
2. The app sends `PUT http://<adapter-ip>/config/adapter/user_info` with body `{"method":"polling","id_token":"<Cognito id_token>"}` and a 40 s timeout (`GPFOutOfHomeController.java:55-58, 144-157`; `GPFRemoteMethodSettingController.java:46-71`). This goes straight to the controller, so the keys are sent as-is.
3. Later, `GET /config/adapter/user_info` returns **`resource_id`**, the cloud edge id (`ri`). The app copies it into every `GPFObject.edgeId` and into the node's auth map (`id="CLUB-DAIKIN-ACCOUNT"`, `port=resource_id`, `resource_id`) (`wwapp/view/settings/OutOfHomeSettingsFragment.java:352-381`). **A local client can use this GET to learn the cloud `ri` of a LAN adapter.**
4. Account bookkeeping on the cloud host (details in the cloud section):
   - `POST /api/locinfo` `{edge_device_id, latitude, longitude, pincode}`, only when the location is known
   - then `PUT /api/machineinfo` `{ri, model_name, serial_no}`

   (`PremisesUnitListFragment.java:444-532, 1038-1091`; `GPFSessionInfoController.java:253-268, 398-409`.) The app fills `edge_device_id` / `ri` from `CommonFunction.e(node)`, which returns the unit *name* (`wwapp/util/CommonFunction.java:69-73`). This looks like an app bug **[inferred]**.
5. The app does not poll the cloud for the new edge; it just re-runs the search.

**Deactivating** (`settingOff`, reached via `DKNetOutOfHomeOff`, `E4/K.java:826-828`):

1. The app sends `PUT /config/adapter/user_info` `{"method":"home_only","id_token":""}`.
2. If an edge id is known, it then sends a cloud **delete** `{"requests":[{"op":4,"to":"/dsiot/edges/<ri>","rqi":"1"}]}` to `https://prod.daikinacmanager.com/dsiot/multireq` (`GPFOutOfHomeController.java:94-108, 135-142`).

The current mode appears as `adp_d.method` (`polling` or `home_only`).

**Reset Wi-Fi.** `POST http://192.168.127.1/config/system/init` factory-resets the adapter's Wi-Fi settings. The app only allows it while the phone is joined to the adapter AP (`wwapp/view/settings/M.java:176-199`).

### Local authentication (`lpw`)

- The lock PIN (`lpw`) is a 4-digit PIN (`wwapp/view/settings/InputPwFragment.java:113-155`).
- **Setting or changing it:** `PUT /config/adapter/lpw` with `{"new_lpw":"<PIN>"}` (`GPFLockPwController.java:40-51`; `wwapp/view/settings/InputWithCheckPwFragment.java:205-215`). No "old PIN" field exists; the current PIN is proven by the `Authorization` header.
- **Clearing it:** `{"new_lpw":""}` (`DialogInterfaceOnClickListenerC0790l.java:24-30`, `C0777e0.java:46-56`).
- **Using it:** when a PIN is set, every local request (multireq and `/config/*`) carries **`Authorization: Basic <PIN>`**. The PIN is sent literally, **not base64** and with no `user:` prefix (`GPFHttpController.java:54-73`). The value is the PIN the user typed, saved through `DKNode.updateLock` and `DKAuthInfo.setLockPassword` (`dknetlib/dk/data/DKNode.java:297-301`, `DKAuthInfo.java:64-65`).
- A request without the header, or with the wrong PIN, gets `rsc` 401 or 4001, which maps to `LPW_NG` locally (`ResultType.java:113-115`).
- `adp_d.lpw_flag == "1"`, or the UDP key `lpw_flag=1`, means the adapter is locked. The app then asks for the PIN (`wwapp/view/unitlist/BaseCreateUnitElement.java:455`).
- Cloud requests never carry `lpw`.
## Room AC (Ra) DSIOT property map (`dgc_status`)

This section covers every `dgc_status` property that the app's room-AC ("Ra") code reads or writes over DSIOT. All paths are relative to `jadx/sources`. `dknetlib/` is short for `jp/co/daikin/dknetlib/` and `wwapp/` for `jp/co/daikin/wwapp/`. Smali paths are relative to `decompiled/smali`.

jadx failed on `GPFRaDataConverter.decodeControlInfo` (garbled output, `GPFRaDataConverter.java:597-7603`) and `GPFRaDataConverter.encodeControlInfo` (not decompiled, `GPFRaDataConverter.java:8614`). Every statement about those two methods comes from the smali, which is shortened below to `RaSmali` = `jp/co/daikin/dknetlib/gpf/data/GPFRaDataConverter.smali`:
- `decodeControlInfo`: `RaSmali:289-5693`
- `encodeControlInfo`: `RaSmali:11401-15153`

Anything marked **[inferred]** is a reasonable reading that the code does not state directly.

### Where the data lives

| Item | Detail | Source |
|---|---|---|
| Indoor unit | `<base>/adr_0100.dgc_status`. The app uses whichever object address starts with `adr_01`. | `dknetlib/gpf/net/GPFBaseController.java:833-841` |
| Outdoor unit | `<base>/adr_0200.dgc_status` (address starting with `adr_02`) | same |
| Other adr | The Ra code uses no other adr for `dgc_status`. Energy data is under `adr_0100.i_power` and `adr_0200.history`; see the energy section. | `GPFRaConvertValue.java:105-113` |
| Control read | One multireq with two `op:2` reads: `/<adr_01xx>.dgc_status?filter=pv,md` and `/<adr_02xx>.dgc_status?filter=pv,md` | `dknetlib/gpf/net/request/airconditioner/GPFControlInfoController.java:42-60` |
| Model-info read | `.adp_i?filter=pv`, `.dev_i?filter=pv`, then the indoor and outdoor `dgc_status?filter=pv,md` | `…/GPFModelInfoController.java:23-40` |
| Sensor read | `.dev_i?filter=pv`, then the indoor and outdoor `dgc_status?filter=pv`, **without md** | `…/GPFSensorInfoController.java:24-41` |

**How the response is flattened.** Every leaf becomes a key such as `dgc_status.e_1002.e_3001.p_01`. The adr prefix is dropped, so indoor and outdoor keys land in one map. They never collide, because the indoor unit only uses `e_1002` and the outdoor unit only uses `e_1003`. A leaf's metadata is flattened to `<key>.md.pt`, `.md.st`, `.md.mi` and `.md.mx`, each holding the raw JSON string (`GPFBaseController.java:283-436`). The app caches the last raw map per device and data type, and new reads are merged into that cache (`dknetlib/gpf/data/GPFDataManager.java:55-81`). The encoder uses this cached raw map both for the capability bitmasks (`md.mx`) and for "previous value" comparisons.

### Value encoding conventions

| Convention | Rule | Source |
|---|---|---|
| Byte order | `pv` is little-endian hex. The app reverses byte order (`convertByteData`) before it parses a multi-byte value. `"0200"` becomes `0x0002`, and `"0F0000"` becomes `0x00000F`. | `GPFDataConverter.java:424-440` |
| 2-byte enums | Mode and fan speed are 16-bit LE. Mode "cool" (2) is written `"0200"`. | encoder, `RaSmali:11936`, `13234` |
| 3-byte enums | Air direction is 24-bit LE, for example `"0F0000"` = swing. | `RaSmali:15154-15823` |
| 1-byte flags | Flags are `"00"` (off) or `"01"` (on); some also take `"02"`, `"03"`, and so on. | throughout |
| `md.mx` on an enum or bitfield property | A **bitmask of allowed values**: bit *n* set means value *n* is supported. The app relies on this for the mode (`p_01.md.mx` bit 8 = humidify), humidity modes (`p_2F/p_31/p_0C/p_2D/p_33 .md.mx`) and air direction (`p_05/07/20/22/24/29 .md.mx`). The app reads it as LE hex, then `parseInt(…,16)`. | `GPFRaDataConverter.java:7906`, `dknetlib/core/data/racontrol/e.java:961-1030`, `GPFRaVerticalAirDirectionType.java:47-121` |
| `md.st` (step) | Parsed as a **decimal** integer (`Integer.parseInt(str)`), so the server is expected to send a JSON number such as `245` **[inferred]**. The high nibble chooses the multiplier: 0–7 means ×10^n, and 8–15 means ×1e-8 up to ×0.1 (8 = 1e-8 … 15 = 0.1). The low nibble is the mantissa. `0xF5` = 0.5. | `GPFDataConverter.java:374-411,814-831` |
| Temperatures | Absolute setpoint: unsigned, value = °C × 2. Relative (auto/dry) setpoint: **signed int8**, value = °C offset × 2. Sensor readings: **signed int16 LE** × 0.5. | see tables |

### Operation mode enum (`e_1002.e_3001.p_01`)

The pv is 2 bytes LE; the table shows the value after byte reversal.

| pv (wire) | Value | Meaning | DK `mode` | Setpoint used on read | Fan key used on read | Written by app? |
|---|---|---|---|---|---|---|
| `"0000"` | 0 | Fan | `6` | none (`"--"`) | `p_28` | yes |
| `"0100"` | 1 | Heat | `4` | `p_03` | `p_0A` | yes |
| `"0200"` | 2 | Cool | `3` | `p_02` | `p_09` | yes |
| `"0300"` | 3 | Auto | `1` | `p_1D` (relative) | `p_26` | yes |
| `"0500"` | 5 | Dry | `2` | `p_1E` (relative) | `p_27` | yes |
| `"0800"` | 8 | Humidify | `HUM` | none | `p_2B` | yes |
| `"0900"` | 9 | **Cool-type state** | `""` (no UI mode) | `p_02` (the cool setpoint) | `p_09` (the cool fan) | **no** |
| `"0A00"` | 10 | **Heat-type state** | `""` (no UI mode) | `p_03` (the heat setpoint) | `p_0A` (the heat fan) | **no** |
| (any) with `e_3003.p_25 = "01"` | – | Laundry-dry | `LND` | – | – | yes (writes `e_3003.p_25`) |

**What `0009` and `000A` are.** The smali for `convertGPFDataToDriveModeType` settles this (`RaSmali:135-263`; jadx lost it, see `GPFRaDataConverter.java:225-282`):
- `0001` and `000A` both return `DKNetRaDriveModeType.Heat`.
- `0002` and `0009` both return `DKNetRaDriveModeType.Cool`.

The control decoder follows the same pattern for setpoint, fan and swing: `0009` reads `p_02`, `p_09`, `p_05` and `p_06`, and `000A` reads `p_03`, `p_0A`, `p_07` and `p_08` (setpoint switch `RaSmali:975-1160`; per-mode fan/swing switches `RaSmali:2259`, `2862`, `3271`; switch tables `RaSmali:5603-5670`). The `mode`/`b_mode` DK value is set to empty for both, so the app shows no mode for them (`RaSmali:613-960`). No string resource, UI code or enum names them, and the app never writes them.

So `0x09` is a cool-family state and `0x0A` a heat-family state. **[inferred]** They are most likely the actual running state while in Auto (auto→cooling and auto→heating), or special cool/heat sub-modes. For Home Assistant, map `0009` to cool and `000A` to heat, or treat them as `hvac_action` cooling/heating with mode auto.

`p_01.md.mx` is a bitmask of the supported modes. The app only tests bit 8 (`0x100`): `humd = 1` means humidify is supported (`GPFRaDataConverter.java:7903-7909`). The other bits follow the same pattern (bit 0 fan, bit 1 heat, bit 2 cool, bit 3 auto, bit 5 dry, bit 9/10 for 0009/000A) **[inferred]**. The app itself always offers Auto, Cool, Heat, Fan and Dry, plus Humidify when `humd = 1` (`racontrol/e.java:1055-1100`).

### `e_1002.e_A002`: power

| Key | Adr | R/W | Meaning | Encoding | Source |
|---|---|---|---|---|---|
| `e_1002.e_A002.p_01` | 0100 | R/W | Power | 1 byte: `"00"` off, `"01"` on. Written as `"0"+pow`. | read `GPFRaDataConverter.java:679-682`; write `RaSmali:11791-11811` |

### `e_1002.e_3001`: operation (mode, setpoints, fan, air direction, humidity)

Fan speed, air direction and humidity each have a separate property per mode.

| Key | Adr | R/W | Meaning | Encoding / values | Capability gate | Source |
|---|---|---|---|---|---|---|
| `p_01` | 0100 | R/W | Operation mode | 2 B LE, see the mode table | `p_01.md.mx` bitmask (bit 8 → `humd`) | dec `RaSmali:613-960`; enc `RaSmali:11863-12012` |
| `p_02` | 0100 | R/W | Cool setpoint (also used for mode 0009) | 1 B unsigned, °C×2 (`2E` = 23.0). Written as `Integer.toString(t*2,16)`, lowercase with no padding. | – | dec `RaSmali:1101`, `1364` (`dt3`); enc `RaSmali:12221` |
| `p_03` | 0100 | R/W | Heat setpoint (also used for mode 000A) | 1 B unsigned, °C×2 | `p_03.md.mi` → `hmlmt_l` (heat low limit, °C = LE value × 0.5) | dec `RaSmali:1143`, `1405` (`dt4`/`dt5`); enc `RaSmali:12119`; `GPFRaDataConverter.java:7972-7976` |
| `p_1D` | 0100 | R/W | Auto setpoint, **relative** | 1 B **signed**, offset °C×2. The app writes `00` (M, ±0), `02` (H, +1), `04` (HH, +2), `FE` (L, −1), `FC` (LL, −2), or a numeric offset as `%02X` of a signed byte. | `e_3003.p_28` (see capabilities) | dec `RaSmali:1064`, `1181-1300` (`stemp_a`, `dt1`, `dt7`); enc `RaSmali:12250-12420` |
| `p_1E` | 0100 | **R only** | Dry setpoint, relative | 1 B signed, offset °C×2 | – | dec `RaSmali:1025`, `1325` (`dt2`). **The encoder never writes `p_1E`**, because dry is not in the stemp switch. |
| `p_1F` | 0100 | md only | Auto absolute-setpoint range | `p_1F.md.mi` / `.md.mx` → `atlmt_l` / `atlmt_h` = (signed byte) × 0.5 °C. Only the md is read. | – | `GPFRaConvertValue.java:41-42`; `GPFRaDataConverter.java:7962-7971` |
| `p_09` | 0100 | R/W | Fan speed, **cool** (and 0009) | 2 B LE, see the fan table | presence → `en_frate` | dec `RaSmali:2511`, `2736` (`dfr3`); enc `RaSmali:13237` |
| `p_0A` | 0100 | R/W | Fan speed, **heat** (and 000A) | same | same | dec `RaSmali:2565`, `2763` (`dfr4`/`dfr5`); enc `RaSmali:13197` |
| `p_26` | 0100 | R/W | Fan speed, **auto** | same | same | dec `RaSmali:2452`, `2678` (`dfr1`/`dfr7`); enc `RaSmali:13283` |
| `p_27` | 0100 | R/W | Fan speed, **dry** | same. The app **always writes `0A00` (auto)** in dry. | same | dec `RaSmali:2394`, `2709` (`dfr2`); enc `RaSmali:13253` |
| `p_28` | 0100 | R/W | Fan speed, **fan mode** | same | same | dec `RaSmali:2625`, `2794` (`dfr6`); enc `RaSmali:13338` |
| `p_2B` | 0100 | R/W | Fan speed, **humidify** | same | same | dec `RaSmali:2328`, `2821` (`dfrh`); enc `RaSmali:13311` |
| `p_05` / `p_06` | 0100 | R/W | Vertical / horizontal air direction, **cool** (and 0009) | 3 B LE, see the air-direction tables | `p_05.md.mx` (vertical bitmask), `p_06.md.mx` (horizontal) | dec `RaSmali:3075`, `3393`, `3716-3780` (`ndfd3`); enc `RaSmali:13526` |
| `p_07` / `p_08` | 0100 | R/W | Vertical / horizontal, **heat** (and 000A) | same | `p_07.md.mx`, `p_08.md.mx` | dec `RaSmali:3134`, `3423`, `3808-3870` (`ndfd4`/`ndfd5`); enc `RaSmali:13445` |
| `p_20` / `p_21` | 0100 | R/W | Vertical / horizontal, **auto** | same | `p_20.md.mx`, `p_21.md.mx` | dec `RaSmali:3016`, `3363`, `3499-3585` (`ndfd1`/`ndfd7`); enc `RaSmali:13688` |
| `p_22` / `p_23` | 0100 | R/W | Vertical / horizontal, **dry** | same | `p_22.md.mx`, `p_23.md.mx` | dec `RaSmali:2957`, `3333`, `3624-3690` (`ndfd2`); enc `RaSmali:13607` |
| `p_24` / `p_25` | 0100 | R/W | Vertical / horizontal, **fan mode** | same. On read the app checks `p_20.md.mx` (the auto mask) for fan mode; on write it uses `p_24.md.mx`. | `p_24.md.mx` / `p_20.md.mx`, `p_25` | dec `RaSmali:3194` (reads `p_20.md.mx` at ≈`3205`), `3457`, `3904-3970` (`ndfd6`); enc `RaSmali:13847` |
| `p_29` / `p_2A` | 0100 | R/W | Vertical / horizontal, **humidify** | same | `p_29.md.mx`, `p_2A.md.mx` | dec `RaSmali:2894`, `3303`, `3996-4060` (`ndfdh`); enc `RaSmali:13769` |
| `p_2F` / `p_2E` | 0100 | R/W | Humidity **mode** / **value**, auto | mode: 1 B, see the humidity table. Value: 1 B hex × `p_2E.md.st` step. | `p_2F` present → `s_humd` bit 0; `p_2F.md.mx` → `sh1` (allowed humidity modes); `p_2E.md.st` → step | dec `RaSmali:1750`, `2012`; enc `RaSmali:13006-13026` |
| `p_31` / `p_30` | 0100 | R/W | Humidity mode / value, **dry** | same | `p_31` → `s_humd` bit 4 (16); `p_31.md.mx` → `sh2`; `p_30.md.st`. The **pv** of `p_31` (not its md) bits 2, 3 and 4 all set → `shtyp = 1`. | dec `RaSmali:1660`, `2069`; enc `RaSmali:12944-12969`; `GPFRaDataConverter.java:8197-8201` |
| `p_0C` / `p_0B` | 0100 | R/W | Humidity mode / value, **cool** | same | `p_0C` → bit 1 (2); `p_0C.md.mx` → `sh3`; `p_0B.md.st` | dec `RaSmali:1845`, `2123`; enc `RaSmali:12893-12913` |
| `p_2D` / `p_2C` | 0100 | R/W | Humidity mode / value, **heat** | same | `p_2D` → bit 2 (4); `p_2D.md.mx` → `sh4`; `p_2C.md.st` | dec `RaSmali:1945`, `2164`; enc `RaSmali:12830-12850` |
| `p_33` / `p_32` | 0100 | R/W | Humidity mode / value, **humidify** | same | `p_33` → bit 5 (32); `p_33.md.mx` → `shh`; `p_32.md.st` | dec `RaSmali:1588`, `2221`; enc `RaSmali:13053-13078` |
| `p_15` | 0100 | R/W | Filter sign (clean-filter indicator) | `"01"` on / `"00"` off. The app writes `"00"` to reset it (DK `filter=0`). | presence → `en_filter_sign` | read `GPFRaDataConverter.java:8480-8482`; write `GPFRaDataConverter.java:8973-8979` (DataType `DKSignInfo`) |
| `p_36` | 0100 | R/W | Ventilation power | 1 B. Read with `toIntOrNull` on the raw string (decimal parse of `"00"` or `"01"`). Written as `%02X`. 0 = off, 1 = on. | presence → `en_ventilation` | `GPFRaDataConverter.java:695-699`, `8986-9051`, `7899-7900` |
| `p_1C` | 0100 | R/W | Ventilation speed | 1 = High, 2 = Auto (`DKNetRaVentilationSpeedType`) | – | same |
| `p_45` | 0100 | R/W | Ventilation category (airflow direction) | 0 = Supply, 1 = Exhaust, 2 = Auto (`DKNetRaVentilationCategory`) | presence → `en_ventilation_category` | `GPFRaDataConverter.java:705-709`, `9054-9083` |

**Setpoint ranges.** The app ignores `p_02`/`p_03` md for ranges and uses hard-coded limits for India (`reg=in`, and `cpv=3`, which the GPF path always forces; `GPFDataConverter.java:807-812`). With GPF devices the step is 0.5 °C (`racontrol/e.java:1295-1300`; the step flag is set for `ProtocolType.GPF` in `wwapp/view/unitcontrol/ra/ViewOnClickListenerC0846y.java:307-309`). The values below are from `U3.k(max, min, step, current)` in tenths of a degree (`racontrol/e.java:1295-1560`):

| Mode | Min | Max | Condition |
|---|---|---|---|
| Cool | 18.0 °C | 32.0 °C | Default. It becomes 21–32 °C when `temp_rng = 1`, but the GPF path always sets `temp_rng = 0`. |
| Heat | 18.0 °C | 30.0 °C | – |
| Auto (absolute) | 18.0 °C | 30.0 °C | Becomes 21–30 °C when `mid = W`; GPF sets `mid = NA`. On DSIOT, auto actually uses the **relative** `p_1D`. |
| Auto/dry relative | −2 °C | +2 °C | Named steps LL, L, M, H, HH map to −2, −1, 0, +1 and +2 °C (`dknetlib/dk/data/DKRaDataConverter.java:495-598`). |

For Home Assistant, reading `p_02.md.mi/mx/st` and `p_03.md.mi/mx/st` would probably give the unit's true range **[inferred; the app does not use them]**.

### Fan speed (`p_09`, `p_0A`, `p_26`, `p_27`, `p_28`, `p_2B`)

The values are 2 bytes LE; the app's `decodeFlate`/`encodeFlate` use the byte-reversed form (`GPFRaDataConverter.java:7768-7796`, `8780-8818`).

| pv (wire) | Value | DK `f_rate` | Meaning (`DKNetRaFanSpeedType`) |
|---|---|---|---|
| `"0300"` | 3 | `3` | Level 1 (Low) |
| `"0400"` | 4 | `4` | Level 2 (MiddleLow) |
| `"0500"` | 5 | `5` | Level 3 (Standard) |
| `"0600"` | 6 | `6` | Level 4 (MiddleHigh) |
| `"0700"` | 7 | `7` | Level 5 (High) |
| `"0A00"` | 10 | `A` | Auto |
| `"0B00"` | 11 | `B` | Quiet / silent (indoor-unit quiet) |

The app offers Auto, Quiet and levels 1–5 in every mode except **Dry, where only Auto is offered** (`racontrol/e.java:273-345`). In Cool, the app writes the fan only when humidity control is off (the humidity mode it is about to write is `"00"`); otherwise it forces `0A00` (`RaSmali:13200-13240`).

`gpf/data/FanSpeed.java` and `gpf/data/Mode.java` are **not** room-AC enums. They are used by the air-purifier (Cj) converter: FanSpeed `00`–`04` is quiet through turbo, and Mode `0000`–`0A00` covers recommend, fan-setting, save-electric, pollen, throat/skin, circulator, cloth-dry, cloth-dry-night, deodorise and inside-dry. Do not apply them to `e_3001.p_01`.

### Air direction

**Vertical** (`p_05`, `p_07`, `p_20`, `p_22`, `p_24`, `p_29`): 3 bytes LE. The enum is `GPFRaVerticalAirDirectionType` (`gpf/data/GPFRaVerticalAirDirectionType.java:11-33`).

| pv (wire) | Value | Name | DK `f_dir_ud` | `md.mx` bit |
|---|---|---|---|---|
| `"000000"` | 0 | Stop / fixed at current position | `0` | bit 0 (1) |
| `"010000"`–`"0E0000"` | 1–14 | Fixed positions P0–P13 | `1..n` = index into the list of supported positions | bits 1–14 (2 … 16384) |
| `"0F0000"` | 15 | Swing | `S` | bit 15 (0x8000) |
| `"100000"` | 16 | Auto | `A` | bit 16 (0x10000) |
| `"110000"` | 17 | Reverse | (not mapped; raw value passed through) | bit 17 |
| `"120000"` | 18 | Insensitive airflow | (not mapped) | bit 18 |
| `"130000"` | 19 | Natural wind | `N` | bit 19 |
| `"140000"` | 20 | Circulating airflow | `C` | bit 20 |
| `"170000"` | 23 | "Nice" airflow (comfort) | `I` | bit 23 |

When the app writes UI position *n* (1-based), it sends the *n*-th set position bit of `md.mx`, so the wire value equals the bit index (`GPFRaDataConverter.java:8697-8776`; smali `RaSmali:15406-15823`). When it reads, a position value is shown as its 1-based index among the supported positions (`GPFRaDataConverter.java:7656-7745`). `setEnabledFlag` condenses each mode's mask into `s_fdir_ud_<mode>`: bit 0 swing, bit 1 auto, bit 2 circulating, bit 3 natural, bit 4 nice (`GPFRaDataConverter.java:9165-9187`, `8076-8088`).

**Horizontal** (`p_06`, `p_08`, `p_21`, `p_23`, `p_25`, `p_2A`): 3 bytes LE.

| pv (wire) | Meaning | DK `f_dir_lr` |
|---|---|---|
| `"000000"`–`"0E0000"` | Stop / fixed position | `0` (every position reads as "off") |
| `"0F0000"` | Swing | `S` |
| `"100000"` | Auto | `A` |

When writing `0`, the app keeps the current raw position if it is `01`–`0E`, and otherwise writes `000000`. `S` is written as `0F0000` and `A` as `100000` (`RaSmali:15154-15405`; `GPFRaDataConverter.java:8624-8667`). The model's horizontal capability is `s_fdir_lr`, built from `p_21/08/06/23/2A.md.mx` (swing = 1, auto = 2, and 0x80 when any mask is present); the app hard-codes `s_fdir_lr_step = 0` (`GPFRaDataConverter.java:8140-8196`).

The app treats "3D" airflow (vertical and horizontal swing together) as `f_dir_ud=S` plus `f_dir_lr=S`. The write always carries **both** vertical and horizontal values: the encoder writes air direction only when both `f_dir_ud` and `f_dir_lr` are in the DK map (`RaSmali:13352-13380`).

### Humidity mode and value

These apply to the pairs `p_2F`/`p_2E` (auto), `p_31`/`p_30` (dry), `p_0C`/`p_0B` (cool), `p_2D`/`p_2C` (heat) and `p_33`/`p_32` (humidify).

| Mode pv | DK `shum` | Meaning | `md.mx` bit (UI offers it) |
|---|---|---|---|
| `00` | `0` | Off | bit 0 (1) |
| `01` | numeric (e.g. `50`) | Target %RH, taken from the value key | bit 1 (2). The UI then offers 50/55/60 % in cool and dry, and 40/45/50 % in heat and humidify. |
| `02` | `AUTO` | Auto | bit 2 (4) |
| `03` | `AUTO_H` | Auto (high) | bit 3 (8) |
| `04` | `AUTO_L` | Auto (low) | bit 4 (16) |
| `05` | `0` (read as off) | Special state. The app sets `adv` code `7` when the current mode's humidity mode is `05`, and it never overwrites `05` with `00` (`encodeSettingHumidity`). **[inferred]**: a special-mode humidity state (`DKNetRaSpecialModeType` 7 = "BeautifulSkin"). | bit 5 |
| `06` | `CONTINUE` | Continuous | bit 6 (64) |

Sources: `GPFRaDataConverter.java:7802-7842` (decode) and `8969-8971` (`encodeSettingHumidity`); the enum `racontrol/DKNetRaHumidityType.java`; the UI option logic in `racontrol/e.java:961-1030`.

- **Value byte:** `hex(value / md.st)`, uppercase and padded to 2 digits. If there is no step, the app writes `hex(value)`. On read, value = `parseInt(pv,16) × md.st`. The value key is written **only when the mode is `01`** (`RaSmali:12830-13078`).
- **Humidity mapping from DK strings:** `AUTO_L`→`04`, `AUTO_H`→`03`, `CONTINUE`→`06`, `AUTO`→`02`, `0`→`00`, any number→`01` (`RaSmali:12529-12560`).

### `e_1002.e_3003`: feature flags and special modes

In the "DK read value" column, `0` means off. The non-zero numbers are the app's internal feature IDs, which are also used as `adv` codes.

| Key | Adr | R/W | Meaning | Values | DK read value | Capability gate | Source |
|---|---|---|---|---|---|---|---|
| `p_24` | 0100 | R/W | **Econo** | `00`/`01` | `econo`: `12` on | presence → `en_econo` | dec `RaSmali:4211-4240`; enc `RaSmali:14575-14630`; `GPFRaDataConverter.java:7956` |
| `p_20` | 0100 | R/W | **Streamer** (air purification) | `00`/`01` | `en_streamer`: `13` on | presence → `en_spmode` = 1, which the UI also uses to offer Powerful/Econo | dec `RaSmali:4812-4840`; enc `RaSmali:11466-11560` (special `only_streamer` write) and ≈`RaSmali:13880-13950`; `GPFRaDataConverter.java:7950` |
| `p_1B` | 0100 | **R** | **Powerful** | `01` = active | adds `1` to `adv` (the DK special-mode code for Powerful) when `p_25 ≠ 01` | – | dec `RaSmali:4110-4135`. **The app has no code that writes it**; see "Writes". |
| `p_25` | 0100 | R/W | **Laundry-dry mode** flag | `01` = on | forces DK `mode = LND` | – | dec `RaSmali:673`; enc `RaSmali:11877-11895` (`mode=LND` → `p_25="1"`, **written as a single char `"1"`**, which looks like an app bug) |
| `p_1C` | 0100 | R | Special mode (DKNet special-mode 4 = "HotWind") **[inferred]** | `01` = on | adds `4` to `adv` | – | dec `RaSmali:4847-4860` |
| `p_21` | 0100 | R | High-temperature prevention (guard) | `01`, `02`, `03` | adds `adv` `11` (01, notify), `9` (02, monitoring) or `10` (03, operation), per `DKNetRaSpecialModeType` 9/10/11 **[inferred mapping]**. Raw value is also exposed as `high_temp_prevent`. | `hasHighTempPrevent` = `e_3003.p_22` present | dec `RaSmali:5060-5150`, `5480-5540` |
| `p_64` | 0100 | R | Low-temperature prevention **[inferred]** | `01`, `02`, `03` | adds `adv` `16`, `14` or `15` | `hasLowTempPrevent` = `p_65` present | dec `RaSmali:5159-5250` |
| `p_22` | 0100 | R | High-temperature-prevention setting | `00`, `01`, `02` | `high_temp_prevent` (raw); feeds `alert` and `alert_mode` | – | dec `RaSmali:5266-5540` |
| `p_65` | 0100 | R | Low-temperature-prevention setting | `00`, `01`, `02` | `low_temp_prevent` (raw); feeds `alert_mode` | – | same |
| `p_27` | 0100 | R | Absence-eco / motion detection ("intelligent eye" absence) | `01` = supported/on | `m_dtct = 1` when `01`; `hasAbsenceEco = 1` when present | – | `GPFRaDataConverter.java:7941-7942`; `RaSmali:5529-5540` |
| `p_6E` | 0100 | R/W | **Intelligent Eye: "Energy Saver"** (UI label, `res/values/strings.xml:1236`) | `00`/`01` | `intelligent_eye`: `53` on | presence of `p_6E` or `p_6F` → `en_intelligenteye` | dec `RaSmali:4585-4700`; enc `RaSmali:11568-11710` and ≈`RaSmali:14140-14320` |
| `p_6F` | 0100 | R/W | **Intelligent Eye: "Auto On/Off"** (the app's `intelligent_eye_energy` name notwithstanding) | `00`/`01` | `intelligent_eye_energy`: `54` on | same | same |
| `p_B2` | 0100 | R/W | **Dew Clean** (self-clean cycle, about 95 min; the UI blocks other changes while it runs) | `00`/`01` | `dew_clean`: `46` on | presence → `en_dewclean` | dec `RaSmali:4773-4800`; enc `RaSmali:11719-11790` (`only_dew_clean`: B2 plus 6F=00 and 6E=00) and ≈`RaSmali:14110-14140` |
| `p_1E` | 0100 | R/W | **Good sleep** (sleep mode) | `00`/`01` | `good_sleep`: `57` on | – (the UI shows it for one region type) | dec `RaSmali:4308-4345`; enc `RaSmali:13955-14010` |
| `p_BA` | 0100 | R/W | Good-sleep "Shift Value": setpoint shift in °C, `01`–`05` (the setpoint rises 1 °C per hour; `wwapp/view/unitcontrol/ra/RaGoodSleepBottomSheet.java:82-111`) | 1 B, raw string passed through. The app writes `good_sleep_degree`, or `"00"` if unset, **whenever `good_sleep` is sent**. | `good_sleep_degree` | – | dec `RaSmali:4347-4382`; enc `RaSmali:14016-14046` |
| `p_BB` | 0100 | R/W | Good-sleep "Timer" in hours, `01`–`09` (despite the DK name `good_sleep_temp`) | 1 B raw, same behaviour as `p_BA` | `good_sleep_temp` | – | same |
| `p_70` | 0100 | R/W | **Smell-proof / odour prevention** | `00`/`01` | `smell_proof`: `47` on | presence → `en_smellproof` **[inferred: the model-info decoder does not set this flag]** | dec `RaSmali:4393-4430`; enc `RaSmali:14051-14106` |
| `p_B1` | 0100 | R/W | **"Variable"** (UI shows levels L1–L5; only offered in Cool/Dry; the button is hidden in 1.5.2) | `00` off, `01`–`05` = L1–L5 | `variable`: `48`–`52` | presence → `en_variable` | dec `RaSmali:4432-4560`; enc `RaSmali:14324-14450` |
| `p_BC` | 0100 | R/W | **Indoor-unit LED brightness** | `00` off, `01` "Low Brightness", `02` "High Brightness" (`wwapp/view/unitcontrol/ra/PopupOptionMenuBottomSheet.java:195-212`) | `en_led_brightness`: `55` (01) or `56` (02) | presence → `en_led_brightness` in model info | dec `RaSmali:4242-4305`; enc `RaSmali:14706-14770` |
| `p_BD` | 0100 | **W** | Filter clean (encoder support only). **The 1.5.2 UI does not use it**: its "Filter Clean" feature is a cloud notification timer, `POST /dsiot/fcn/status` with `{"ri","status":"ON"|"OFF"|"RESET"}` (`RaUnitCtrlFragment.java:1138-1150`) | `00`, `01`, `02` from DK `filter_clean` `0`, `1`, `2` | (not read) | – | enc `RaSmali:14636-14700` |
| `p_2D` | 0100 | **W** | Power-change trigger | `"00"` when the write turns the unit **on** (new pow = 1, stored = 0), `"01"` when it turns the unit **off**, `"02"` when power is unchanged. The ventilation writers always send `"02"`. | – | – | enc `RaSmali:11811-11860`; `GPFRaDataConverter.java:8573-8576`, `8996`, `9009`, `9070` |
| `p_28` | 0100 | R | Relative-temperature-in-auto disable | `01` → `en_rtemp_a = 0` (no relative setpoint); anything else → 1 | – | – | `GPFRaDataConverter.java:7959-7960` |
| `p_29` | 0100 | – | "Amenity type" (declared) | The code actually computes `shtyp` from `e_3001.p_31` | – | – | `GPFRaConvertValue.java:49`; `GPFRaDataConverter.java:8197-8201` |
| `p_2C` | 0100 | R | Separate cool/heat energy metering | `01` plus `adp_i.func.en_ipw_sep = 1` plus `elec = 1` → `en_ipw_sep = 1` | – | – | `GPFRaDataConverter.java:7961` |
| `p_30` | 0100 | R | **Error present** flag | `01` = the unit reports an error code in `p_31` | → `err` | – | `GPFRaDataConverter.java:9296-9304` |
| `p_31` | 0100 | R | **Error code** | ASCII, byte-reversed. The first 2 characters after reversal form a Daikin code such as `U4` or `A5`. | → `err` | – | `GPFRaDataConverter.java:9304-9433` |
| `p_39` | 0100 | R/W | 24-hour ventilation (variant A) | `%02X` of 0 off, 1 on with turbo, 2 on without turbo. Write also sends `p_2D="02"`. | presence → `en_ventilation_24hour_39` | – | `GPFRaDataConverter.java:8528-8581`, `7888-7889` |
| `p_3E` | 0100 | R/W | 24-hour ventilation (variant B) | same values; used only when `p_39` is absent | presence → `en_ventilation_24hour_3e`; `p_3E.md.mx` (parsed as a decimal int) → allowed values | – | same, `7890-7898` |
| `p_52` | 0100 | R | "Water internal cleaning" status | hex int, `1` = active. On model `e_2016.p_01 = "01850020"` without `p_2B`, it is only reported when room temperature ≥ 23 °C and humidity ≥ 40 %. | `water_internal_cleaning` | – | `GPFRaDataConverter.java:8483-8504` |

**`adv` special-operation codes.** The decoder builds `adv` as a `/`-joined list. The codes are `DKNetRaSpecialModeType` values; the UI treatment is from `RaUnitCtrlFragment.java:2355-2432`.

| Code | Source | Name | UI text (India) |
|---|---|---|---|
| 1 | `p_1B=01` (and `p_25≠01`) | HouseKeep in the enum, but it comes from `p_1B` **[inferred: Powerful]** | "Other operation" |
| 4 | `p_1C=01` | HotWind | "Other operation" |
| 7 | humidity mode `05` in the current mode | BeautifulSkin | none (treated as "special op active") |
| 9 | `p_21=02` | High-temperature prevention: monitoring | "Fan (High temperature)"; humidify blocked |
| 10 | `p_21=03` | High-temperature prevention: operation | "Cooling (High temperature)" |
| 11 | `p_21=01` | High-temperature prevention: notify | "Fan (High temperature)" |
| 14 | `p_64=02` | Low-temperature analogue of 9 | "Fan (Low temperature)" |
| 15 | `p_64=03` | Low-temperature analogue of 10 | "Heating (Low temperature)" |
| 16 | `p_64=01` | Low-temperature analogue of 11 | "Fan (Low temperature)" in Fan mode |

`hasAbsenceEco` (the `e_3003.p_27` key is present) switches the app's "Unattended operation" notification text (`C0836n.java:190-198`).

### `e_1002.e_A00B`: indoor sensors

These are read by the sensor controller (without md) and by the control and model reads.

| Key | Adr | R/W | Meaning | Encoding | Source |
|---|---|---|---|---|---|
| `e_A00B.p_01` | 0100 | R | Room temperature (legacy; only its `md.st` appears in other converters) | – | inventory only |
| `e_A00B.p_06` | 0100 | R | **Room temperature** | **signed int16 LE × 0.5 °C** (`"2E00"` = 23.0). For the `PA` group it is a raw int instead. Its `md.st` is used for the water-cleaning check. | `GPFRaDataConverter.java:8450-8456` |
| `e_A00B.p_02` | 0100 | R | **Room humidity %** | 1 B unsigned hex, **no byte swap** | `GPFRaDataConverter.java:8457-8462` |

### `e_1002.e_A001`, `e_A006`, `e_A011`, `e_2016`: identity, capability and status

| Key | Adr | R/W | Meaning | Encoding → DK key | Source |
|---|---|---|---|---|---|
| `e_A001.p_01` | 0100 | R | Model name | ASCII hex, **byte-reversed** (`convertHexToStringWithoutNull` reverses and then drops `00` bytes) → `model_name` | `GPFConvertValue.java:63`; `GPFDataConverter.java:496-508,596-618` |
| `e_A001.p_02` | 0100 | R | Model number | same → `model_num` | `GPFConvertValue.java:64` |
| `e_A001.p_0D` | 0100 | R | Model code | raw pv → `model`. The app compares `model` with a list of humidifier-capable codes (`097A`…`0A13`). | `GPFRaConvertValue.java:11`; `racontrol/e.java:17` |
| `e_A001.p_07` | 0100 | R | Model type | `01` → `type = C`, otherwise `N` (**[inferred]**: C = cooling-only) | `GPFRaDataConverter.java:7883-7884` |
| `e_A001.p_0E` | 0100 | R | Destination / market | `00` → `ac_dst = in`, otherwise `--` | `GPFRaDataConverter.java:7943-7944` |
| `e_A001.p_0C` | 0100 | R | Air-purifier (Cj) link | `00` → `en_cjlink = 1` (as coded) | `GPFRaDataConverter.java:8202-8203` |
| `e_A006.p_0D` | 0100 | R | Communication error (indoor↔outdoor or adapter) | `01` → the `err` value is prefixed with `10` (e.g. `10000`) | `GPFRaDataConverter.java:9293-9295` |
| `e_A006.p_12` | 0100 | R | "Support humidity" (declared) | overwritten by the computed `s_humd` | `GPFRaConvertValue.java:16` |
| `e_A006.p_14` | 0100 | R | Dry display | `01` → `disp_dry = 1` | `GPFRaDataConverter.java:7945-7946` |
| `e_A011.p_01` | 0100 | R | Energy metering supported | `01` plus `adp_i.func.en_ipower = "1"` → `elec = 1` | `GPFRaDataConverter.java:7936-7937` |
| `e_A011.p_02` | 0100 | R | Alert / notification enable | See the alert logic below | `RaSmali:5266-5540` |
| `e_A011.p_05` | 0100 | R | Patrol (temperature patrol) | mapped, but `en_patrol` is forced to `0` | `GPFRaDataConverter.java:7981` |
| `e_2016.p_01` | 0100 | R | Micom / firmware ID | Compared with `"01850020"` (water-cleaning special case) | `GPFRaDataConverter.java:8492` |

**Alert logic** (`RaSmali:5266-5385`). This runs when both `A011.p_02` and `e_3003.p_22` are present.
- If `A011.p_02` is not `01`: `alert = 255`.
- If `A011.p_02 = 01`:
  - `p_22 = 00` → `alert = 1`.
  - `p_22 = 01` → `alert = 0`.
  - `p_22 = 02` → `alert = 16` if `e_3003.p_27` exists, otherwise `2`.
  - any other `p_22` value → `16` if `p_27` exists, otherwise `255`.

`alert_mode` (`RaSmali:5386-5520`):
- `1`: `p_22 = 00` and `p_65 = 00`.
- `0`: `p_22` is `01` or `02`, and `p_65` is `01` or `02`.
- `2`: `p_22` is `01` or `02`, and `p_65 = 00`.
- `3`: `p_22 = 00`, and `p_65` is `01` or `02`.

### `e_1003`: outdoor unit (`adr_0200`)

| Key | Adr | R/W | Meaning | Encoding | Gate | Source |
|---|---|---|---|---|---|---|
| `e_1003.e_3002.p_3D` | **0200** | R/W | **Quiet / outdoor-unit silent** | `00`/`01` → `quite_mode`: `45` on | presence → `en_quitemode` | dec `RaSmali:4722-4760`; enc `RaSmali:14453-14508`; `GPFRaDataConverter.java:7952` |
| `e_1003.e_3002.p_44` | **0200** | R/W | **Power Chill** (fast cooling) | `00`/`01` → `pow_chill`: `44` on | presence → `en_powchill` | dec `RaSmali:4140-4200`; enc `RaSmali:14514-14569`; `GPFRaDataConverter.java:7951` |
| `e_1003.e_A00D.p_01` | 0200 | R | **Outdoor temperature** | **signed int16 LE × 0.5 °C** | presence → `temp` (outdoor temperature supported) | `GPFRaDataConverter.java:8463-8468`, `7938-7939` |
| `e_1003.e_2006.p_04` | 0200 | R | **Compressor frequency** (Hz **[inferred]**) | unsigned int, LE, → `cmpfreq` | – | `GPFRaDataConverter.java:8470-8474` |
| `e_1003.e_A005.p_01` | 0200 | R | Momentary power | LE uint *x* → `mompow = (x*10 + 100) / 100` (integer division, as coded) | presence → `en_mompow` | `GPFRaDataConverter.java:8475-8479`, `7979-7980` |

### Capability and model-info map

`decodeModelInfo` (`GPFRaDataConverter.java:7846-8260`) turns the raw map, which includes `md`, into these DK flags. A Home Assistant integration can apply the same rules directly to the `?filter=pv,md` read.

| DK key | Meaning | Derived from |
|---|---|---|
| `humd` | Humidify mode supported | `e_3001.p_01.md.mx & 0x100` |
| `s_humd` | Humidity control per mode (bitmask) | bit 0 = `p_2F` present (auto), bit 1 = `p_0C` (cool), bit 2 = `p_2D` (heat), bit 4 = `p_31` (dry), bit 5 = `p_33` (humidify), bit 7 = `e_A00B.p_02` **and** `p_30` present (humidity sensor) |
| `sh1`, `sh2`, `sh3`, `sh4`, `shh` | Allowed humidity modes per mode (bitmask, see the humidity table) | `p_2F`, `p_31`, `p_0C`, `p_2D`, `p_33` `.md.mx` |
| `shum_step_val_*` | Humidity value step | `p_2E`, `p_30`, `p_0B`, `p_2C`, `p_32` `.md.st` |
| `en_frate` | Fan-speed control | any of `p_09`, `p_0A`, `p_26`, `p_27`, `p_28`, `p_2B` present |
| `s_fdir` | Air-direction support | `0` none, `1` vertical only, `3` vertical and horizontal (presence of the per-mode keys) |
| `en_fdir`, `en_fdir2` | Any air direction | same |
| `s_fdir_ud` | Union of vertical capabilities (hex) | bit 0 swing, bit 1 auto, bit 2 circulating, bit 3 natural, bit 4 nice, `0x80` any, over `p_20/07/05/24/22/29 .md.mx` |
| `s_fdir_ud_{auto,heat,cool,fan,dry,hum}` | Per-mode vertical capability | `setEnabledFlag(p_20/p_07/p_05/p_24/p_22/p_29 .md.mx)` |
| `s_fdir_ud_step` | Number of distinct fixed vertical positions | count of P0–P13 bits over all masks |
| `s_fdir_lr`, `s_fdir_lr_step` | Horizontal capability; step is always `0` | `p_21/08/06/23/2A .md.mx` |
| `en_econo` | Econo | `e_3003.p_24` present |
| `en_spmode` | Special modes (Powerful/Econo menu) | `e_3003.p_20` present |
| `en_powchill` | Power Chill | `e_1003.e_3002.p_44` present |
| `en_quitemode` | Outdoor quiet | `e_1003.e_3002.p_3D` present |
| `en_intelligenteye` | Intelligent eye | `e_3003.p_6E` or `p_6F` present |
| `en_variable` | Variable capacity | `e_3003.p_B1` present |
| `en_led_brightness` | LED brightness | `e_3003.p_BC` present |
| `en_dewclean` | Dew clean | `e_3003.p_B2` present |
| `en_filter_sign` | Filter sign | `e_3001.p_15` present |
| `en_rtemp_a` | Relative setpoint in auto | `e_3003.p_28 ≠ 01` |
| `atlmt_l`, `atlmt_h`, `hmlmt_l` | Auto limits, heat low limit | `p_1F.md.mi/mx`, `p_03.md.mi` |
| `temp` | Outdoor temperature available | `e_1003.e_A00D.p_01` present |
| `elec` | Energy data | `e_A011.p_01 = 01` and `adp_i.func.en_ipower = 1` |
| `en_ipw_sep` | Separate cool/heat energy | `elec` and `adp_i.func.en_ipw_sep = 1` and `e_3003.p_2C = 01` |
| `en_mompow` | Momentary power | `e_1003.e_A005.p_01` present |
| `m_dtct` | Motion detection | `e_3003.p_27 = 01` |
| `disp_dry` | Dry display | `e_A006.p_14 = 01` |
| `en_ventilation`, `en_ventilation_category`, `en_ventilation_24hour_39`, `en_ventilation_24hour_3e` | Ventilation | `p_36`, `p_45`, `e_3003.p_39`, `e_3003.p_3E` present |
| `en_scdltmr` | Schedule timer | `adp_i.func.en_scdltmr` |
| `pv`, `cpv`, `cpv_minor` | Hard-coded to `3.40`, `3`, `40` | `GPFDataConverter.java:807-812` |
| Always 0 | `acled`, `land`, `temp_rng`, `dmnd`, `en_patrol`; `mid = NA` | `GPFRaDataConverter.java:7886,7934-7947,7981` |

### Error codes

`decodeError` (`GPFRaDataConverter.java:9285-9439`) builds the numeric `err` value in these steps:
1. **Prefix.** If `e_1002.e_A006.p_0D = "01"`, start with `"10"`.
2. **Code.** If `e_1002.e_3003.p_30 = "01"`, byte-reverse `e_3003.p_31` and read its first 2 bytes as ASCII. This gives a code such as `"U4"`.
3. **Number.** Encode the code as `firstLetter*16 + second`, printed as `%03d`:
   - first letter: A = 16, C = 32, E = 48, H = 64, F = 80, J = 96, L = 112, P = 128, U = 144
   - second character: a digit 0–9 is its value; A = 10, H = 11, C = 12, J = 13, E = 14, F = 15
4. If no error code is present, the code part is `000`.

For Home Assistant, simply read `p_30`, and when it is `01` decode `p_31` as reversed ASCII to get the Daikin code (e.g. `U4`, `A5`, `E7`).

### How the app writes control changes

- **Flow.**
  1. The UI builds a full DK control map. `racontrol/a.toMap` always emits `pow`, `mode`, `stemp`, `shum` and `adv`, plus every other key in its map (`racontrol/a.java:546-562`).
  2. `GPFRaDataConverter.encode` sends it to `encodeControlInfo`, passing the cached raw GPF map for the same device (`GPFRaDataConverter.java:9442-9458`).
- **Always written:**
  - `e_A002.p_01` (power).
  - `e_3003.p_2D` (power-change trigger: 00 on, 01 off, 02 unchanged).
  - `e_3001.p_01`, when `mode` is present. The one exception is `LND`, which writes `e_3003.p_25` instead.
- **Mode-dependent (only the current mode's properties):**
  - Setpoint: `p_03` heat, `p_02` cool, `p_1D` auto. Nothing is written for dry or fan.
  - Humidity mode, plus the value when the mode is `01`: `p_2D`/`p_2C`, `p_0C`/`p_0B`, `p_31`/`p_30`, `p_2F`/`p_2E`, `p_33`/`p_32`.
  - Fan: `p_0A`, `p_09` (auto when humidity control is on), `p_27` (always `0A00`), `p_26`, `p_2B`, `p_28`.
  - Air direction (vertical and horizontal), only if **both** `f_dir_ud` and `f_dir_lr` are present: `p_07`/`p_08`, `p_05`/`p_06`, `p_22`/`p_23`, `p_20`/`p_21`, `p_29`/`p_2A`, `p_24`/`p_25`.
- **Feature keys** are written only when that DK key is in the map: `en_streamer`→`p_20`, `good_sleep`→`p_1E`+`p_BA`+`p_BB`, `smell_proof`→`p_70`, `dew_clean`→`p_B2`, `intelligent_eye`→`p_6E`/`p_6F`, `variable`→`p_B1`, `quite_mode`→`e_1003.e_3002.p_3D`, `pow_chill`→`e_1003.e_3002.p_44`, `econo`→`p_24`, `filter_clean`→`p_BD`, `en_led_brightness`→`p_BC`, and `ventilation_*`→`p_36`/`p_1C`/`p_45`.
- **Short-circuit writes.** Three DK flags produce a write containing only their own properties:
  - `only_streamer` + `dew_clean` + `en_streamer`: only `p_20`.
  - `only_i_eye` + `intelligent_eye`: only `p_6E`/`p_6F`.
  - `only_dew_clean` + `dew_clean`: `p_B2`, plus `p_6F=00` and `p_6E=00`.

  Source: `RaSmali:11466-11800`.
- **Intelligent-eye encoding** (DK `intelligent_eye` value → `p_6F`, `p_6E`):
  - `0` → 01, 01
  - `1` → 00, 01
  - `2` → 01, 00
  - `3` → 00, 00
  - `4` → only `p_6E=00`
  - `5` → only `p_6F=00`

  Source: `RaSmali:11568-11710`, ≈`14140-14320`.
- **Not written anywhere by this app:** `e_3003.p_1B` (Powerful; no UI path sends Powerful, and `RequestType.DKSpecialMode` is unused), `p_1C`, `p_21`, `p_64`, `p_22`, `p_65`, and `e_3001.p_1E` (dry offset). Modes `0009`/`000A` are never written either. **[inferred]** Powerful can probably be set by writing `e_3003.p_1B="01"`, mirroring Econo's `p_24`, but this has not been verified.
- **Split between indoor and outdoor.** `GPFControlInfoController.set` removes `dgc_status.e_1003.e_3002.p_3D` and `p_44` from the batch. It sends everything else as one `op:3` PUT to `/<adr_01xx>.dgc_status`, then sends the two outdoor keys **2 seconds later** in a separate PUT to `/<adr_02xx>.dgc_status` (`GPFControlInfoController.java:114-141`, `33-40`).
- **Write body.** The flat keys are split on `.` into a nested `pn`/`pch` tree. Leaves become `{"pn":..,"pv":..}` with no `pt`, and the request is `op:3` (`GPFBaseController.java:217-281,438-466,575-589`).
- **UI layer** (`wwapp/view/unitcontrol/ra/RaUnitCtrlFragment.java:711-981`, `J2()`). Every action rebuilds a map; it is not a copy of the last read. The map contains:
  - `mode` and `pow`;
  - `stemp` (from a per-mode cache) and `shum`;
  - `f_dir_ud` and `f_dir_lr`, copied from the current state if the action did not supply them;
  - `type=RA`;
  - the action's own keys. `f_rate` is sent only when fan speed changes; `adv` and feature flags are never copied from state.

  Side effects of particular actions:
  - **Power off** also sends `dew_clean=0`, which writes `p_B2=00`.
  - **Power on** re-sends `en_streamer=1` if the streamer was on.
  - **Power off while in Dry** sends mode Cool with pow 0.
  - **Power Chill on** also sends `f_dir_ud=0`, `variable=0` and `quite_mode=0`.

  Requests are debounced by 1 s (`p170z0/b.java:121-131`). After each set the app re-reads the full status (DKExpandCh), and it also polls every 60 s (`p170z0/b.java:187`).
- **Not a diff.** The full DK state goes into the encoder, so power, mode, setpoint, humidity, fan and air direction for the current mode are **always** rewritten, even when only one of them changed. Feature keys are sent only when present in the DK map.

### Example writes

In the examples below, `<base>` is `/dsiot/edges/<ri>` (cloud) or `/dsiot/edge` (local).

**Power off.** The app also re-sends mode, setpoint, fan and air direction; only these two properties are needed:
```json
{"requests":[{"op":3,"to":"<base>/adr_0100.dgc_status","pc":{"pn":"dgc_status","pch":[{"pn":"e_1002","pch":[
  {"pn":"e_A002","pch":[{"pn":"p_01","pv":"00"}]},
  {"pn":"e_3003","pch":[{"pn":"p_2D","pv":"01"}]}]}]}}]}
```

**Power on, cool, 24.5 °C, fan auto, vertical swing, horizontal fixed.** This is what the app's encoder produces:
```json
{"requests":[{"op":3,"to":"<base>/adr_0100.dgc_status","pc":{"pn":"dgc_status","pch":[{"pn":"e_1002","pch":[
  {"pn":"e_A002","pch":[{"pn":"p_01","pv":"01"}]},
  {"pn":"e_3003","pch":[{"pn":"p_2D","pv":"00"}]},
  {"pn":"e_3001","pch":[
    {"pn":"p_01","pv":"0200"},
    {"pn":"p_02","pv":"31"},
    {"pn":"p_0C","pv":"00"},
    {"pn":"p_09","pv":"0A00"},
    {"pn":"p_05","pv":"0F0000"},
    {"pn":"p_06","pv":"000000"}]}]}]}}]}
```
The `p_0C` line is only present if the unit has cool humidity control.

**Heat, 22 °C, fan level 3.**
```json
{"pn":"e_3001","pch":[{"pn":"p_01","pv":"0100"},{"pn":"p_03","pv":"2c"},{"pn":"p_0A","pv":"0500"}]}
```

**Auto with a +1 °C offset and quiet fan.**
```json
{"pn":"e_3001","pch":[{"pn":"p_01","pv":"0300"},{"pn":"p_1D","pv":"02"},{"pn":"p_26","pv":"0B00"}]}
```

**Dry.** The app writes no setpoint and forces fan auto:
```json
{"pn":"e_3001","pch":[{"pn":"p_01","pv":"0500"},{"pn":"p_27","pv":"0A00"}]}
```

**Fan mode, level 5, 3D swing.**
```json
{"pn":"e_3001","pch":[{"pn":"p_01","pv":"0000"},{"pn":"p_28","pv":"0700"},{"pn":"p_24","pv":"0F0000"},{"pn":"p_25","pv":"0F0000"}]}
```

**Econo on / streamer on** (indoor unit):
```json
{"pn":"e_3003","pch":[{"pn":"p_24","pv":"01"}]}
{"pn":"e_3003","pch":[{"pn":"p_20","pv":"01"}]}
```

**Power Chill or outdoor quiet** (outdoor unit, separate request):
```json
{"requests":[{"op":3,"to":"<base>/adr_0200.dgc_status","pc":{"pn":"dgc_status","pch":[{"pn":"e_1003","pch":[
  {"pn":"e_3002","pch":[{"pn":"p_44","pv":"01"}]}]}]}}]}
```
For quiet, use `{"pn":"p_3D","pv":"01"}` in place of the `p_44` entry.

**Powerful** (**[inferred]**; the app never sends this):
```json
{"pn":"e_3003","pch":[{"pn":"p_1B","pv":"01"}]}
```

### Corrections to the existing API.md table

1. **Mode 0009/000A.** They are no longer unknown. The app treats `0009` as a cool-family state (it uses `p_02`, `p_09`, `p_05` and `p_06`) and `000A` as a heat-family state (`p_03`, `p_0A`, `p_07` and `p_08`). The app shows no mode for either and never writes them; see the mode table.
2. **Setpoint encoding.**
   - `p_02`/`p_03`: correct as °C×2, but they are 1 byte and the app writes them as lowercase hex without padding.
   - `p_1D`/`p_1E`: signed int8 offsets in 0.5 °C units (so `02` = +1 °C), and **`p_1E` is never written** by the app.
3. **Fan speed.** Values are LE 2-byte: `0300`–`0700` are levels 1–5, `0A00` auto, `0B00` quiet. The encoding in API.md is right, but note that in **dry** the app always sends `0A00`, and in cool it forces `0A00` whenever humidity control is on.
4. **Swing.**
   - API.md shows the full vertical enum; add `110000` reverse, `120000` insensitive, `130000` natural, `140000` circulation and `170000` "nice".
   - Fixed positions are bits in `md.mx`, so the UI's step number is not the raw value.
   - For **horizontal**, the app only uses `000000` (fixed, preserving the current position), `0F0000` (swing) and `100000` (auto).
   - On read, **fan mode checks `p_20.md.mx`**, while the write uses `p_24.md.mx`.
5. **Room temperature `e_A00B.p_06`.** Correct (int16 LE × 0.5). **Room humidity `p_02`** is a single unswapped byte in percent.
6. **Compressor frequency** is LE uint; **outdoor temperature** is on the outdoor unit (`adr_0200`) as signed int16 × 0.5. Both correct.
7. **Econo / streamer.** Correct (`e_3003.p_24` / `p_20`). Add that **`e_3003.p_1B` is Powerful** (read-only in the app).
8. **Quiet / Power Chill.** Correct (`e_1003.e_3002.p_3D` / `p_44` on `adr_0200`). The app sends them in a **separate PUT 2 s after** the indoor write.
9. **Missing from API.md:**
   - the mandatory `e_3003.p_2D` power-change trigger;
   - the humidity modes and values;
   - LED brightness `p_BC`, dew clean `p_B2`, intelligent eye `p_6E`/`p_6F`, good sleep `p_1E`/`p_BA`/`p_BB`, smell-proof `p_70`, variable capacity `p_B1`, filter clean `p_BD`, filter sign `e_3001.p_15`;
   - error codes `e_3003.p_30`/`p_31`, momentary power `e_1003.e_A005.p_01`;
   - ventilation `p_36`/`p_1C`/`p_45`/`e_3003.p_39`/`p_3E`;
   - identity keys `e_A001.*`, and the `md.mx` capability bitmask convention.
10. **Humidify mode.** `0800` is correct, but it is only offered when `p_01.md.mx` bit 8 is set.
11. **Example write.** API.md writes the cool-mode fan with `p_09` and swing with `p_05`/`p_06`, which is correct. The app would also include `e_3003.p_2D`.

### Remaining unknowns

- Whether `0009`/`000A` are the running state inside Auto or distinct modes. Confirming this needs live traffic.
- The exact physical meaning of `p_1C` (HotWind?) and of humidity mode `05` (BeautifulSkin?).
- The meaning of `e_3003.p_2D` beyond "power-change trigger".
- Whether Powerful can be written through `p_1B`.
- Units for `mompow`.
- The JSON type of `md.st`: the app parses it as a decimal integer.
## Room AC (Ra) auxiliary features over DSIOT

This section covers the Ra features outside the basic control and status map: weekly schedule, ventilation, patrol, energy history, electricity price and target, filter-sign reset, and sensor and model reads.

Every feature here uses the same `/dsiot/multireq` envelope as the core protocol. Reads are `POST` with `op:2` and writes are `PUT` with `op:3`.

Paths are built as `<base>/<indoor>.<resource>` or `<base>/<outdoor>.<resource>`:
- `<base>` is `/dsiot/edges/<ri>` in the cloud and `/dsiot/edge` locally.
- `<indoor>` is the object address that starts with `adr_01`, normally `adr_0100`.
- `<outdoor>` is the address that starts with `adr_02`, normally `adr_0200`.
- Source: `dknetlib/gpf/net/GPFBaseController.java:797-838`.

Citations use these conventions: `dknetlib/` stands for `jp/co/daikin/dknetlib/`, `wwapp/` for `jp/co/daikin/wwapp/`, and smali paths are relative to `decompiled/smali`.

### How the app builds write bodies (applies to every write below)

`createJson(to, map, false)` (`GPFBaseController.java:575`) takes a flat map of dotted keys:
- It splits each key on `.` (`createMap`, `:217`).
- The **first segment becomes `pc.pn`**. The remaining segments become nested `pch` entries (`getJsonForRequest`, `:438`; `createPch`, `:268`).
- Leaves are sent as `{"pn":..,"pv":..}` without `pt`, because nulls aren't serialized.
- A `pv` may be a string, a JSON number, a JSON array or a JSON object. The type of the Java value decides which.

Example: the key `price.int=12` becomes `pc = {"pn":"price","pch":[{"pn":"int","pv":12}]}`.

Responses are flattened the same way, into `"<pc.pn>.<child>.<leaf>" → pv-as-string` (`getMapForResponse`, `:667`, `:866ff`). A `pv` that is a JSON array or object is kept as its JSON text.

### Where the data comes from: `expand=ch` versus per-resource reads

The app reads most of this state in one call: `op:2` on `/dsiot/edges/<ri>?expand=ch` in the cloud, or `/dsiot/edge` locally (`dknetlib/gpf/net/request/GPFExpandChController.java:44-67`).
- The `pch` of every child object (`adr_0100`, `adr_0200`) is flattened **without** the `adr_xxxx` prefix. The result contains keys such as `dgc_status.e_1002…`, `scdl_t.info`, `scdl_t.body.mo`, `i_power.week_power.datas` and `history.h_01.data` (`GPFBaseController.java:681-691`).
- `GPFRaDataConverter.decode` for `DKExpandCh` (`gpf/data/GPFRaDataConverter.java:9209-9232`) decodes the model, control and sensor data from that one map.
  - It decodes the schedule **only if `adp_i.func.en_scdltmr == "1"`** (`:9219`).
  - It always decodes energy (`:9224`).
- That is why `GPFRaConvertValue` carries `_EX` keys (`scdl_t.body.mo`, `i_power.week_power.datas`), used for expand=ch, alongside short keys (`body.mo`, `week_power.datas`), used for single-resource reads (`gpf/data/GPFRaConvertValue.java:88-113`).

### Capability flags (from model info or expand=ch)

| DK flag | Source | Rule | Ref |
|---|---|---|---|
| `en_scdltmr` (schedule supported) | `adp_i.func.en_scdltmr` | copied through (`"1"` means supported) | `GPFRaDataConverter.java:7977-7978`, `GPFRaConvertValue.java:44` |
| `elec` (energy screens) | `adp_i.func.en_ipower` **and** `dgc_status.e_1002.e_A011.p_01` | both must hold: `en_ipower=="1"` and `p_01=="01"` | `GPFRaDataConverter.java:7937` |
| `en_mompow` (instant power) | `dgc_status.e_1003.e_A005.p_01` | present means supported | `:7979-7980` |
| `en_patrol` | (the enum maps `e_1002.e_A011.p_05`) | **hard-coded `"0"` for GPF Ra** | `:7981` |
| `dmnd` (demand / power saving) | none | **hard-coded `"0"` for GPF Ra** | `:7947` |
| `en_ventilation` | `dgc_status.e_1002.e_3001.p_36` | present and non-blank | `:7899-7900` |
| `en_ventilation_category` | `dgc_status.e_1002.e_3001.p_45` | present and non-blank | `:7901-7902` |
| `en_ventilation_24hour_39` / `_3E` | `dgc_status.e_1002.e_3003.p_39` / `p_3E` | present and non-blank | `:7888-7891` |
| `en_ventilation_24hour_3E.md.mx` | `…e_3003.p_3E.md.mx` | parsed as a decimal int (likely the highest allowed 24-hour mode) **[inferred]** | `:7892-7897` |
| `en_filter_sign` | `dgc_status.e_1002.e_3001.p_15` | present means supported | `:7984` |

---

## Weekly schedule timer (`scdl_t`)

This is the only timer-like feature the app implements over DSIOT for Ra.

**No DSIOT on/off timer, sleep timer, holiday mode or temperature program.** The old on/off timer (`wwapp/view/oldtimer`, `RaOldTimerElement`), holiday (`wwapp/view/holiday`), temperature program (`wwapp/view/tempprogram`) and power-saving/demand (`wwapp/view/powersaving`) screens use `DKTimerSetting`, `DKHolidaySetting`, `DKProgramSetting` and `DKDemandSetting`. The GPF dispatcher `E4/K.java` has **no case** for those request types in its get path (`:148-292`) or its set path (`:713-1047`), so they only reach older devices through the legacy protocol: `/aircon/get_timer|set_timer`, `/common/get_holiday`, `/aircon/get_program|set_program`, `/aircon/get_demand_control|set_demand_control`. `GPFRaDataConverter` contains no timer keys other than `en_scdltimer`.

### Resources

| Operation | op | `to` | Ref |
|---|---|---|---|
| Read info | 2 | `<base>/adr_0100.scdl_t.info?filter=pv,md` | `dknetlib/gpf/net/request/common/GPFScheduleTimerController.java:33-44` |
| Read body | 2 | `<base>/adr_0100.scdl_t.body?filter=pv,md` | `…/GPFScheduleTimerController.java:20-31` |
| Write info | 3 | `<base>/adr_0100.scdl_t.info` | `…/airconditioner/GPFRaScheduleTimerController.java:227-257` |
| Write body | 3 | `<base>/adr_0100.scdl_t.body` | `…/GPFRaScheduleTimerController.java:59-225` |

RequestType dispatch: `DKScheduleTimerInfoSetting` maps to getInfo/setInfo and `DKScheduleTimerBodySetting` maps to getBody/setBody (`E4/K.java:204-227`, `:779-802`).

### `scdl_t.info`

This is a **single leaf whose `pv` is a JSON object**, not hex.

| Field | Type | Meaning |
|---|---|---|
| `per_day` | int | Maximum entries per weekday. The app always writes `6`, and the UI refuses a 7th entry (`wwapp/view/schedule/RaScheduleSettingFragment.java:439`). |
| `en_scdltimer` | int 0/1 | Master enable. |
| `name` | string | Schedule name. The app always writes `""`. |

The app writes it like this (`GPFRaScheduleTimerController.java:242-247`):
```json
{"requests":[{"op":3,"to":"/dsiot/edges/<ri>/adr_0100.scdl_t.info",
  "pc":{"pn":"info","pv":{"per_day":6,"en_scdltimer":1,"name":""}}}]}
```

- `en_scdltimer` is derived from the DK key `info.en_scdltimer` (`GPFRaDataConverter.encodeScheduleTimer`, `:8842-8846`).
- The DK encoder **always sends `"1"`** (`dk/data/DKRaDataConverter.java:1135-1146`).
- The app therefore turns a schedule "off" by clearing every entry's enable byte, via `RaScheduleTimerElement.D()` (`wwapp/view/schedule/RaScheduleTimerElement.java:53-62`), not by writing `en_scdltimer:0` **[inferred from UI flow]**.

When read, the response `pv` is parsed with `JSONObject` (`GPFRaDataConverter.decodeScheduleTimer`, `:8346-8370`; smali `jp/co/daikin/dknetlib/gpf/data/GPFRaDataConverter.smali:9690`). The decoder fabricates the fixed values `format=v1`, `scdl_num=3` and `active_no=1`. **GPF Ra supports only one schedule pattern**, while legacy devices support up to three.

Expected response (`pt` inferred):
```json
{"responses":[{"fr":"/dsiot/edges/<ri>/adr_0100.scdl_t.info","rsc":2000,
  "pc":{"pn":"info","pt":3,"pv":{"per_day":6,"en_scdltimer":1,"name":""}}}]}
```

### `scdl_t.body`

This is a container with seven leaves: `su mo tu we th fr sa`. Each leaf's `pv` is a **JSON array of 18-character ASCII strings**, one string per timer entry, with at most `per_day` (6) entries.

Body write, built by `setBody`, which turns each `body.<day>` value into a Gson `JsonArray` (`GPFRaScheduleTimerController.java:78-224`):
```json
{"requests":[{"op":3,"to":"/dsiot/edges/<ri>/adr_0100.scdl_t.body",
  "pc":{"pn":"body","pch":[
    {"pn":"su","pv":[]},
    {"pn":"mo","pv":["103901225.0A3-----","113200----------"]},
    {"pn":"tu","pv":[]}, {"pn":"we","pv":[]}, {"pn":"th","pv":[]},
    {"pn":"fr","pv":[]}, {"pn":"sa","pv":[]}]}}]}
```

- The app always sends all seven days (`encodeScheduleTimer`, `:8848-8966`).
- It emits each day's entries in HashMap iteration order (`DKRaDataConverter.java:1052-1055`), so the entries are **not guaranteed to be time-sorted**. Sorting them by time is the safe choice **[inferred]**.
- An empty day is `[]`.

The second `mo` entry above is a hypothetical 22:00 off entry and is **[inferred]**: the app's exact mode, temperature and fan bytes for an off entry weren't traced.

#### Entry string layout (GPF wire order, character offsets)

Sources: decode `GPFRaDataConverter.java:8373-8425` plus smali `jp/co/daikin/dknetlib/gpf/data/GPFRaDataConverter.smali:9690-10395` (the mode switch, which jadx garbled); encode `GPFRaDataConverter.java:8848-8960`.

| Offset | Len | Field | Values |
|---|---|---|---|
| 0 | 1 | entry enable | `0` / `1` |
| 1–4 | 4 | time | **minutes after 00:00**, zero-padded decimal (`%04d`): `0390` = 06:30, `1320` = 22:00. Range `0000`–`1439`. (`DKRaDataConverter.java:1078`; `G/C0054q.java:42-48`; `dknetlib/core/data/schedule/a.java:c()`) |
| 5 | 1 | power | `1` = start or run, `0` = stop |
| 6 | 1 | mode | `0` fan, `1` heat, `2` cool, `3` auto, `5` dry, `8` humidify. Anything else, including `-`, decodes to "unknown". |
| 7–10 | 4 | setpoint | ASCII decimal °C with one decimal place: `25.0`, `18.5`. `----` means none (the UI sends this for fan, dry and off entries). `M000`, `L000` and `H000` are relative levels (0 / −1 / +1 step) that the UI uses for auto and humidify mode (`RaScheduleSettingFragment.java:492-515`; `DKRaDataConverter.java:1060-1076`). |
| 11 | 1 | fan speed | `3`–`7` = level 1–5, `A` = auto, `B` = silent/quiet, `-` = unset (`DKRaDataConverter.java:157-199`) |
| 12 | 1 | airflow / swing | `0` = no swing, `1` = vertical swing, `2` = horizontal swing, `3` = both (3-D), `-` = unset (`E4/C0029d.java:368-380`; `RaScheduleSettingFragment.java:1098-1111`) |
| 13–15 | 3 | humidity | `%03d` percent (`040`), `---` = none, `A_L` / `A_N` / `A_H` = auto low / normal / high, `CNT` = continuous (`DKRaDataConverter.java:201-222`; smali `jp/co/daikin/dknetlib/dk/data/DKRaDataConverter.smali:593`) |
| 16 | 1 | special mode | `1` = powerful, `2` = econo, `3` = streamer, `-` = none (`DKRaDataConverter.java:424-478`; `core/data/racontrol/DKNetRaSpecialModeType.java`) |
| 17 | 1 | special mode on/off | `1` / `0`; `-` when the special mode is `-` |

The app keeps the internal ("DK") string in a different order and permutes it on the way in and out:
- DK order: `en, pow, mode, temp4, time4, fan, swing, hum3, sp, sppow`.
- The mapping is GPF[0]=DK[0], GPF[1:5]=DK[7:11], GPF[5]=DK[1], GPF[6]=mode(DK[2]), GPF[7:11]=DK[3:7], GPF[11:18]=DK[11:18].
- DK strings may carry 10 extra characters (`fhd`/`fvd`, `DKRaDataConverter.java:1508-1511`). The GPF encoder **truncates them to 18**.

Mode mapping between the DK and GPF encodings (smali pswitch at `jp/co/daikin/dknetlib/gpf/data/GPFRaDataConverter.smali:10389`; encode `:8864-8930`):

| GPF char | DK char | App mode (DKNet) |
|---|---|---|
| `3` | `1` (also `0`, `7` when encoding) | auto (0) |
| `2` | `3` | cool (1) |
| `1` | `4` (also `5` when encoding) | heat (2) |
| `0` | `6` | fan (3) |
| `5` | `2` | dry (4) |
| `8` | `H` | humidify (5) |
| `-` | DK `L` (laundry) or unknown | not representable |

Example, Monday 06:30, on, cool, 25 °C, fan auto, 3-D swing, no humidity, no special mode:
`1` `0390` `1` `2` `25.0` `A` `3` `---` `-` `-` → **`103901225.0A3-----`**

#### Read flow in the app

1. `DKModelInfo`, `DKBasicInfo`, then `DKScheduleTimerInfoSetting` (a GET of info). Code: `dknetlib/e.java:92-96`, `:36-40`, `:148-152`, wrapped by `DKApiParallel$getScheduleListRa$1$totalTime$1$deferredList$1..3`.
2. A GET of body, keyed `target` (`wwapp/view/unitcontrol/ra/K.java:198-214`).
3. Alternatively, `DKExpandCh` supplies `scdl_t.info` and `scdl_t.body.*` in one call (`wwapp/view/schedule/ScheduleTimerMainFragment.java:565`).

The GainSpan variant (`DKApiParallel$getScheduleListRaGainSpan…deferredList$3.java:43`) uses the legacy `DKTimerSetting` instead.

#### Write flow in the app

1. Write info with `en_scdltimer:1`.
2. After `rsc` OK, write the body containing all seven days (`RaScheduleSettingFragment.java:480-489`; `E4/C0029d.java:332-416`).

---

## Ventilation (models with a ventilation unit)

All ventilation settings are ordinary `dgc_status` properties. There is no GET controller: the values arrive through the normal control and status read or expand=ch. Writes go to `<base>/adr_0100.dgc_status` (`dknetlib/gpf/net/request/airconditioner/GPFRaVentilationController.java`, `…24hourController.java`, `…CategoryController.java`, all `set()`). The RequestTypes are `DKVentilation`, `DK24HourVentilation` and `DKVentilationCategory` (`E4/K.java:1033-1039`).

| Key (under `dgc_status.`) | DK name | Encoding | Ref |
|---|---|---|---|
| `e_1002.e_3001.p_36` | `ventilation_power` | 1 byte: `00` off, `01` on | `GPFRaConvertValue.java:69`; `core/data/racontrol/DKNetRaVentilationPowerType.java` |
| `e_1002.e_3001.p_1C` | `ventilation_speed` | `01` high, `02` auto | `:70`; `DKNetRaVentilationSpeedType.java` |
| `e_1002.e_3001.p_45` | `ventilation_category` | `00` supply, `01` exhaust, `02` auto | `:71`; `DKNetRaVentilationCategory.java` |
| `e_1002.e_3003.p_39` **or** `p_3E` | `ventilation_24hour` | `00` off, `01` on with turbo, `02` on without turbo | `:67-68`; `DKNetRaVentilation24hourType.java` |
| `e_1002.e_3003.p_2D` | (written alongside) | `02` on every ventilation write | see the note below the table |

Note on `p_2D`: `GPFVRVDataConverter.java:1956` sets it to `00` when the write turns the unit on, `01` when it turns the unit off, and `02` when power is unchanged. It is **[inferred]** to be the same "power-change" flag for Ra.

- **Decoding:** each value is parsed as **decimal** (`kotlin.text.q.y`, radix 10) from the hex string. That works because all the values are below 10 (`GPFRaDataConverter.decodeVentilation…`, `:8508-8560`).
- **Encoding:** values are written as `%02X`.

Which keys each ventilation write sends:

| App action | Keys written | Ref |
|---|---|---|
| Ventilation power off | `p_36="00"`, `p_2D="02"` | `encodeVentilation`, `:8986-9051`; smali `jp/co/daikin/dknetlib/gpf/data/GPFRaDataConverter.smali:16487` |
| Ventilation power on | `p_36="01"` and `p_1C` (`01`/`02`, required); `p_45` only if the category is supply `00` or auto `02`; plus `p_2D="02"` | same |
| Category screen | `p_36` (current power) and `p_45` (`00` supply or `01` exhaust only); plus `p_2D="02"` | `encodeVentilationCategory`, `:9054-9083` |
| 24-hour ventilation | `p_39` if the model reports `p_39`, else `p_3E` if it reports `p_3E`; plus `p_2D="02"` | `encode24HourVentilation`, `:8562-8581` |

Example: turn ventilation on, speed auto, category auto.
```json
{"requests":[{"op":3,"to":"/dsiot/edges/<ri>/adr_0100.dgc_status","pc":{"pn":"dgc_status","pch":[
  {"pn":"e_1002","pch":[
    {"pn":"e_3001","pch":[{"pn":"p_36","pv":"01"},{"pn":"p_1C","pv":"02"},{"pn":"p_45","pv":"02"}]},
    {"pn":"e_3003","pch":[{"pn":"p_2D","pv":"02"}]}]}]}}]}
```

---

## Patrol (temperature patrol / monitoring)

**Model info forces `en_patrol` to `"0"` for GPF Ra** (`GPFRaDataConverter.java:7981`), so the patrol UI is hidden on India DSIOT units. The protocol is still implemented:
- Code: `dknetlib/gpf/net/request/airconditioner/GPFPatrolController.java`; dispatch at `E4/K.java:265-292` (get) and `:763` (set).
- The enable flag is mapped to `dgc_status.e_1002.e_A011.p_05` (`GPFRaConvertValue.java:46`).

| Resource | GET `to` | SET | RequestType | Keys (flattened as `<pn>.<leaf>`) → DK |
|---|---|---|---|---|
| setting | `<base>/adr_0100.patrol.setting?filter=pv,md` | `<base>/adr_0100.patrol.setting` | `DKPatrolSetting` | `setting.mode` → `patrol_mode`, `setting.hi_stemp` → `patrol_hi_stemp`, `setting.lo_stemp` → `patrol_lo_stemp` |
| status | `….patrol.status?filter=pv,md` | – | `DKPatrolStatus` | `status.status` → `patrol_status` |
| spec | `….patrol.spec?filter=pv,md` | – | `DKPatrolSpec` | `spec.hi_temp_min`, `spec.hi_temp_max`, `spec.lo_temp_min`, `spec.lo_temp_max` |
| notify | `….patrol.notify?filter=pv,md` | `….patrol.notify` | `DKPatrolAutoOffNotice` | `notify.off_flg` → `patrol_off_flg` (`"1"` means auto-off happened), `notify.off_tm` → `patrol_off_tm` |

Key mapping: `GPFRaConvertValue.java:114-123`. Path builder: `GPFPatrolController.java:44-59`, `:95-112`.

**Encoding.** Values are **decimal integers, not hex**:
- `Q4/a.java:40-80` parses them with `Integer.parseInt`, and a missing value becomes −99.
- The app writes them as JSON **strings**, such as `"pv":"300"` (`dk/data/DKRaDataConverter.java:1148-1157`).
- Whether the device returns numbers or strings is **[unverified]**.

| Field | Values |
|---|---|
| `setting.mode` | `0` off, `1` low-temperature patrol, `2` high-temperature patrol (`core/data/patrol/DKNetRaPatrolOperationModeType.java`; UI `wwapp/view/unitcontrol/ra/G.java:89-100`) |
| `status.status` | `0` off, `1` standby, `2` monitoring, `3` running (`DKNetRaPatrolOperationStatusType.java`) |
| `*_stemp`, `spec.*` | **°C × 10**. The UI shows `value/10` (`wwapp/view/unitcontrol/ra/RunnableC0847z.java:41-55`, `G.java:189-190`) and writes `°C×10` (`DKRaDataConverter.java:1152-1153`). |

Example write: low-temperature patrol at 10 °C, high at 30 °C.
```json
{"requests":[{"op":3,"to":"/dsiot/edges/<ri>/adr_0100.patrol.setting",
 "pc":{"pn":"setting","pch":[{"pn":"mode","pv":"1"},{"pn":"lo_stemp","pv":"100"},{"pn":"hi_stemp","pv":"300"}]}}]}
```

---

## Energy consumption

These screens are shown when `elec=1` (see the capability table). `RequestType.DKPowerUse` fires three reads in parallel (`E4/K.java:243-246`); expand=ch provides the same data.

| Read | `to` | Response keys (single read) | Keys in expand=ch | Ref |
|---|---|---|---|---|
| Week | `<base>/adr_0100.i_power.week_power?filter=pv,md` | `week_power.today_runtime`, `week_power.datas` | `i_power.week_power.*` | `…/airconditioner/GPFPowerConsumptionOfWeek.java` |
| Year | `<base>/adr_0100.i_power.year_power?filter=pv,md` | `year_power.this_year`, `year_power.previous_year` | `i_power.year_power.*` | `…/GPFPowerConsumptionOfYear.java` |
| Month (daily history) | `<base>/adr_0200.history.h_01.data` (**outdoor unit**, no filter) | converter expects `history.h_01.data` | `history.h_01.data` | `…/GPFPowerConsumptionOfMonth.java` |

On the month read: a single read of `…history.h_01.data` presumably returns `pc.pn = "data"`, which the converter doesn't map. In practice the month data probably only arrives via expand=ch **[inferred]**.

**Conversion.** `GPFRaDataConverter.decodePowerConsumption` (`:8262-8315`) joins each JSON array into `/`-separated text (`encodeConsumption`, `:8583-8611`):
- `datas` is padded to 7 values.
- `this_year` and `previous_year` are padded to 12.
- `month_pow` keeps its own length, or 96 if empty.
- `today_runtime` is passed through unchanged.

The data manager then splits the values back out (`dk/data/DKRaDataConverter.java:605-647`, `:1239-1320`).

| Key | Array element encoding | Layout | Unit |
|---|---|---|---|
| `today_runtime` | decimal int | scalar | **minutes** of operation today. The UI shows `v/60` h `v%60` min (`wwapp/view/consumption/ShowInstPowerFragment.java:627-628`). |
| `datas` | **decimal** JSON numbers, 7 of them | Rolling last 7 days, **`datas[6]` = today**, `datas[6-k]` = k days ago. The app rebuilds a "this week" array (index 0 = Sunday, up to today) and a "last week" array (only the days not in this week are filled; the rest are 0) (`DKRaDataConverter.java:617-644`). | **Wh**. The UI shows `v/1000` as kWh with one decimal (`ShowInstPowerFragment.java:351-355`, `:633-638`). |
| `this_year` / `previous_year` | **decimal** JSON numbers, 12 of them | index 0 = January … 11 = December. The UI indexes by `Calendar.MONTH` (`:647-653`). | Unit unresolved: the text shows the raw value as an integer "kWh" (`:434-441`), but the bar chart draws it unscaled, like month (0.1 kWh) (`wwapp/view/consumption/GraphMaker.java:251-283`). **[unverified]** |
| `history.h_01.data` → `month_pow` | **hex little-endian** strings; bytes are swapped before parsing (`dknetlib/b.java:a()`, `DKRaDataConverter.java:1260-1320`) | Chronological daily history, oldest first, **last element = yesterday**. This month = the last `(today−1)` elements mapped to days 1..today−1; last month = the elements before those, right-aligned so the final one is the last day of the previous month. The array is typically longer than 31 elements; the empty default is 96. | **0.1 kWh**. The UI shows `v/10` kWh (`ShowInstPowerFragment.java:405-408`). |

Example (values illustrative):
```json
{"responses":[{"fr":"/dsiot/edges/<ri>/adr_0100.i_power.week_power","rsc":2000,
 "pc":{"pn":"week_power","pt":1,"pch":[{"pn":"today_runtime","pt":3,"pv":95},
   {"pn":"datas","pt":3,"pv":[1200,800,0,450,2300,1900,640]}]}}]}
```
Here today's runtime is 1 h 35 min, today's energy is 0.64 kWh and yesterday's is 1.9 kWh. `pt` and the numeric `pv` types are **[inferred]** from the parsing code.

Instant power (`mompow`) comes from the core status map at `dgc_status.e_1003.e_A005.p_01`. It is an LE hex value converted with `floor((raw*10+100)/100)` into 0.1 kW units (`GPFRaDataConverter.java:8476-8479`; UI `wwapp/view/consumption/c.java:105-115`, which shows `n*0.1 kW` and "0.1 kW or less" when n ≤ 1). The raw value is therefore probably in 10 W units **[inferred]**.

---

## Electricity unit price and cost target

| Item | GET | SET | Keys (DK ↔ GPF) | Ref |
|---|---|---|---|---|
| Unit price | `<base>/adr_0100.price?filter=pv,md` | `<base>/adr_0100.price` | `price_int` ↔ `price.int`, `price_dec` ↔ `price.dec` | `…/airconditioner/GPFElectricityUnitPriceController.java`; `GPFRaConvertValue.java:102-103` |
| Target | `<base>/adr_0100.target?filter=pv,md` | `<base>/adr_0100.target` | `target` ↔ `target` | `…/GPFTargetElectricityPriceController.java`; `:104` |

RequestTypes are `DKPowerPrice` and `DKPowerTarget` (`E4/K.java:237-241`, `:804-810`).

- **Encoding:** plain **JSON integers**. The set path does `Integer.parseInt` before `createJson` (`GPFElectricityUnitPriceController.java:74`, `GPFTargetElectricityPriceController.java:74`). Reads keep only `price.int`; `price.dec` is dropped (`GPFRaDataConverter.java:8303-8310`; `DKRaDataConverter.java:791-810`).
- **App ranges:**
  - Price is `1`–`50` currency units per kWh; the UI clamps it (`p099o5/j.java:91-101` (clamp at `:95`), `ShowInstPowerFragment.java:239-248`). `price.dec` is always sent as `0` (`p099o5/m.java:44-49`).
  - Target is `0`–`10000` in steps of `100`, where `0` means "not set" (`ShowInstPowerFragment.java:224-235`, `p099o5/m.java:61-64`, `:81`). It is drawn as a horizontal line on the **year** chart only (`GraphMaker.java:363-365`, `:429-441`). That makes it presumably a monthly cost target **[inferred]**.
- **Currency:** the device doesn't store it. The app takes the symbol from the locally selected country (`CountryData.getCurrency_symbol()` from `selected_country_info`, `ShowInstPowerFragment.java:202-206`). Cost is computed on the client as kWh × `price.int`.

```json
{"requests":[{"op":3,"to":"/dsiot/edges/<ri>/adr_0100.price","pc":{"pn":"price","pch":[{"pn":"int","pv":8},{"pn":"dec","pv":0}]}}]}
{"requests":[{"op":3,"to":"/dsiot/edges/<ri>/adr_0100.target","pc":{"pn":"target","pv":2000}}]}
```

---

## Sensor info, model info, filter sign (resource list)

| Controller | Requests (one multireq) | Notes / Ref |
|---|---|---|
| `GPFSensorInfoController.get` (`DKSensorInfo`) | op 2: `<base>.dev_i?filter=pv`, `<base>/adr_0100.dgc_status?filter=pv`, `<base>/adr_0200.dgc_status?filter=pv` | `dknetlib/gpf/net/request/airconditioner/GPFSensorInfoController.java:31`. Decoded fields (`GPFRaDataConverter.decodeSensorInfo`, `:8434-8505`): `htemp` = `e_1002.e_A00B.p_06` as signed int16 LE ×0.5 (or ×1 for group `PA`); `hhum` = `e_A00B.p_02` hex; `otemp` = `e_1003.e_A00D.p_01` ×0.5; `cmpfreq` = `e_1003.e_2006.p_04`; `mompow` (above); `filter_sign` = `e_3001.p_15=="01"`; `water_internal_cleaning` = `e_3003.p_52`. No separate Ra air-quality resource exists; `GPFCjAirQualityController` is for air purifiers only. |
| `GPFModelInfoController.get` (`DKModelInfo`) | op 2: `<base>.adp_i?filter=pv`, `<base>.dev_i?filter=pv`, `<base>/adr_0100.dgc_status?filter=pv,md`, `<base>/adr_0200.dgc_status?filter=pv,md` | `…/GPFModelInfoController.java:30`. Produces the capability flags in the table above (`GPFRaDataConverter.decodeModelInfo`, `:7846-8260`). |
| `GPFSignOffController.set` (`DKSignInfo`) | op 3: `<base>/adr_0100.dgc_status` with `e_1002.e_3001.p_15` | Filter-sign reset. The UI sends `filter=1`, which becomes **`p_15="01"`** (`GPFRaDataConverter.encodeSignInfo`, `:8973-8979`; UI `wwapp/view/unitcontrol/ra/RaUnitCtrlBottomMenuFilterSignDialog.java:72-80`). |

---

### Room AC auxiliary features: open questions

- **Wire types:** whether the device returns `scdl_t.info.pv` as an object, `datas`/`this_year` as JSON number arrays, and patrol/price/target values as numbers or strings. The shapes above come from the parsing code and haven't been captured live.
- **Year energy unit:** kWh or 0.1 kWh.
- **Month history read:** whether a single read of `history.h_01.data` is usable, or only expand=ch works.
- **Month array alignment:** whether the last element of `history.h_01.data` is yesterday or today.
- **Setpoint bytes in schedule entries:** what the device accepts for temperature bytes 7–10 in auto mode. The UI sends relative `M000` and `L000`/`H000`; absolute values are unverified.
- **`e_3003.p_2D` semantics for Ra:** inferred from the VRV converter.
- **Firmware support:** whether any India firmware implements `patrol.*`, given that the app hard-disables it.
## Device-type identification

The app picks a `DeviceType` from a type code string, then chooses the protocol (`ProtocolType`) and the data converter from the pair `(protocol, device_type)`.

**Where the type code comes from**

| Source | Field | Cite |
|---|---|---|
| GPF cloud/local (DSIOT) | `dev_i.type` (mapped to legacy key `type`) | `dknetlib/gpf/data/GPFConvertValue.java:42`, `dknetlib/gpf/net/GPFRemoteSearchController.java:270` |
| GPF adapter hardware kind | `adp_i.kind` (legacy key `adp_kind`) to `DKAdapterType` | `GPFConvertValue.java:14`, `GPFRemoteSearchController.java:277` |
| Legacy `/common/basic_info` (local/UDP) | `type=`, plus `cdev=` when `type=GPF`, and `protocol=` | `p032e5/b.java:62-170` |
| Legacy cloud `/common/device_list_ex` | 4th `:`-separated field of each entry | `dknetlib/dk/net/http/d.java:149` |

**`DeviceType.toType` (type code string to device type)** (`dknetlib/core/data/DeviceType.java:18-52`)

| Code(s) | DeviceType | What it is | Legacy category (`http/d.java:192-220`) |
|---|---|---|---|
| `RA`, `PA`, `aircon` | RoomAirConditioner | Room AC (`PA` is a packaged AC, which is also routed to the VRV decoder) | `RA` |
| `NA`, `common_adp` | CommonAdapter | Generic adapter. GPF search treats it as RoomAirConditioner (`GPFRemoteSearchController.java:272`) | — |
| `1D`, `cleaner` | AirCleaner | Air purifier ("Cj") | `CJ` |
| `circulator` | Circulator | **cc**: Daikin circulator fan (`strings.xml` `cc_title`="Circulator") | `CC` |
| `dryer` | RoomDryer | **rd**: "Air dryer", a dehumidifier or clothes dryer (`rd_title`="Air dryer") | `Others` |
| `EQ`, `ecocute` | EcoCute | **eq**: Daikin **Eco-Cute** heat-pump water heater with bath autofill (JP product; strings `eq_*`) | `EQ` |
| `1C`, `all_heat_exchanger` | AllHeatExchanger | **vh**: **total heat exchanger** (ERV ventilation unit, "Ventilation unit" in `notification_turn_on_confirmation_msg_vh`) | `VH` |
| `GPF` | Gpf | Placeholder. The real type is in `cdev` (`p032e5/b.java:79-120`) | — |
| `Water Heater`, `Floor Heater` | WaterHeater / FloorHeater | ECHONET-only devices (protocol forced to `echonet`) (`p032e5/b.java:121-124`) | — |
| `UNKNOWN` / anything else | Unknown / Others | — | — |

**`ProtocolType.toType`** (`dknetlib/core/data/ProtocolType.java:13-29`): `daikin`/`RS232C` gives Daikin (legacy HTTP); `gpf`/`DGC` gives GPF (DSIOT); `echonet` gives Echonet.
- In basic_info, `type=GPF`, `protocol=RS232C` and `cdev` in {`RA`,`PA`} gives legacy Daikin. Every other `type=GPF` gives GPF (`p032e5/b.java:79-110`).
- `CommonAdapter` + `protocol=DGC` gives Daikin (`p032e5/b.java:130-131`).

**`DKAdapterType`** (`adp_kind` / `adp_i.kind`) (`dknetlib/dk/data/DKAdapterType.java:7-40`):

| Code | Adapter |
|---|---|
| `0` | GainSpan |
| `1` | STMicroWired |
| `2` | STMicroWireless |
| `3` | MarvellWireless |
| `4` | Generation4 |
| other | Others (unsupported) |

**Converter selection** (`C3/V.java:99-132`, switch maps in `E4/L.java:16-48`):

| DeviceType | Protocol Daikin (legacy HTTP) | Protocol GPF (DSIOT) |
|---|---|---|
| RoomAirConditioner | DKRaDataConverter | GPFRaDataConverter |
| AirCleaner | DKCjDataConverter | GPFCjDataConverter |
| Circulator (cc) | **DKCcDataConverter** | GPFRaDataConverter (fallback; no GPF cc support) |
| RoomDryer (rd) | **DKRdDataConverter** | GPFRaDataConverter (fallback; no GPF rd support) |
| EcoCute (eq) | DKRaDataConverter (fallback; no legacy eq support) | **GPFEqDataConverter** |
| AllHeatExchanger (vh) | DKRaDataConverter (fallback) | **GPFVhDataConverter** |

The result: **eq and vh are GPF/DSIOT-only, and cc and rd are legacy-HTTP-only.**
- A GPF `DKBasicInfo` request for eq is routed to `GPFEqModelInfoController`, and for vh to `GPFVhModelInfoController` (`E4/K.java:150-164`).
- The matching writes are at `E4/K.java:1054-1061`.

---

## Air purifier (Cj, `DeviceType.AirCleaner`)

### Identification

- **Device type:** `dev_i.type` holds the type (`dknetlib/gpf/data/GPFConvertValue.java:33`, key `TYPE("type","dev_i.type")`). `DeviceType.toType` maps `"1D"` or `"cleaner"` to `AirCleaner` (`dknetlib/core/data/DeviceType.java:37-39`).
  - The search controller then labels the device `"CJ"` (`dknetlib/gpf/net/GPFRemoteSearchController.java:270-271,374-376`).
  - For comparison, `"EQ"`/`"ecocute"` map to EcoCute and `"1C"` to AllHeatExchanger (VH). `"RA"`/`"PA"`/`"aircon"` and `"NA"` (common adapter) map to the room AC.
- **Converter selection:** for protocol GPF plus `AirCleaner`, the app uses `GPFCjDataConverter`; for the legacy Daikin protocol plus `AirCleaner`, it uses `DKCjDataConverter` (`C3/V.java:101-131`).
- **Internal DK-style map:** `GPFCjDataConverter` translates DSIOT properties into the legacy-style key/value map used by the UI (`pow`, `mode`, `airvol`, `humd`, ...), which `DKCjDataConverter` then decodes (`GPFCjDataConverter.java:448-450`). The legacy key names in the tables below are that DK-side name.
- **Product series** (`dknetlib/core/data/cj/DKNetCjProductSeries.java:9-14`): `__` normal, `K_` humidify, `B_` UV, `KB` UV+humidify, `Z_` "clear force". I found no caller in the decompiled code, so where the series code comes from is **[inferred]** to be the model name.
- **Model name:** `dgc_status.e_1002.e_A001.p_18`, hex-encoded ASCII (`production_model_name`, `GPFCjDataConverter.java:2825`).

### Resources and requests

All device resources live under the indoor object `adr_0100`. The controller's `getIndoor()` is the `adr_01xx` address (`dknetlib/gpf/net/GPFBaseController.java:836-837`). The base is `/dsiot/edges/<ri>` in the cloud and `/dsiot/edge` locally.

| Operation | Request (`to`) | Source |
|---|---|---|
| Read state + capabilities | `op:2` on each of `<base>.adp_i?filter=pv`, `.adp_d?filter=pv`, `.adp_r?filter=pv`, `.dev_i?filter=pv`, `<base>/adr_0100.dgc_status?filter=pv,md` | `gpf/net/request/GPFCjControlInfoController.java:39-48` |
| Write control | `op:3` `<base>/adr_0100.dgc_status` with a `pc` tree of the changed `p_xx` only | `GPFCjControlInfoController.java:139` |
| Air-quality history | `op:2` `<base>/adr_0100.history?filter=pv,md` | `gpf/net/request/GPFCjAirQualityController.java:25` |
| Schedule read | `<base>/adr_0100.scdl_t.info?filter=pv` and `.scdl_t.body?filter=pv` (each read together with `dgc_status?filter=pv,md`) | `gpf/net/request/GPFCjScheduleTimerController.java:56,80` |
| Schedule write | `op:3` `<base>/adr_0100.scdl_t.info` / `.scdl_t.body` | `GPFCjScheduleTimerController.java:293,423` |

Encoding follows the room AC: `pv` is little-endian hex, and every key below is prefixed `dgc_status.`. The key table is in `dknetlib/gpf/data/GPFCjConvertValue.java:11-80`.

### Control properties (`adr_0100.dgc_status`)

| What | Key | DK name | Encoding |
|---|---|---|---|
| Power | `e_1002.e_A002.p_01` | `pow` | `00` off, `01` on |
| Operation changeover ("acOpeMode") | `e_1002.e_3001.p_3F` | `acOpeMode` | `00` purify air, `01` dehumidify + purify ("APwD"), `02` humidify + purify ("APwH"). `md.mx` is a bitmask of supported values; `7` means all three and enables the v2 schedule format (`GPFCjDataConverter.java:3191-3199,733-735`). Labels are the `common_cj_turn_mode_*` strings. |
| Mode/course, purify | `e_1002.e_3007.p_01` | `mode` (+ `airvol`) | 2 bytes; see the mode table |
| Mode/course, dehumidify | `e_1002.e_3007.p_02` | as above | same enum |
| Mode/course, humidify | `e_1002.e_3007.p_03` | as above | same enum |
| Manual fan speed, purify / dehumidify / humidify | `e_1002.e_3007.p_04` / `p_05` / `p_06` | `airvol` | `00` quiet, `01` low, `02` standard, `03` high ("strong"), `04` turbo. Only used when the mode is `0100` (manual). |
| Humidity setpoint, dehumidify, per mode | `e_1002.e_3007.p_07`–`p_11` | `humd` | See the humidity table. One key per mode: `p_07` smart, `p_08` manual, `p_09` auto fan, `p_0A` econo, `p_0B` pollen, `p_0C` moist, `p_0D` circulator, `p_0E` laundry, `p_0F` night laundry, `p_10` water deodorize, `p_11` internal drying. |
| Humidity setpoint, humidify, per mode | `e_1002.e_3007.p_12`–`p_1C` | `humd` | Same order as above: `p_12` smart … `p_1C` internal drying |
| UV clean | `e_1002.e_3007.p_2A` | `uv_clean` | `00`/`01` |
| Humidifying-filter drying run | `e_1002.e_3007.p_29` | `filter_drying` | `00`/`01` (read only in practice) |
| Wind direction / swing present | `e_1002.e_3001.p_41` | none | If the key exists, `en_OpeOpt` gets bits 2 and 4 (`GPFCjDataConverter.java:2816`). Values not decoded. |

**Mode/course values** (`p_01`/`p_02`/`p_03`), from `GPFCjDataConverter.java:1904-1975,1977-2100`. The DK `mode`/`airvol` values are from `DKNetCjDriveModeType` and `DKNetCjFanSpeedType`; the UI labels are the `common_cj_course_*` strings.

| GPF value | Course | DK `mode` / `airvol` |
|---|---|---|
| `0000` | Smart ("Recommend") | 1 / 0 |
| `0100` | Manual fan (speed in `p_04`/`p_05`/`p_06`) | 0 / 1–5 |
| `0200` | Auto fan | 0 / 0 |
| `0300` | Econo | 2 |
| `0400` | Pollen | 3 |
| `0500` | Moist ("throat/skin") | 4 |
| `0600` | Circulator | 5 |
| `0700` | Laundry dry | 6 |
| `0800` | Night laundry dry | 7 |
| `0900` | Deodorize by water | 8 |
| `0A00` | Internal drying | 9 |

The `md.mx` of `p_01`/`p_02`/`p_03` is a bitmask of supported courses, where bit *n* means value `0n00`. The `md.mx` of `p_04`/`p_05`/`p_06` is a bitmask of supported fan speeds (bits 0–4). Source: `GPFCjDataConverter.java:2627-2684`.

**Humidity setpoint values** (`GPFCjDataConverter.java:1628-1660,1668-1900`):

| GPF | Meaning | DK `humd` |
|---|---|---|
| `00` | Off | 0 |
| `01` | Low ("moderate") | 1 |
| `02` | Standard | 2 |
| `03` | High | 3 |
| `04` | Continuous | 5 |
| none | Auto. The app reports this for courses `0000` Smart and `0500` Moist, whose humidity is fixed. | 4 |

**Writing a course.** Write `p_3F`, then the mode key for that changeover (`p_01`/`p_02`/`p_03`), then the matching fan-speed key if the mode is `0100`, then the humidity key for that changeover and course (`GPFCjDataConverter.java:870-1380`).
- On products that don't support `acOpeMode`, the app picks `p_3F` from the humidity setting: `humd=0` gives `00` with `p_01`; `humd>0` gives `02` with `p_03`.
- Example: humidify-purify, manual fan "standard", humidity "high". **[inferred]** by composing these rules.
  ```json
  {"pn":"dgc_status","pch":[{"pn":"e_1002","pch":[
    {"pn":"e_A002","pch":[{"pn":"p_01","pv":"01"}]},
    {"pn":"e_3001","pch":[{"pn":"p_3F","pv":"02"}]},
    {"pn":"e_3007","pch":[{"pn":"p_03","pv":"0100"},{"pn":"p_06","pv":"02"},{"pn":"p_13","pv":"03"}]}]}]}
  ```

### Sensors and status (read only)

| What | Key | DK name | Encoding |
|---|---|---|---|
| PM2.5 level | `e_1002.e_3007.p_1D` | `pm25` | Hex to integer level. The UI clamps it to 0–5 (`wwapp/view/unitcontrol/cj/CjUnitCtrlMainContentsFragment.java:361-375`); `-9` means not ready yet (legacy). |
| Dust level | `e_1002.e_3007.p_1E` | `dust` | Same as PM2.5 |
| Odor level | `e_1002.e_3007.p_1F` | `odor` | Same as PM2.5 |
| PM2.5 / dust / odor raw values | `e_1002.e_3007.p_26` / `p_27` / `p_28` | none | These keys are the source paths of the history series (`md.path`), and their presence sets `sup_sensor` bits 0x100, 0x200 and 0x400 (`GPFCjDataConverter.java:326-331,2800-2808`). What the raw values are is **[inferred]**. |
| Room temperature | `e_1002.e_A00B.p_06` | `htemp` | Signed int16, multiplied by the step taken from `e_A00B.p_01.md.st`, or 1 if `md` is absent (`GPFCjDataConverter.java:485-491,2467-2471`). **[inferred]** that this works out to ×0.5 or ×1. |
| Room humidity | `e_1002.e_A00B.p_02` | `hhum` | Hex to integer % |
| Deodorizing-filter "off" sign | `e_1002.e_3007.p_3E` | `filter` | Flag |
| Streamer maintenance sign | `e_1002.e_3001.p_40` | `strmr_cln` | Flag |
| Streamer maintenance method | `e_1002.e_A001.p_1C` | `streamer_type` | `01` gives `1`; anything else gives `0` |
| Water supply needed (humidifier tank empty) | `e_1002.e_3007.p_20` | `water_supply` | Flag |
| Dehumidify tank full | `e_1002.e_3007.p_21` | `water_full` | Flag. Notifications about it are shown only if `sup_sensor & 0x800`. |
| Dust filter replacement sign | `e_1002.e_3007.p_22` | `dust_filter_inf` / `dust_filter` | Flag. **Reset** by writing `p_22 = "00"` (`GPFCjDataConverter.java:840-846`). |
| Dust filter remaining life | `e_1002.e_3007.p_23` | `dust_filter_per` | % (hex to integer) |
| Dust filter remaining life | `e_1002.e_3007.p_24` | `dust_filter_mon` | Months (hex to integer) |
| Error code | `e_1002.e_A004.p_09` | `unit_err` | The first 2 bytes are ASCII (for example `"U4"`). The app re-encodes this as a legacy numeric code (`GPFCjDataConverter.java:1481-1626`). |
| Schedule supported | `adp_i.func.en_scdltmr` | `en_scdltmr` | `"1"` means supported |

Capability flags derived by the app (`decodeModelInfo`, `GPFCjDataConverter.java:2596-2829`):
- `sup_sensor` bits: 1 PM2.5, 2 dust, 4 odor, 8 temperature, 0x10 humidity, 0x20 deodorizing filter, 0x40 streamer sign, 0x80 water supply, 0x100/0x200/0x400 the PM2.5/dust/odor history sources, 0x800 full-water sign. Each bit is set when the corresponding key is present.
- `en_OpeOpt` bits: 1 = the `acOpeMode` changeover exists (`p_3F.md.mx == 7`), 2|4 = `e_3001.p_41` present, 0x10 = UV (`p_2A`) present.

### Air-quality history (`adr_0100.history`)

Response children are `h_01`…`h_06`. Each has:
- `data`: a JSON array of little-endian hex values, where `null` means 0
- `lt`: the time of the latest sample, formatted `yyyy-MM-ddTHH:mm:ssZ` in UTC
- `md.type`, `md.point`, `md.cycle` and `md.path`

Sources: `GPFCjDataConverter.java:324-333,515-705`.

| id | Series | Points | Cycle | `md.path` |
|---|---|---|---|---|
| `h_01` | PM2.5, hourly | 48 | Hour (`10`) | `dgc_status.e_1002.e_3007.p_26` |
| `h_02` | PM2.5, daily | 14 | Day (`20`) | `p_26` |
| `h_03` | Dust, hourly | 48 | Hour | `p_27` |
| `h_04` | Dust, daily | 14 | Day | `p_27` |
| `h_05` | Odor, hourly | 48 | Hour | `p_28` |
| `h_06` | Odor, daily | 14 | Day | `p_28` |

- `md.type` enum: 0 instantaneous, 1 max, 2 min, 3 average, 4 difference. All six series expect `4`.
- `md.cycle` enum: 1 = 15 min, 2 = 30 min, 10 = hour, 20 = day, 30 = month.
- The app splits the hourly series into today and yesterday (24 values each). It shows the last 14 daily values as two weeks.

### Schedule timer (`adr_0100.scdl_t`)

`scdl_t.info` is a JSON string:
- `en_scdltimer`: 0 or 1
- `active_no`: which of the 3 programs is active
- `per_day`: always written as 6
- `name`, `name2`, `name3`: the program names
- `format`

Sources: `GPFCjDataConverter.java:714-774`, `GPFCjScheduleTimerController.java:320-414`.

`scdl_t.body` has keys `mo`, `tu`, `we`, `th`, `fr`, `sa` and `su`. Each key holds a JSON array of entry strings, which the app builds at `GPFCjDataConverter.java:2872-3182`. Entry format **[inferred]** from the substring offsets:

| Offset | Meaning |
|---|---|
| 0 | Unknown **[inferred]**: an enable or slot flag, copied through unchanged |
| 1 | Power (`0` off, `1` on) |
| 2 | Course as one hex digit (`0`–`A`, the high byte of the course value; `-` when off) |
| 3 | Fan speed (`0`–`4`), or `-` |
| 4 | Humidity (`0`–`4`), or `-` |
| 5–8 | Time `HHMM` |
| 9 | `acOpeMode` digit (v2 format only; `-` in v1) |
| 10 | Trailing `-` |

### Legacy (DK) path

`DKCjDataConverter` (`dknetlib/dk/data/DKCjDataConverter.java`, 1329 lines) decodes the same DK key names from the older "Daikin" HTTP protocol. It is used when the node's protocol is `Daikin` (`C3/V.java:104-111`).
- The legacy parameter names are the DK-side names in the tables above: `pow`, `mode`, `airvol`, `humd`, `uv_clean`, `pm25`, `dust`, `odor`, `htemp`, `hhum`. `acOpeMode` is **[inferred]**. Values are passed through unchanged apart from `-` ↔ `-9`.
- The endpoints are `/cleaner/get_unit_info` and `/cleaner/set_control_info` (`E4/K.java:351`, `X4/b.java:38`); see the legacy-protocol section.

## VRV / packaged AC (`PA` edges over GPF)

### Identification: "VRV" means a PA edge, handled as a room AC

- **No separate device type.** `dev_i.type` (`GPFConvertValue.TYPE`, `dknetlib/gpf/data/GPFConvertValue.java:42`) is `"PA"` for these units. `DeviceType.toType("PA")` returns `RoomAirConditioner`, the same as `"RA"` (`dknetlib/core/data/DeviceType.java:28-31`).
- **Converter selection.** No converter is chosen for VRV directly. `GPFRaDataConverter` hands off to `GPFVRVDataConverter` only when the decoded `type` is `"PA"`:
  - control-info decode: `dknetlib/gpf/data/GPFRaDataConverter.java:667-668`
  - model-info decode: `dknetlib/gpf/data/GPFRaDataConverter.java:7877-7878`
  - control-info encode (smali `GPFRaDataConverter.smali` `encodeControlInfo`, near line 11401+35..55)
- **The encode check reads the outgoing request map.** The VRV UI puts `"type":"PA"` into every control write (`wwapp/view/unitcontrol/vrv/VRVUnitCtrlFragment.java:713`).
- **Other `"PA"` checks:**
  - Sensor decode uses `DKNode.getDevice()[0].getDeviceInfo().getGroup() == "PA"` (`dknetlib/gpf/data/GPFVRVDataConverter.java:686-705`, `GPFRaDataConverter.java:8453`).
  - The UI uses `DKNode.getGroupName() == "PA"` in many places (`wwapp/view/unitlist/CreateUnitElement.java:127,406`, `wwapp/view/schedule/*`).
- **Default icon.** A PA edge gets icon 14 instead of 0 (`dknetlib/gpf/net/GPFRemoteSearchController.java:319-329`).
- **Resources are the same as the room AC** (`/dsiot/edges/<ri>` or `/dsiot/edge`):
  - `adr_0100.dgc_status`: indoor unit
  - `adr_0200.dgc_status`: outdoor unit
  - `adr_0100.scdl_t.{info,body}`: schedule
  - `adr_0100.i_power.*` and `adr_0200.history.h_01.data`: energy

  There is no VRV-specific request controller. In practice it is the room-AC property map with the differences listed below.
- **HA takeaway.** If `dev_i.type == "PA"`, apply the VRV encodings below. Otherwise use the room-AC encodings.

### Key map (`adr_0100.dgc_status.` prefix unless noted)

Source: `GPFVRVConvertValue` (`dknetlib/gpf/data/GPFVRVConvertValue.java:10-121`), plus the encode and decode code cited per row.

| What | Key | Encoding (VRV / PA) | Ref |
|---|---|---|---|
| Power | `e_1002.e_A002.p_01` | `00` off, `01` on | `GPFVRVDataConverter.java:1417,1953` |
| Operation trigger | `e_1002.e_3003.p_2D` | Sent with every write: `00` when switching on, `01` when switching off, `02` when power is unchanged. Also `02` on ventilation-only writes. **[inferred]** "change source/trigger" flag | `:1956,825,1073` |
| Mode (write) | `e_1002.e_3001.p_01` | **1 byte**: `03` auto, `05` dry, `02` cool, `01` heat, `00` fan, `08` humidify. The room-AC map writes 2 bytes (`0300`…); VRV writes 1 byte. | `:1965-1999` |
| Mode (read) | same | After LE byte swap: `0000` fan, `0001` heat, `0002` cool, `0003` auto, `0005` dry, `0008` humidify. `0009` counts as cool and `000A` as heat, **[inferred]** meaning auto-changeover currently cooling or heating. | smali `GPFVRVDataConverter.smali` `convertGPFDataToDriveModeType`; `decodeControlInfo` near line 5740 |
| Setpoint, cool | `e_1002.e_3001.p_02` | **°C × 10**, unsigned LE, e.g. 26.0 → `0401`. **Not** × 2 as on the room AC. See the quirk note below. | encode `:2066-2073`; decode smali near line 6295 (`/10`) |
| Setpoint, heat | `e_1002.e_3001.p_03` | °C × 10, same as cool | `:2080-2089`; smali near line 6345 |
| Setpoint, dry (write) | `e_1002.e_3001.p_1D` | °C × 10 (app writes dry `stemp` here) | `:2050-2058` |
| Setpoint, dry (read) | `e_1002.e_3001.p_1E` | °C × 10 | smali near line 6185 |
| Setpoint, auto | `e_1002.e_3001.p_1D` | 1 byte, signed offset × 2. `M`=`00`, `H`=`02`, `L`=`FE`, `HH`=`04`, `LL`=`FC`, or `stemp_a`×2 | `:2011-2043` |
| Fan speed | `p_09` cool, `p_0A` heat, `p_26` auto, `p_28` fan, `p_2B` humidify (all `e_1002.e_3001`) | `0300`–`0700` = levels 1–5, `0A00` = auto, `0B00` = silent. Dry is always written as `0A00` to `p_27`. | `encodeFlate :861-899`, `:2113-2151`; `decodeFlate :448-476` |
| Vertical vane | `p_05` (cool **and auto**), `p_07` heat, `p_22` dry, `p_24` fan | 3 bytes. UI only offers `0F0000` = swing and `010000`–`050000` = positions 1–5. Codec also knows `000000` stop, `100000` auto, `130000` natural, `140000` circulating, `170000` "nice". | encode smali `encodeControlInfo` rel. lines 884-1016; `wwapp/view/unitcontrol/vrv/VRVUpDownPopupOptionMenuBottomSheet.java:~107`; `GPFVRVVerticalAirDirectionType.java:10-33` |
| Horizontal vane | `p_06` (cool **and auto**), `p_08` heat, `p_23` dry, `p_25` fan | Same 3-byte codes (UI: `0F0000`, `010000`–`050000`) | smali rel. 1047-1175; `VRVUpDownPopupOptionMenuBottomSheet.java:~216` |
| Vane capability | `p_05/07/20/22/24/29 .md.mx` | Bitmask: bit0 stop, bits1–14 positions P0–P13, bit15 swing, bit16 auto, bit17 reverse, bit18 insensitive, bit19 natural, bit20 circulating, bit23 nice | `GPFVRVVerticalAirDirectionType.java:40-117`, `GPFVRVDataConverter.java:1707-1718` |
| Humidity setpoint | `p_2E` auto, `p_30` dry, `p_0B` cool, `p_2C` heat, `p_32` humidify | Value is scaled by the matching `.md.st`. Companion mode keys are `p_2F`, `p_31`, `p_0C`, `p_2D`, `p_33`: `00` off, `01` absolute, `02` AUTO, `03` AUTO_H, `04` AUTO_L, `06` CONTINUE **[inferred pairing]** | `decodeHumidity :482-522`; `GPFVRVConvertValue.java:53-62` |
| Room temperature | `e_1002.e_A00B.p_06` | int16 LE. For PA it is **not** × 0.5: the raw value is passed through, then the DK layer multiplies by 10 and the list view divides by 1000. So the unit is °C × 100 **[inferred]** (the room AC uses × 0.5). | `GPFVRVDataConverter.java:703-705`; `dknetlib/dk/data/DKVRVDataConverter.java:1533`; `wwapp/view/unitlist/CreateUnitElement.java:406` |
| Room humidity | `e_1002.e_A00B.p_02` | % (1 byte) | `:710-711` |
| Outdoor temperature | `adr_0200` `e_1003.e_A00D.p_01` | int16 LE × 0.5 | `:716-717` |
| Compressor frequency | `e_1003.e_2006.p_04` | integer | `:723-724` |
| Momentary power | `e_1003.e_A005.p_01` | app shows `(raw*10+100)/100` (integer division) | `:728-729` |
| Filter sign | `e_1002.e_3001.p_15` | `01` = lit. Reset by writing `00`; the app writes `filter==1 ? 01 : 00`. Presence of the key means the feature is supported. | `:732-734,1050-1056,1705-1706` |
| Water internal cleaning | `e_1002.e_3003.p_52` | `01` = active. For model `e_1002.e_2016.p_01 == 01850020` it only counts when room temp ≥ 23 and humidity ≥ 40 | `:735-754` |
| Ventilation power | `e_1002.e_3001.p_36` | `00` off, `01` on (key present means supported) | `:1063-1128`; `DKNetVRVVentilationPowerType` |
| Ventilation speed | `e_1002.e_3001.p_1C` | `01` high, `02` auto | `DKNetVRVVentilationSpeedType` |
| Ventilation category | `e_1002.e_3001.p_45` | `00` supply, `01` exhaust, `02` auto | `:1131-1160`; `DKNetVRVVentilationCategory` |
| 24-hour ventilation | `e_1002.e_3003.p_39`, or `p_3E` if `p_39` is absent | `00` off, `01` on with turbo, `02` on without turbo | `:780-833`; `DKNetVRVVentilation24hourType` |
| Error code | `e_1002.e_3003.p_30` = `01` means an error is present. `p_31` first 2 bytes are ASCII (e.g. `"U4"`). `e_1002.e_A006.p_0D` = `01` adds a prefix. | App encodes letter×16 + digit as a number: A=16, C=32, E=48, F=80, H=64, J=96, L=112, P=128, U=144 | `:1440-1594` |
| Model / type / destination | `e_1002.e_A001.p_0D` model, `p_07` type (`01` becomes `C`, otherwise `N`), `p_0E` destination (`00` is `in`) | string / flag | `:1606-1670` |
| Mode capability | `e_1002.e_3001.p_01.md.mx` | bitmask of supported modes. Bit 8 (0x100) means humidify is supported. | `:1629-1635` |
| Auto / heat limits | `p_1F.md.mi/mx` (auto offset limits × 0.5), `p_03.md.mi` (minimum heat setpoint) | | `:1685-1698` |
| Schedule enabled | `adp_i.func.en_scdltmr` = `1` | Schedule lives at `adr_0100.scdl_t.info` / `.body.{su..sa}`, same as the room AC. In each entry string, character 6 is the mode: `0` fan, `1` heat, `2` cool, `3` auto, `5` dry, `8` humidify. | `:589-683,918-1048,1359` |

**Setpoint encoding quirk.**
- **Decoding** (`convertOriginalStemp`, `GPFVRVDataConverter.java:1259-1304`) recognises only the 2-byte values `0401`, `0E01`, `1801`, `2201`, `2C01`, `3601` and `4001` (26.0–32.0 °C in whole degrees). Anything else is read as its first byte only, which works up to 25.5 °C.
- **Encoding** (`convertStemp`, `:1306-1328`) is the inverse.
- The general form is therefore uint16 LE with 0.1 °C units **[inferred]**, but the app only round-trips values up to 25.5 °C and whole degrees from 26 to 32 °C. Check `p_02.md` (`st`/`mi`/`mx`) on a real unit.

### Enums defined for VRV (`dknetlib/core/data/vrvcontrol/`)
These are app-level ("DKNet") codes, not wire values.
- **`DKNetVRVDriveModeType`:** Auto 0, Cool 1, Heat 2, Fan 3, Dry 4, Humidity 5
- **`DKNetVRVFanSpeedType`:** 1–5, Auto 10, Quiet 11
- **`DKNetVRVVerticalAirFlowDirectionType`:** Level1–6, Swing 20, Natural 21, Circulating 22, Auto 23, Nice 24
- **`DKNetVRVHumidityType`:** Absolute 100, Auto_Low 109, Auto 110, Auto_High 111, Continuous 120
- **`DKNetVRVSpecialModeType`:** Econo 12, Streamer 13, and others
- **`DKNetVRVDemandModeType`:** declared but no GPF mapping was found

## Eq: Eco-Cute heat-pump water heater (GPF/DSIOT)

This is a Japan-market product and is unlikely to appear on an India account. It is listed here for completeness.

- **Read:** `GPFEqModelInfoController` issues op 2 reads (`dknetlib/gpf/net/request/GPFEqModelInfoController.java:37`) on:
  - `<base>.adp_i?filter=pv`
  - `.adp_d?filter=pv`
  - `.adp_r?filter=pv`
  - `.dev_i?filter=pv`
  - `<base>/adr_0100.dgc_status?filter=pv,md`

  If `adp_i.reg` is missing, the app sets it to `in` (`:58-68`).
- **Write:** op 3 (PUT) on `<base>/adr_0100.dgc_status` (`:113`).
- **Key properties:** all live under `dgc_status.e_1002.e_3005.*` unless noted.
  - **Wire format:** LE hex. The app byte-swaps with `convertEndian` and then applies the enum or number conversion.
  - **Enum values** below are written as **wire LE hex**. Two-byte enums are byte-swapped, so the app's `"0001"` is `0100` on the wire.
  - **Sources:** decoder `dknetlib/gpf/data/GPFEqDataConverter.java:83-372`; model `L4/c.java:427-980`; semantics `wwapp/viewmodel/eq/EqBaseViewModel.java`, `ControlEqViewModel.java`; enums `dknetlib/core/data/eq/*`.
  - **W** = writable. Only the keys in the encoder switch are sent: `GPFEqDataConverter.java:372-560`.

| Key | Meaning | Encoding |
|---|---|---|
| `p_01` | Supply type | `00` full auto, `01` semi auto, `02` supply only, `03` business (`SupplyType`) |
| `p_03` / `p_04` | Boiling test-run state / sub-state | int. `p_03==2 && p_04==2` means test run not complete (`EqBaseViewModel.java:566-568,887`) **[inferred]** |
| `p_02` | Unknown | int × 10 (`GPFEqDataConverter.java:94`) |
| `p_07` (W) | Tank boiling amount | `00` auto, `01` plenty, `02` less |
| `p_08` | Favourite boiling amount level | 2 bytes: `0000` off, `0100`…`0A00` = levels 1–10 |
| `p_09` (W) | "More boiling" (extra tank heating) | `00` stop, `01`–`05` boil-up 1–5, `06` full now, `07` full 12 h, `08` full day |
| `p_0A` | More-boiling permitted | `00`/`01` |
| `p_0B` | Currently boiling | `00`/`01` |
| `p_0E` (W) | Suspend boiling | `00`/`01` |
| `p_0F` | In night-time tariff zone | `00`/`01` |
| `p_10`/`p_11`, `p_12`/`p_13` | Daytime zone start h/m, end h/m | int (0 is shown as 24) **[inferred h/m split]** (`ControlEqViewModel.java:253-325`) |
| `p_14` (W) | Pause boiling (away) | `00`/`01` |
| `p_15`/`p_16`/`p_17` (W) | Return-home year / month / day | int (`EqBaseViewModel.java:56-65`) |
| `p_1D` (W) | Day-shift setting | `00` off, `01` once, `02` daily |
| `p_1E` / `p_1F` (W) | Day-shift start / end hour | int; `md.mi`/`md.mx` give the range |
| `p_20` | Day-shift permitted | `00`/`01` |
| `p_21` (W), `p_22` | External operation ("cooperation") flags | `00`/`01` (`ControlEqViewModel.java:465-469`) |
| `p_37` (W) | Bath auto-fill start/stop | `01` start, `00` stop |
| `p_38` | Auto-fill state | `00` stop, `01` filling, `02` keep-warm wait, `03` keep-warm, `04` keep-warm supply |
| `p_39` (W) | Bath function command | `00` stop, `01` reheat, `02` pipe cleaning, `03` add water, `04` add hot water, `05` add high-temp water, `06` hot bath, `07` bubble bath |
| `p_3A` | Bath function state | 2 bytes: `0000` other, `0100` filling, `0200` reheating, … `0800` bubble bathing (`FunctionState`) |
| `p_3B` / `p_3C` | Bath enabled / reheat enabled | `00`/`01` |
| `p_3D` | Filling completed | `00`/`01` |
| `p_3E` | Bath temperature | int °C |
| `p_3F` (W), `p_40` (W), `p_41` (W) | Bath schedule on, hour, minute | `p_3F` is `00`/`01`. `p_40` is an int. `p_41` is the minute ÷ 10 on the wire, decoded ×10 (`GPFEqDataConverter.java:258`, encoder `:520-526`) |
| `p_44` | Hot-water supply temperature | int × `md.st` (default step 1) |
| `p_45` / `p_46` | Water setting / high-temperature setting | `00`/`01` |
| `p_49` | Remaining hot water level | `00`–`05` |
| `p_4A` | Remaining hot water | litres (UI buckets <50 / 50 / 100 / 150 / ≥200 L; `EqBaseViewModel.java:726-744`) |
| `p_4B` | Supply-available time | minutes (≤5 is shown as "a few minutes") |
| `p_4C` | Faucet-left-open notification on | `00`/`01` |
| `p_4D` (W) | Faucet-left-open judgement time | int × `md.st` (default 10), with `mi`/`mx` |
| `p_4E` | Not used for a long time | `00`/`01` |
| `p_4F`–`p_66`, `p_67`–`p_7E` | Usage history, 24 hourly values × 2 series | int (`dknetlib/a.java:14-17`; `wwapp/view/unitcontrol/eq/EqUsageHistoryFragment.java:404`) **[inferred today / yesterday]** |
| `p_86`…`p_7F` (reverse order) | Usage history, 8 daily values | int (`a.java:20`) |
| `p_87`–`p_92`, `p_93`–`p_9E` | Usage history, 12 monthly values × 2 series | int (`a.java:23-26`) **[inferred this year / last year]** |
| `p_B2` (W) | Weather-forecast linkage on | `00`/`01` |
| `p_B4` | Weather-code date | ASCII bytes |
| `p_C1` | Day-shift not-performed notice | `00` none, `01` bad weather, `02` communication failure |
| `p_C2` (W) | Day-shift weather group | `00` sunny only, `01` sunny or cloudy |
| `p_C3` / `p_C4` | Weather-alert extra boiling: setting / active | `00`/`01` |
| `e_1002.e_A013.p_01` (W) | Unit clock | ASCII `yyyy-MM-ddTHH:mm:ss` (`EqBaseViewModel.java:639-655`) |
| `e_1002.e_A004.p_02` | Error code | via `convertErrorCode` |

Eq also uses the weather host (`DKWeatherLinkageSetting`, `GPFEqDataConverter.java:586-592`) for day-shift weather linkage.

---

## Vh: total heat exchanger / ventilation unit (GPF/DSIOT)

- **Read:** `GPFVhModelInfoController` (`dknetlib/gpf/net/request/GPFVhModelInfoController.java:36`) reads the same adapter nodes as Eq, **plus both** `<base>/adr_0100.dgc_status?filter=pv,md` and `<base>/adr_0200.dgc_status?filter=pv,md`.
- **Write:** op 3 on `<base>/adr_0100.dgc_status` (`:112`).
- **Sources:** decoder `dknetlib/gpf/data/GPFVhDataConverter.java:42-97`; encoder `:99-118`; model `U4/b.java:83-198`; UI `wwapp/viewmodel/vh/VhBaseViewModel.java`; enums `dknetlib/core/data/vh/*`.

| Key (`dgc_status.`) | Meaning | Encoding (wire) |
|---|---|---|
| `e_1002.e_A002.p_01` (W) | Power | `00` off, `01` on |
| `e_1002.e_3001.p_3D` (W) | Mode | `00` eco-auto, `01` auto, `02` ventilation |
| `e_1002.e_3001.p_3D.md.mx` | Supported modes | Bitmask: 1 = eco-auto, 2 = auto, 4 = ventilation |
| `e_1002.e_3001.p_1C` (W) | Ventilation (fan) speed | 2 bytes: `0000` low, `0100` high, `0700` middle |
| `e_1002.e_3001.p_1C.md.mx` | Supported speeds | Bitmask: 1 = low, 2 = high, 128 = middle |
| `e_1002.e_3001.p_3E` (W) | Dehumidify ("Dry settings") level | `00` low, `01` middle, `02` high. The UI shows it as unknown in ventilation or eco-auto mode (`ControlVhViewModel.java:133-151`) |
| `e_1002.e_3001.p_3E.md.mx` | Supported dry levels | Bitmask: 1 = low, 2 = middle, 4 = high |
| `e_1002.e_3001.p_15` | Filter sign | `00`/`01` |
| `e_1002.e_3003.p_5E` | Internal cleaning in progress | `00`/`01` (shown as "internal cleaning" status) |
| `e_1002.e_3003.p_30` | Error flag | `01` = error **[inferred; decompiled branch is garbled, `U4/b.java:87-101`]** |
| `e_1002.e_A004.p_09` | Error code | via `convertErrorCode` |
| `e_1002.e_A001.p_08` | Read and endian-swapped but not used | — |
| `e_1003.e_A005.p_01` | Power consumption | LE int × 10, clamped for display to 10–1000 (`GPFVhDataConverter.java:94`; `ControlVhViewModel.java:84-129`). Unit likely W **[inferred]**. Read from the `adr_0200` object **[inferred from e_1003 = outdoor/secondary]** |

---

## Rd: air dryer (legacy Daikin HTTP only, read-only)

The UI's unit list issues only `DKBasicInfo` + `DKRdUnitInfo` (`dknetlib/DKApiParallel$getUnitListRD$1$totalTime$1$deferredList$1.java:42`). The app has no set endpoint for rd (`strings.xml` `rd_not_supported`="The unit cannot be operated from smartphone.").

- **Endpoint:** `GET /dryer/get_unit_info` (`E4/K.java:674`). The response is legacy `ret=OK,k=v,...` text.
- **Decoding:** `DKRdDataConverter.java:35-51` multiplies `htemp` by 10. The model is `S4/c.java:47-103`, and the UI is `wwapp/view/unitcontrol/rd/RdMainContentsFragment.java:439-530`.

| Key | Meaning | Encoding |
|---|---|---|
| `pow` | Running | `1` on, other values off |
| `mode` | Operation mode | `0` Turbo, `1` Powerful(auto), `2` Auto, `3` "Low" (enum `ModularAuto`), `4` Quiet (not shown in the UI) |
| `care` | Maintenance ("care") operation | `1` = maintenance running (overrides the mode label) |
| `htemp` | Room temperature | decimal °C (app ×10, then UI ÷10) |
| `hhum` | Room humidity | % |
| `offtimer_en` | Off-timer enabled | `1`/`0` |
| `offtimer_remain` | Off-timer remaining | minutes (UI shows days if >1440, otherwise hours) |
| `unit_err` | Unit error code | int |

---

## Cc: circulator fan (legacy Daikin HTTP only)

- **Unit list:** `DKBasicInfo`, `DKModelInfo`, `DKUnitInfo` and `DKCcLinkageInfo` (`dknetlib/e.java:40-180`; `DKApiParallel$getUnitListCC$1$totalTime$1$deferredList$1-4`).
- **Converter:** `dknetlib/dk/data/DKCcDataConverter.java`.

| Endpoint | Purpose | Cite |
|---|---|---|
| `GET /circulator/get_model_info` | Capabilities, e.g. `en_auto` (auto-fan supported), `en_asst` (auto-assist supported), `s_frate_step` | `E4/K.java:337`; `wwapp/view/unitcontrol/cc/CcMainContentsFragment.java:222,274` **[keys inferred from UI use]** |
| `GET /circulator/get_unit_info` | State (table below) | `E4/K.java:360` |
| `/circulator/set_control_info?pow=&f_rate=&f_dir=` (query string, built by `dk/net/http/a.c`) | Control | `p013b5/a.java:39`; encoder `DKCcDataConverter.java:277-293` |
| `/circulator/get_device_setting` / `set_device_setting` | Airflow auto-assist: `asst_mode` (`1` cool assist, `2` heat assist), `c_asst` / `h_asst` (assist temperatures, °C) | `E4/K.java:647`; `p013b5/b.java:43`; `G4/b.java:27-60` |
| `/circulator/get_linkage_info` / `set_linkage_info` | AC linkage: `AcLink` (`1` on), `LinkMac` (MAC of the linked AC) | `E4/K.java:654`; `p013b5/c.java:35`; `G4/e.java:22-34` |
| `/circulator/get_linkage_notify` / `clear_linkage_notify` | `auto_off_flg` (`1`), `auto_off_tm` | `E4/K.java:661`; `p013b5/d.java:43`; `G4/f.java:22-27` |
| `/circulator/get_scdltimer_info`, `get_scdltimer_body`, `set_scdltimer_info`, `set_scdltimer_body` | Weekly schedule (below) | `E4/K.java:424,453`; `p013b5/g.java:39-50` |

**Unit/control info keys** (`G4/h.java:40-94`; wire conversions `DKCcDataConverter.java:88-117,252-276`):

| Key | Meaning | Wire encoding |
|---|---|---|
| `pow` | Power | `1` / `0` |
| `f_rate` | Fan speed | `1`–`15` = levels, `R` = rhythm (app code 101), `A` = auto (app code 102) |
| `f_dir` | Air-flow direction / oscillation | `0` off, `1`–`5` = levels, `S` = swing (app code 11) |
| `htemp` | Temperature | decimal °C (app ×10) |
| `hhum` | Humidity | % |
| `opt_dev` | Option device present | `1`/`0` |
| `err`, `unit_err` | Adapter / unit error | code |
| `linkcomm_err` | Linkage communication error | `1` = error |

**Schedule body** (`DKCcDataConverter.java:181-240,295-337`):
- `format=v1`, `target=1`.
- For each day `su,mo,tu,we,th,fr,sa` (`dknetlib/b.java:19`):
  - `<day>c=<count>`
  - `<day>1..N=<E><P><HHMM>`, where `E` = entry enabled `0/1`, `P` = power on/off `0/1`, and `HHMM` is 4 digits.
- `set_scdltimer_info` sends `active_no` (default `1`) and `en_scdltimer`.

The UI also offers an installation-type picker (`strings.xml` `cc_put_type_01..07`: assist fan wall / cool-heat assist / air curtain / circulator wall / ceiling / floor horizontal / floor vertical). Its parameter key was not located **[unknown]**.

## Legacy "Daikin" HTTP protocol (pre-DSIOT adapters)

This is the older `ret=OK,k=v,...` text protocol (the one `pydaikin` speaks), implemented in `dknetlib/dk/net/http/*` and dispatched from `E4/K.java`. In the app it's `ProtocolType.Daikin`; DSIOT is `ProtocolType.GPF` (`dknetlib/core/data/ProtocolType.java:13-29`).

### When the app uses legacy and when it uses GPF

The choice is made **per node**. Each request looks at the node's `protocol`: `Daikin` goes to the legacy `/aircon/*` handlers and `GPF` goes to the DSIOT controllers (`E4/K.java:135-138`, legacy branch from `:296`). The converter is chosen the same way (`C3/V.java:100-129`). Nothing falls back from one protocol to the other at runtime.

How a node's protocol is set:

| Discovery path | Protocol assigned | Source |
|---|---|---|
| Cloud, `GET /common/device_list_ex` (legacy list) | always `Daikin`. Only the RA, CJ, CC and RD types are instantiated; EQ and VH entries are dropped | `dknetlib/dk/net/http/d.java:136-209` |
| Cloud, `POST /dsiot/multireq` edge list | always `GPF`. Type comes from the edge's `type` field, and `common_adp`/`NA` becomes RA | `dknetlib/gpf/net/GPFRemoteSearchController.java:270-303` |
| Local UDP `basic_info` reply, `type` ∈ {`aircon`/`RA`/`PA`, `cleaner`/`1D`, `circulator`, `dryer`, `common_adp`/`NA`} | the reply's `protocol` field (`daikin`/`RS232C` → Daikin; `gpf`/`DGC` → GPF). If the field is missing, **Daikin** | `p032e5/b.java:69-78,130-139` |
| Local, `type=GPF` | **Daikin** if `protocol=RS232C` **and** `cdev` ∈ {`RA`,`PA`}; otherwise **GPF**. The real device type then comes from `cdev` | `p032e5/b.java:79-110` |
| Local, `type=UNKNOWN` | the device type comes from `cdev`; the protocol field is used as-is | `p032e5/b.java:111-120` |
| Local, `type` = `ecocute`/`EQ` or `all_heat_exchanger`/`1C` | the `protocol` field (these are always instantiated as `GPFDevice`) | `p032e5/b.java:446-451` |

Which device class each type gets:

| Device type | Daikin protocol | GPF protocol |
|---|---|---|
| RA | `DKRaDevice` | `GPFDevice` |
| CJ | `DKCjDevice` | `GPFDevice` |
| CC and RD | always `DKRaDevice` (legacy only) | n/a |
| EQ and VH | n/a | GPF only |

Source: `p032e5/b.java:445-478`.

On the cloud, both searches run **in parallel** on every refresh: `device_list_ex` and the GPF edge list (`dknetlib/dk/data/DKRemoteDeviceManager.java:284-350`). So a legacy adapter that is registered to the account appears as a legacy cloud node. In demo mode the app calls `/common/device_list` with `id`/`spw` instead.

Adapter hardware (`adp_kind` → `DKAdapterType`, `dknetlib/dk/data/DKAdapterType.java`):

| `adp_kind` | Hardware |
|---|---|
| `0` | GainSpan |
| `1` | STMicro wired |
| `2` | STMicro wireless |
| `3` | Marvell wireless |
| `4` | Generation4 |
| anything else | Others |

- If `adp_kind` is missing, the app infers GainSpan when `ver` is at or below 1_2_2 (`p032e5/b.java:158-167`).
- Feature gates by firmware are in `dknetlib/dk/data/DKNode.java`: `OLD_INTERFACE_SUPPORT_VERSION=1_5_0`, `NEW_INTERFACE=2_2_6`, `NEW_SCHEDULE_TIMER=2_7_2`.
- For a Home Assistant integration: **use legacy only when a local `basic_info` reply has no `protocol`, or has `protocol=daikin`/`RS232C`, or when the cloud `device_list_ex` returns the unit. Use GPF for everything else.**

### Transport

All legacy requests are **HTTP GET**. Parameters go in the query string and there is no body (`androidx/emoji2/text/l.java:107-126`, `R/a.java:267-283`). The URL is built in `dknetlib/dk/net/http/a.java:38-162`, and the scheme is chosen in `dknetlib/dk/net/http/b.java:93-128`.

| Aspect | Local | Cloud |
|---|---|---|
| Base URL | `http://<ip>[:api_port]` | `https://prod.daikinacmanager.com`. HTTPS is used when the host is one of prod.daikinacmanager.com, sha2.daikinonlinecontroller.com, test2.daikindev.com or dspsph.com |
| Path | `/aircon/get_control_info` etc. | the **same** path, e.g. `https://prod.daikinacmanager.com/aircon/get_control_info` |
| Identifies the unit | host IP | query `port=<port>`, where `port` is field 0 of the unit's `device_list_ex` entry (`d.java:131`) |
| Auth | `lpw=<PIN>` as a **query parameter**, only when a lock PIN is set. No headers are sent (`R/a.java` calls `b.c(url, null)`) | header `Authorization: <id_token>`: the **raw Cognito id_token with no `Bearer ` prefix** (`a.java:73-79`), plus the literal query parameters `id=ID&spw=SPW` |
| Other headers | none | `Connection: close` |
| Timeout and retries | 5 s; up to 6 tries | 5 s; 2 tries. HTTP 500 → `ret=INTERNAL_SERVER_ERROR`, 503 → `ret=SERVER_MAINTENANCE` |

- There is **no** `X-Daikin-uuid` or key header anywhere in this build. The uuid/key scheme used by some other Daikin apps (e.g. BRP072C) is absent. Local legacy access is unauthenticated apart from the optional `lpw`.
- `id`, `apw` and `port` from the local `basic_info` are stored but are **not** sent to local nodes (`a.java:66-72`: non-`lpw` auth keys are added only for remote nodes and servers).
- On the `set_*` endpoints, the query string omits any key that matches `^(dt|dh|dfr|dfd|ndfd)[1-7h](_a)?$` or `^b_(mode|stemp|shum|f_rate|f_dir|stemp_a|f_dir_ud|f_dir_lr)$` (`a.java:30-33,135-146`). These are per-mode memory values that `get_control_info` returns but that should not be echoed back. `terminalid`, when present, is placed first.
- Response: `ret=OK,key=val,...`. Values are percent-encoded where needed (e.g. `name`). `ret` ∈ {`OK`, `PARAM NG`, `ADV_NG`, `INTERNAL_SERVER_ERROR`, `SERVER_MAINTENANCE`, `UNAUTHORIZED`, …} (`dknetlib/core/data/ResultType`).

### Cloud legacy device list

```
GET https://prod.daikinacmanager.com/common/device_list_ex?id=ID&spw=SPW&id=&spw=&device=A&device_token=<fcm token>
Authorization: <id_token>
```
Source: `dknetlib/dk/data/DKRemoteDeviceManager.java:296-333`.

- The response is `ret=OK,device=<entry>/<entry>/...`. Each entry is a list of fields separated by `:`.
- Field positions are read in `dknetlib/dk/net/http/d.java:112-212`:

| Field | Meaning |
|---|---|
| 0 | `port`, the unit handle used in later calls |
| 3 | device type code (see the device-type table: `aircon`/`RA`, `cleaner`, `circulator`, `dryer`, …) |
| 4 | firmware `ver` (e.g. `1_14_68`) |
| 6 | `err` code |
| 8 | name (URL-encoded) |
| 9 | icon |
| 11 | region |
| 14 | adapter LED (`1` = on) |
| 15 | `adp_kind` |
| 16 | FW auto-update (`1` = on) |
| 21 | option device type |
| 22 | option device version |
| 25 | installation form (`instform`) |
| 26 | connected, `1` = online (default 1) |

### Local `basic_info` / UDP reply keys

- The reply comes from `DAIKIN_UDP/common/basic_info` (UDP, port 30050) or from `GET /common/basic_info`.
- It's plain `k=v,` text and uses the same keys either way. They're parsed in `p032e5/b.java:62-325`.

| Key | Meaning |
|---|---|
| `type` | device type (see the DeviceType table) |
| `protocol` | `daikin`, `RS232C`, `gpf`, `DGC` or `echonet` (drives the protocol choice) |
| `cdev` | connected-device type code, used when `type` is `GPF` or `UNKNOWN` |
| `ip`, `api_port` | address |
| `ver` | adapter firmware, `a_b_c` |
| `reg` | region (defaults to `in`) |
| `adp_kind` | hardware generation |
| `adp_mode` | `run`, `ap` or `ap_run` |
| `id`, `pw` (→`apw`), `port` | cloud-registration identity (not needed locally) |
| `lpw_flag` | `1` means a lock PIN is set, so `lpw` must be sent |
| `led`, `auto_update`, `en_hol` | flags, `0`/`1` |
| `disp_ssid`, `ssid` | SSID display flag and SSID |
| `method` | `polling` means "out-of-home" (cloud) access is enabled |
| `edid` | DSIOT edge ID when known |
| `option`, `opt_sv` | option device |
| `name` | URL-encoded display name |
| `icon`, `instform` | UI hints |
| `err` / `comm_err` | error code |

### Endpoints

Paths are dispatched in `E4/K.java:296-680`, with the setters in `Y4/*` (aircon), `X4/*` (cleaner), `p013b5/*` (circulator) and `p020c5/*` (common). Response keys are listed where they matter for Home Assistant.

| Path | Used for | Key params / response keys |
|---|---|---|
| `/common/basic_info` | adapter info | see above |
| `/common/get_remote_method`, `set_remote_method` | cloud polling on/off | `method=polling` |
| `/common/get_datetime`, `get_holiday`/`set_holiday`, `get_notify`/`set_notify`, `get_group`/`set_group`, `get_network_setting`/`set_network_setting`, `get_wifi_setting`/`set_wifi_setting`, `get_wifi_scan_result`, `reboot`, `port_assign`, `erase_device`, `get_apw`, `get_spw`, `get_progsum` | adapter administration | none of these are needed for Home Assistant |
| `/aircon/get_control_info` | RA state | `pow` (0/1), `mode`, `stemp`, `shum`, `f_rate`, `f_dir`, `f_dir_ud`, `f_dir_lr`, `adv` (`/`-separated active special modes), plus per-mode memories `dt1..7`/`dh1..7`/`dfr1..7`/`dfd*`/`ndfd*` and `b_*` |
| `/aircon/set_control_info` | RA write | `pow`, `mode`, `stemp`, `shum`, `f_rate`, `f_dir_ud`, `f_dir_lr` (the app sends all current non-memory keys; `Y4/a.java:42`) |
| `/aircon/get_sensor_info` | RA sensors | `htemp` (room °C), `hhum` (%, `-` if none), `otemp` (outdoor °C), and others |
| `/aircon/get_model_info` | RA capabilities | e.g. `en_*` feature flags and `s_*` ranges (parsed by `Y4/d`) |
| `/aircon/set_special_mode` | powerful, econo, streamer | `spmode_kind` = `1` powerful, `2` econo, `3` streamer (`DKRaDataConverter.java:463-476`); enable flag `set_spmode=0/1` **[inferred]** |
| `/aircon/get_timer`/`set_timer`, `get_program`/`set_program`, `get_scdltimer[_info|_body]`/`set_scdltimer[_info|_body]` | on/off timers and weekly schedules | the schedule body is fixed-width strings, e.g. `<en><pow><mode><temp4><HHMM><f_rate><f_dir><hum3><spmode><sppow>...` (`DKRaDataConverter.java:1488-1510`) |
| `/aircon/get_week_power[_ex]`, `get_year_power[_ex]`, `get_day_power_ex`, `get_price`/`set_price`, `get_target`/`set_target`, `get_demand_control`/`set_demand_control` | energy | `datas` arrays separated by `/`; `curr_day_cool`/`heat`, `prev_year_cool`/`heat`, etc. |
| `/aircon/get_patrol_*`, `set_patrol_setting`, `clear_patrol_notify` | "patrol" (temperature-guard) monitoring | `patrol_mode`, `patrol_lo_stemp` and `patrol_hi_stemp` (all ×10) |
| `/cleaner/get_unit_info` | CJ state | response `ret=OK,ctrl_info=<%-encoded k=v,..>,unit_status=<…>,sensor_info=<…>`. Each part is percent-decoded and parsed again as `k=v` (`DKCjDataConverter.java:454-480`) |
| `/cleaner/set_control_info` | CJ write | `pow`, `mode` (0–9), `airvol` (fan, 0–5), `humd` (humidify, 0–5), `uv_clean` (`0`/`1`). Values are the same enum numbers as the GPF `DKNet` model; `-` means n/a (`DKCjDataConverter.java:814-1110`) |
| `/cleaner/get_model_info`, `get_day_snsr_count`, `get_week_snsr_count`, `get_linkage_info`/`set_linkage_info`, `get_scdltimer_*`/`set_scdltimer_*` | CJ capabilities, dust/odor/PM2.5 history (`week_pm25`, `week_dust`, `week_odor`), linkage with an AC, and schedules | sensor keys in `sensor_info`: `htemp` (°C), `hhum` (%), `pm25`, `dust`, `odor` (levels; `-` means none) |
| `/circulator/get_unit_info`, `set_control_info`, `get_model_info`, `get_device_setting`/`set_device_setting`, `get_linkage_info`/`set_linkage_info`, `get_linkage_notify`/`clear_linkage_notify`, `get_scdltimer_*` | CC (circulator fan), legacy only | see the CC section |
| `/dryer/get_unit_info` | RD (dehumidifier), legacy only, read-only in the app | see the RD section |

### RA legacy value encodings (`dknetlib/dk/data/DKRaDataConverter.java`)

| Key | Wire value | App value / meaning | Source |
|---|---|---|---|
| `mode` | `0`, `1`, `7` = auto; `2` = dry; `3` = cool; `4` = heat; `6` = fan; `HUM`/`H` = humidify; `LND` = laundry-dry | `DKNetRaDriveModeType`: Auto 0, Cool 1, Heat 2, Fan 3, Dry 4, Humidity 5, Laundry 6 | `:353-420`, `:311-331` |
| `stemp` | °C as a decimal string (`25.0`). In dry/auto modes it can be a relative code: `LL`, `L`, `M`, `H`, `HH` = −2, −1, 0, +1, +2 steps. `--` means none | ×10 internally | `:545-600` |
| `shum` | `%`, `AUTO`, `AUTO_L`, `AUTO_H`, `CONTINUE`, or `-`/`--` for none | 110, 109, 111, 120, −9 | `:289-305` |
| `f_rate` | `A` = auto, `B` = quiet, `3`–`7` = levels 1–5 | `DKNetRaFanSpeedType` 10, 11, 1–5 | `:157-199` |
| `f_dir_ud` | `S` swing, `A` auto, `N` natural, `C` circulating, `I` "nice"; otherwise a numeric position `0`–`6` | 20, 23, 21, 22, 24 | `:1690-1732` |
| `f_dir_lr` | `S` swing, `A` auto, or a numeric position | 10, 11 | `:1672-1686` |
| `f_dir` (older) | `0` off, `1` vertical swing, `2` horizontal, `3` both | `DKNetRaAirFlowDirectionType` | `core/data/racontrol/a.java:125-140` |
| `spmode_kind` | `1` powerful, `2` econo, `3` streamer | `DKNetRaSpecialModeType` 2, 12, 13 | `:463-476` |
| `htemp`/`otemp` | °C decimal; `-` means none | ×10 | `:1540-1560` |
| `adv` | active special modes, `/`-separated, e.g. `2/13` | `DKNetRaSpecialModeType` codes | `core/data/racontrol/a.java:153-173` |
## Other cloud endpoints

This section covers the non-authentication cloud calls. Login, OTP, tokens, profile and RSA are out of scope here (see [Authentication](#authentication)). `/dsiot/multireq` property reads and writes and the edge list are documented separately. Citations are relative to `jadx/sources/`, with `dknetlib/` meaning `jp/co/daikin/dknetlib/` and `wwapp/` meaning `jp/co/daikin/wwapp/`.

### Transport conventions (apply to every call below)

| Item | Behaviour | Ref |
|---|---|---|
| Main host | `https://prod.daikinacmanager.com` (`DKServer` addr). Headers: `Content-Type: application/json`, `Authorization: Bearer <id_token>` | `dknetlib/gpf/net/GPFHttpController.java:54` |
| Account host | `https://prod-clubdaikin.daikinacmanager.com` (`getAuth`/`postAuth`). Header: `Authorization: Bearer <cd_accessToken>` | `GPFHttpController.java:75,447` |
| Weather host | `https://app-weather.daikinsmartdb.jp` (`getRegion`/`setRegion`). Header: `Bearer <cd_accessToken>` | `GPFHttpController.java:456,535,562` |
| Verb helpers | `get`=GET, `config`=POST, `set`/`multiSet`=PUT, `delete`=DELETE, `multiGet`=POST. With no URL given, `config`/`multiGet`/`multiSet` go to `/dsiot/multireq` | `dknetlib/gpf/net/GPFBaseController.java:207,466-487,520-790` |
| GET body | The helpers take a body string, but it is never sent on GET (`doOutput = method != "GET"`) | `GPFHttpController.java:354` |
| Timeout | 10 s (40 s for adapter `user_info`) | `GPFHttpController.java:476` |
| HTTP errors | On 401, 404, 500 or 503 the body is replaced with `{"responses":[{"rsc":<status>}]}`. Other non-200 responses pass the error body through. An I/O failure produces `{"responses":[{"rsc":6000}]}` or `rsc:<status>` | `GPFHttpController.java:392-398` |
| Flat response parse | `parseResponse` → `getMapForResponse`: with no `responses` key, each top-level key becomes a string map entry and `rsc` defaults to `"2000"` when absent. Nested objects and arrays are kept as JSON text (`body`, `message_info` …). Primitives go through Gson `Object`, so a JSON number becomes e.g. `"200.0"` **[inferred]**; the app compares `result_cd` against the string `"200"` | `GPFBaseController.java:905-1080`, `dknetlib/gpf/net/request/GenericMapSerializer.java` |
| `rsc` → result | `2000`–`2004` OK; `4000` PARAM_NG; `401`/`4001` ACCOUNT_NG (remote); `404`/`4004` NOT_FOUND; `4003` FORBIDDEN; `4009` LOCK_NG; `4105` ACCOUNT_MIGRATED; `4109` NOT_EXISTS; `4110` REACH_MAX; `4234` AUTO_UPDATING; `500` ISE; `503` SERVER_MAINTENANCE; `5000` INTERNAL_NG; `5107` DEVICE_NOT_CONNECTED; `6010` SERIAL_IF_FAILURE; anything else UNKNOWN | `dknetlib/core/data/ResultType.java:108` |
| `/api/*`-style replies | These are checked on `result_cd == "200"`, and the payload is in `body` (JSON text) or `message`. The transport `rsc` is usually absent, which yields OK | e.g. `wwapp/view/unitcontrol/ra/L.java:104` |
| Request identifiers | `uuid` is a random per-install UUID in prefs `uuid` (`E4/C0030e.java:159`). `resource_id`/`port` is the cloud edge id of the unit (`dknetlib/gpf/net/GPFRemoteSearchController.java:293-295`). `edgeId` is taken from `GPFDevice.objects[0].edgeId` (`GPFBaseController.java:818-824`) | |
| Dispatcher | `RequestType` → controller mapping: GET path `E4/K.java:137-292`, SET path `E4/K.java:709-1045`, numbering in `E4/H.java` | |

### Buildings, zones, floors and edge metadata (`GPFMetaDataController`)

All calls go to the main host with `Bearer id_token`. The controller entry points are in `dknetlib/i.java` at lines 99, 125, 151, 345, 369, 528, 570 and 585.

| Method + path | Body | Response (as parsed) | App feature | Ref |
|---|---|---|---|---|
| `GET /dkapp/app_config_all` | – | `{rsc, responses:[{"/dkapp/edge_meta":{rsc, edge_meta:{dkapi:{<ref_id>:[EdgeMetaInfo]}, dsapi:{…}}}}, {"/dsiot/buildings":{rsc, pc:[Building]}}]}` | Loads buildings, zones and edge metadata on unit-list refresh (`wwapp/view/unitlist/UnitSearch.java`) | `dknetlib/gpf/ctrl/GPFMetaDataController.java:750-768, 452-521` |
| `GET /dkapp/edge_meta/{dsapi\|dkapi}/{ref_id}` | – | `{rsc, edge_meta:{dkapi\|dsapi:{<ref_id>:[{pn, pv, ct, lt}]}}}` | Air-purifier (CJ) filter-replacement record (`wwapp/viewmodel/filter/ControlCjViewModel.java:36`) | `:725-744, 383-405` |
| `PUT /dkapp/edge_meta/{dsapi\|dkapi}/{ref_id}/{pn}` | `{"pv":[{"filter_id":"…","replaced_at":"yyyy-MM-ddTHH:mm:ssZ"}]}`; `pn` = `extra_filters` | `{rsc}` | Record a filter replacement (`wwapp/viewmodel/filter/FilterReplacementViewModel.java:89`) | `:651-677`; `dknetlib/dk/data/zone/EditEdgeMetaParamBuilder.java` |
| `PUT /dsiot/buildings/{bId}` | `{"name":"…","location":{"latitude":"…","longitude":"…","code":"…","name":"…"}}` (either field may be omitted; Gson drops nulls) | `{rsc}` | Rename a building (`wwapp/view/unitlist/EditZoneNameFragment.java:505`); set a building location from a map pick plus `/city` (`wwapp/viewmodel/buildinglocation/BuildingLocationSettingViewModel.java:125`) | `:624-649` |
| `PUT /dsiot/buildings/{bId}/zones/{zId}` | `{"name":"…","support_info":[{"enable_support_type":[int],"members":["…"]}]}` | `{rsc}` | Rename a room (`EditZoneNameFragment.java:572-578`); "support drive" room grouping (`wwapp/view/supportdrive/SupportDriveFragment.java:373`) | `:679-704` |
| `POST /dsiot/buildings/{bId}/{zones\|floors}/{zId}/edges` | `{"ref_id":"<edge id = node auth port>","api_type":"dsapi\|dkapi"}` | `{rsc, pc:{id}}` (the new edge-assignment id) | Assign a unit to a room or floor (`wwapp/view/unitlist/EditUnitInfoFragment.java:649-651`) | `:573-599` |
| `DELETE /dsiot/buildings/{bId}/{zones\|floors}/{zId}/edges/{edgeAssignId}` | – | `{rsc}` | Remove a unit from a room or floor (`EditUnitInfoFragment.java:578`) | `:601-622` |

Types (Gson field names): `Building{id, name, location{code,name,latitude,longitude}, zones:[Zone], floors:[Zone]}`, `Zone{id, name, parent_id, edges:[Edge], support_info:[{enable_support_type:[int], members:[str]}]}`, `Edge{id, ref_id, parent_id, api_type}` (`dknetlib/dk/data/zone/DKBuilding.java`, `DKZone.java`, `DKEdge.java`, `DKSupportInfo.java`). The support-type ints are `RoomTemperature=0`, `Ventilation=1`, `Humidity=2`, `EcoCuteRoomAirConditioner=10` (`DKSupportType.java:22-26`). `EdgeMetaInfo{pn:"extra_filters", pv:[{filter_id, replaced_at}], ct, lt}` (`GPFMetaDataController.java:285-346`).

Creating or deleting buildings and zones is not possible from the app. `RequestCreateBuildingParam`, `RequestCreateZoneParam`, `RequestDeleteBuildingParam` and `RequestDeleteZoneParam` exist, but no code references them.

Status handling (`GPFMetaDataController.java:531-571, 780-977`):
- `rsc` values `2000`, `2001`, `2002`, `2004`, `4001` and `5000` all map to OK in the decompiled switch.
- The other mappings are:
  - `401`: UNAUTHORIZED
  - `500`: INTERNAL_SERVER_ERROR
  - `4000`: BAD_REQUEST
  - `4003`: FORBIDDEN
  - `4004`: NOT_FOUND
  - `4110`: REACH_MAX
  - `5003`: SERVER_MAINTENANCE
  - `6000`: UNKNOWN
  - anything else: NG
- For `app_config_all`, a synthesized HTTP-error body has no top-level `rsc`, so the result is `6000`/UNKNOWN.
- When the top-level and buildings `rsc` are both 2000, an edge-meta `rsc` of `4001` or `5003` is propagated. `isEdgeMetaEnabled` is set when the edge-meta result is OK or NOT_FOUND.

### Weather host (`app-weather.daikinsmartdb.jp`, `Bearer cd_accessToken`)

| Method + path | Body | Response | Feature | Ref |
|---|---|---|---|---|
| `GET /city?lat={lat}&lon={lon}` | – | `{rsc:int, cityData:[{code, name}]}` | Building location picker | `GPFMetaDataController.java:706-723, 260-281`; `wwapp/view/buildinglocation/BuildingLocationSettingFragment.java:272` |
| `GET /weather-linkage-setting?deviceId={edgeId}` | – | Flat map with keys `isSettingWeatherForecast`, `targetAlertList`, `isSettingWeatherAlert` **[inferred]**, matching `dknetlib/dk/data/DKWeatherLinkage.java:22-30` | EcoCute water-heater weather linkage (`wwapp/viewmodel/eq/EqBaseViewModel.java:497`) | `dknetlib/gpf/net/request/common/GPFWeatherLinkageController.java:88-91` |
| `POST /weather-linkage-setting` | `{"deviceId":"<edgeId>","isSettingWeatherForecast":bool,"targetAlertList":["…"],"isSettingWeatherAlert":bool}` (nulls omitted) | `{rsc}` | Same feature (`wwapp/viewmodel/eq/WeatherLinkageViewModel.java:31`, `WeatherMoreBoilingViewModel.java:327`) | `GPFWeatherLinkageController.java:116-137` |

### Push notification registration

`os_type` is always `"A"` (the app's `device` key is renamed; `GPFDataConverter.java:956,992`). `device_token` is the FCM token.

| Method + path | Body | Response | Feature | Ref |
|---|---|---|---|---|
| `POST /dsiot/terminals` | `{uuid, device_token, os_type}` | `{rsc}` | Register the phone's push token (`isUpdate:"false"`) | `dknetlib/gpf/net/request/common/GPFDeviceInfoManagementController.java:68-90`; `dknetlib/core/data/g.java:55-70`; `E4/K.java:817-823` |
| `PUT /dsiot/terminals/{uuid}/device_token` | `{uuid, device_token, os_type}` | `{rsc}` | Update the token (`isUpdate:"true"`) | `GPFDeviceInfoManagementController.java:92-113` |
| `GET /dsiot/terminals/{uuid}/device_token` | – | Flat map (DataType `DKDeviceTokenSetting`) | Check the registered token | `GPFDeviceInfoManagementController.java:33-39`; `E4/K.java:192` |
| `GET /dsiot/subscription/{uuid}/{resource_id}` | – | `{ra_flg, aq_flg, we_flg, wf_flg, cj_filter_flg, lo_pat_flg, hi_pat_flg, err_notify_flg, eq_hw_fill_flg, eq_unused_flg, eq_close_flg, eq_unit_err_flg, vh_filter_care_flg}` ("0"/"1"; missing flags default to "0") | Per-unit notification settings screens (`wwapp/view/unitcontrol/*/…Notification*`, `O4/c.java`) | `dknetlib/gpf/net/request/common/GPFEquipmentNoticeSubscribeManagementController.java:34-42`; `dknetlib/gpf/data/GPFDataConverter.java:732` |
| `POST /dsiot/subscription` | `{uuid, device_token, os_type, resource_id, ra_flg, ra_low_flg, aq_flg, cc_flg, we_flg, wf_flg, cj_filter_flg, lo_pat_flg, hi_pat_flg, err_notify_flg, eq_hw_fill_flg, eq_unused_flg, eq_close_flg, eq_unit_err_flg, vh_filter_care_flg}` (flags are strings "0"/"1"; app `on_flg`→`ra_flg`, `low_on_flg`→`ra_low_flg`) | `{rsc}` | First subscribe for a unit (`isUpdate:"false"`, `O4/c.java:123-125`) | `…SubscribeManagementController.java:72-183`; `GPFDataConverter.java:992-1022`; `E4/K.java:747-755` |
| `PUT /dsiot/subscription/{uuid}` | Same keys | `{rsc}` | Change flags | `…SubscribeManagementController.java:186-297` |
| `GET /dsiot/adm_notification/subscriptions/{uuid}` | – | `{adm_push_rcv_flg:"0"\|"1", …}` | Daikin/admin announcement push toggle **[inferred]** (`wwapp/view/settings/AdmNotificationFragment.java:115`) | `dknetlib/gpf/net/request/common/GPFAdmNotificationController.java:33-35`; `E4/K.java:281` |
| `POST /dsiot/adm_notification/subscriptions` | `{uuid, language:"ja", adm_push_rcv_flg}` | `{rsc}` | First registration (`isUpdate:"post"`, `dknetlib/core/data/g.java:43`) | `GPFAdmNotificationController.java:58-80`; `E4/K.java:901-914` |
| `PUT /dsiot/adm_notification/subscriptions/{uuid}` | `{language, adm_push_rcv_flg}` | `{rsc}` | Toggle (`isUpdate:"put"` or absent; `dknetlib/d.java:196`) | `GPFAdmNotificationController.java:82-96` |

`DKDeviceTokenDelete`, used on logout/reset (`wwapp/view/settings/DialogInterfaceOnClickListenerC0776e.java:84`), has no GPF handler in `E4/K.java`, so the app never deletes the token in the cloud **[inferred]**.

### Equipment notices / message inbox

| Method + path | Body | Response | Feature | Ref |
|---|---|---|---|---|
| `GET /dsiot/message_info/count_info/{uuid}/{resource_id}` | – | `{message_info:[{resource_id, unread, total}]}` | Unread badge on the unit list (`wwapp/view/unitlist/UnitSearch.java:717-750`) | `dknetlib/gpf/net/request/common/GPFEquipmentNoticeExistController.java:30-38`; `GPFDataConverter.java:639-686` |
| `GET /dsiot/message_info/messages/{uuid}/{resource_id}` | – | `{message_info:[{sent_at:"yyyy-MM-ddTHH:mm:ssZ", message_number, message_id, read_f}]}` | Per-unit notice list (RA/CJ/VH/EQ/RD control screens) | `…/GPFEquipmentNoticeInfoController.java:38-46`; `GPFDataConverter.java:689-729` |
| `PUT /dsiot/message_info/messages/{uuid}/{message_number}` | `{uuid, message_number, resource_id}` (app `msg_no`→`message_number`) | `{rsc}` | Mark a notice as read (`com/bumptech/glide/e.java:398-415`) | `…/GPFEquipmentNoticeInfoController.java:83-106`; `GPFDataConverter.java:974` |

The app turns the response lists into strings of the form `id:resource_id:unread:total/…` and `yyyy-MM-dd HH_mm_ss:msg_no:msg_id:read_f/…` for display only.

### Terms of use (`GPFTermOfUseInfoController`)

| Method + path | Body | Response | Ref |
|---|---|---|---|
| `GET /dsiot/terms_info/{uid}` (`uid` from the session, else the stored user id; `E4/C0030e.java:261`) | – | `rsc` is what matters. `2000` means a record exists and triggers a PUT; `4004` means none exists and triggers a POST | `dknetlib/gpf/net/request/common/GPFTermOfUseInfoController.java:32-35`; `E4/K.java:200, 869-887` |
| `POST /dsiot/terms_info` | `{version, accepted_at:"yyyy-MM-ddTHH:mm:ssZ", p_version, p_accepted_at}` (the `p_*` privacy-policy fields only if accepted) | `{rsc}` | `…:65-100`; `GPFDataConverter.java:1024-1066` |
| `PUT /dsiot/terms_info/{p_uid\|uid}` | Same, sent through `multiSet` | `{rsc}` | `…:103-146` |

The app triggers this after login when a terms version and consent date are stored locally (`E4/C0030e.java:204-240`).

### Filter-cleaning notification (FCN), RA only

`edge_device_id` in these calls is the unit property `edid` (`adp_i.edid`; `dknetlib/gpf/data/GPFConvertValue.java:61`). Callers are in `wwapp/view/unitcontrol/ra/RaUnitCtrlFragment.java:1125-1145, 1316`.

| Method + path | Body | Response | Ref |
|---|---|---|---|
| `GET /dsiot/fcn/status/{edid}` | – | Flat: `fcn_state` (`ON`/`RESET`/`OFF`), `is_fcn_threshold_breached`, `is_fcn_alert_a_reminder`, `is_fcn_alert` (`"true"`) → drives filter-clean UI and reminder dialogs (`wwapp/view/settings/M.java:416-443`) | `dknetlib/gpf/net/request/common/GPFSessionInfoController.java:86-93` |
| `POST /dsiot/fcn/status` | `{"ri":"<edid>","status":"ON\|OFF\|RESET"}` (app status `1`→ON, `0`→OFF, else RESET) | Checked only on the result type | `…:286-299`; `dknetlib/gpf/net/request/common/GPFClubDaikinAutentification.java:145` |
| `POST /dsiot/fcn/reminder/set` | `{"ri":"<edid>","reminder_time":"…"}` (`reminder_time` only if non-empty) | Result type only | `…:370-378`; `GPFClubDaikinAutentification.java:127` |

### `/api/*` (main host)

In these calls `edge_device_id` is the unit's display name (`CommonFunction.e`, `wwapp/util/CommonFunction.java:69`) on the RA and VRV screens, but the adapter SSID in Unit Settings (`wwapp/view/settings/UnitSettingsFragment.java:368`). The backend probably keys on the adapter SSID or default name **[inferred]**.

| Method + path | Body | Response | Feature | Ref |
|---|---|---|---|---|
| `GET /api/weatherinfo?edge_device_id={id}&aqi=no&weather=yes` | – | `{result_cd:"200", body:{location_name, weather_data:{weather_condition:{code}, is_day}}}` | Weather tile on the RA/VRV control screen, cached for 1 h | `GPFSessionInfoController.java:110-117`; `wwapp/view/unitcontrol/ra/L.java:112-126`; `RaUnitCtrlFragment.java:1006-1016` |
| `GET /api/weatherinfo?edge_device_id={id}&aqi=yes&weather=no` | – | `{result_cd:"200", body:{"overall aqi value":"<n>"}}` | "CITY AQI" chip, cached for 1 h | `…:78-85`; `L.java:56-70` |
| `POST /api/machineinfo/list` | `{"ri":"<id>"}` | `{result_cd:"200", body:{data:{model_name, …}}}` | Model name in unit control and unit settings | `…:119-130`; `wwapp/view/settings/M.java:444-454` |
| `PUT /api/machineinfo` | `{"ri":"<unit name>","model_name":"…","serial_no":"…"}` | `result_cd` | Save the model and serial number after adding a unit (QR/serial flow; `wwapp/view/premises/PremisesUnitListFragment.java:445-470`) | `…:398-410`; `GPFClubDaikinAutentification.java:533` |
| `POST /api/locinfo` | `{edge_device_id, latitude, longitude, pincode}` | Result type | Register the unit location when it is added (`PremisesUnitListFragment.java:1051-1080`) | `…:253-269`; `GPFClubDaikinAutentification.java:242` |
| `PUT /api/locinfo/{edge_device_id}` | `{latitude, longitude, pincode}` | Result type | Edit the unit location (`wwapp/view/unitlist/EditUnitInfoFragment.java:1090-1111`) | `…:380-396`; `GPFClubDaikinAutentification.java:262` |
| `GET /api/faqinfo?deviceType={ra\|vrv}` | – | `{result_cd:"200", body:[{id, category, title, answer}]}` | FAQ screen (`wwapp/view/faq/FaqFragment.java:398-440`; `R/a.java:494-527`) | `…:95-101` |
| `GET /api/supportedmodels/list?country_code={cc}` | – | `{result_cd:"200", body:[{id, model_no, status, type?}]}`, or `body`/`message` holding an error string | Model list for Add Unit by QR (`wwapp/view/addUnit/AddUnitQRCodeScanFragment.java:438-560`; `R/a.java:434-470`) | `…:103-109` |
| `POST /dsiot/duplicate_unit_detection` | `{ssid, uid}` | – | Unused: no caller of `DKDuplicateUnitDetection` | `…:70-77`; `GPFClubDaikinAutentification.java:349` |
| `GET /multicountry/get_supported_countries` (account host, `Bearer cd_accessToken`) | – | `{success:true, body:[{country_code, country_name, dial_code, currency_symbol}]}` **[inferred shape]** | Country picker on the login and signup screens | `…:140-142`; `wwapp/view/settings/LoginFragment.java:510-520`; `wwapp/viewmodel/model/CountryData.java` |

Responses from these calls are all fed through `GPFSessionInfoController.onRequestFinished` (`:224-235`), which calls back through `onSetFinished` even for GETs.

### Device name, icon, erase, out-of-home, time

| Operation | Wire | Feature | Ref |
|---|---|---|---|
| Rename unit | `PUT /dsiot/multireq`, op 3 to `/dsiot/edges/{edgeId}.adp_d` with `{name}` (see the multireq section) | Edit Units / Edit Unit Info | `dknetlib/gpf/net/request/common/GPFDeviceNameController.java:40-53`; `GPFConvertValue.java:24` |
| Set icon | Same, with `{icon:<int>}` | Same | `…/GPFDeviceIconController.java:40-59` |
| Erase device from cloud | `POST /dsiot/multireq` `{"requests":[{"op":4,"to":"/dsiot/edges/{edgeId}","rqi":"1"}]}` (`op`/`to` come from the parent `Requests` class, `GPFBaseController.java:56,196`). Sent to the main host even when the adapter is local | Delete a unit (`wwapp/view/settings/DialogInterfaceOnClickListenerC0807u.java:191`) | `…/GPFEraseDeviceController.java:35-54, 125-139` |
| Out-of-home ON | Local adapter: `PUT http://<adapter>/config/adapter/user_info` `{"method":"polling","id_token":"<id_token>"}` (40 s timeout). This hands the adapter the user's token so it registers with the cloud | Settings, then Out-of-home (`wwapp/view/settings/OutOfHomeSettingsFragment.java`) | `…/GPFOutOfHomeController.java:144-157`; `…/GPFRemoteMethodSettingController.java:58-72` |
| Out-of-home OFF | Local `PUT /config/adapter/user_info` `{"method":"home_only","id_token":""}`. If that returns OK, the app also erases the device from the cloud as above | Same | `GPFOutOfHomeController.java:55-121, 135-142` |
| Read out-of-home mode | Local `GET /config/adapter/user_info` | – | `GPFRemoteMethodSettingController.java:22-29` |
| Remote date/time | `GET /premise/dsiot/system_info/version`. Only the HTTP `Date` header is read, and no auth header is sent. The app synthesizes `{rsc:2000,date,time,sta:2}` from it | Adapter clock display when remote | `…/GPFDateTimeController.java:25-36`; `GPFHttpController.java:189-240` |
| Notify info / notify datetime | Notify info is multireq on `/dsiot/edges/{id}.adp_d` (`notify.auto_off_flg`/`auto_off_tm`). Notify datetime is local `PUT /config/adapter/datetime`. Neither is a separate cloud REST endpoint | – | `…/GPFNotifyInfoController.java:23-80`; `…/GPFNotifyDateTimeController.java:40-53` |
| Firmware auto-update flag | multireq op 3 on `/dsiot/edges/{id}.adp_f` `{auto_update:int}` | Unit Settings | `…/GPFFwAutoUpdateController.java:40-59` |

### Account transfer (legacy account → new account)

`POST /premise/dsiot/account_transfer` (main host) with body `{"code":RSA(<old id/pw>),"user_id":"…","password":"…"}` (`code` built as for login; see `API.md`). The response is `rsc`; the app shows an error when no `rsc` is present. It is called from the login screen, and ACCOUNT_MIGRATED is `4105`. This call only migrates the account; there is no per-device transfer endpoint. Refs: `dknetlib/gpf/net/request/common/GPFAccountTransferController.java:69-93`, `E4/K.java:1042`, `wwapp/view/settings/RunnableC0799p0.java:78-169`.

### Gift codes

Gift codes use the legacy Daikin-protocol server node on the main host: `GET https://prod.daikinacmanager.com/common/gift_code_auth?gift_code=<code>`. The legacy client sends the auth-map `id_token` as a raw `Authorization` header with no "Bearer" prefix, plus `id=ID&spw=SPW` **[inferred: depends on the auth map at call time]**. The response is legacy `ret=…` text with `gift_code`, `auth_ret` and `kind` (`P` = Patrol, `/`-separated). `auth_ret` values: `OK`→Active, `NO AUTH`→UnAuth, `NO RECORD`→Invalid, `BEFORE`, `EXPIRE`→Expired, `FORBIDDEN`. The app re-validates a stored code at startup. Refs: `dknetlib/dk/data/DKGiftCodeManager.java:28-48`, `E4/K.java:635-641`, `dknetlib/dk/net/http/a.java:40-100`, `M4/a.java:20-35`, `Z4/d.java`, `jp/co/daikin/remoapp/MainActivity.java:527-529`.

### Firmware updates

There is no cloud firmware check. Update availability compares the adapter's `ver` with the hard-coded `3_10_0` (`dknetlib/p.java:207,230`). The image is bundled at `assets/Generation4/3_10_0/DKWL4G_OTA_CS_V3_10_0.bin` and pushed locally by `POST /config/firmware/update` (`dknetlib/gpf/net/request/common/GPFFWUploadController.java:100-160`).

### Other URL literals

- The legacy local-protocol paths in `E4/K.java:300-680` (`/common/basic_info`, `/aircon/*`, `/cleaner/*`, `/circulator/*`, `/dryer/get_unit_info`) are adapter-local and out of scope here.
- `/dsiot/edges/{id}?expand=ch` (`dknetlib/gpf/net/request/GPFExpandChController.java:55`) is a multireq op 2 target.
- The remaining `https://` literals are web links only: daikinindia.com, ac.daikin.co.jp FAQ and user guides, YouTube demos, WhatsApp support `9871409300` and flagcdn.com. They live in `wwapp/view/mymenu/MyMenuFragment.java:312-396` and similar files and are not APIs.
## Consolidated open questions

Each section above also lists its own open items. The ones that matter most for a Home Assistant integration:

| Area | Question | How to settle |
|---|---|---|
| Auth | This spec does not document the auth flow in detail (see [Authentication](#authentication)); rely on `API.md` and capture traffic. | mitmproxy capture of a login |
| Modes | Whether `0009`/`000A` are the running state inside Auto (auto→cool/heat) or distinct modes. The app treats them as cool/heat-family and never writes them. | Observe `p_01` while running Auto |
| Writes | Whether Powerful can be set via `e_3003.p_1B="01"` (the app never writes it). Exact semantics of `e_3003.p_2D`. | Live write test |
| Ranges | Whether `p_02`/`p_03` `md.mi/mx/st` carry real setpoint ranges (the app hard-codes 18–32 °C cool, 18–30 °C heat). | Read with `?filter=pv,md` |
| `md` | JSON type of `md.st` (app parses decimal int) and meaning of `pt` 2 vs 3. | Capture |
| Energy | Year energy unit (kWh vs 0.1 kWh); whether a single read of `adr_0200.history.h_01.data` works or only `expand=ch`; whether the last month element is yesterday or today; `mompow` units. | Capture and compare with app UI |
| Discovery | Exact members of the edge object's `ch[]`; `lt` format; relation of `adp_i.edid` to `ri`. | Capture edge list |
| Provisioning | Meaning of `rslt=0` in the `/config/wlan/connect/permit` loop; response keys of `connect/start` and `permit`. | Capture a setup |
| Other devices | VRV setpoint/room-temperature scaling; Cj room-temperature scale and history raw values; Eq/Vh several fields (see their sections). | Capture from those devices |
| Legacy | Enable parameter for `/aircon/set_special_mode`; legacy `get_model_info` capability keys. | Capture / pydaikin |
| Cloud misc | Whether `/api/*` `edge_device_id` expects the unit name (as the app sends, apparently a bug) or the edge id; whether `result_cd` is a string. | Capture |
