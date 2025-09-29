# HTTP Client Behaviour

EVCC wraps a standard HTTP client with the following requirements before
invoking any ConnectedDrive endpoints.

## Base Hosts

| Region          | Auth Base (`AuthURI`)                | API Base (`CocoApiURI`)           |
|-----------------|--------------------------------------|-----------------------------------|
| Rest of World / EU (`row`) | `https://customer.bmwgroup.com/gcdm` | `https://cocoapi.bmwgroup.com` |
| North America (`na`)       | `https://login.bmwusa.com/gcdm`     | `https://cocoapi.bmwgroup.us`  |

(See `regions.md` for related client IDs and credentials.)

## OAuth Transport

All HTTP requests are executed with an `oauth2.Transport` that injects the
Bearer token obtained via the flow described in `auth.md`. Token refresh is
handled transparently by the transport.

## Default Headers

Every request starts with the following header set (values shown for brand
`bmw`):

```
accept: application/json
accept-language: en
x-raw-locale: en-US
user-agent: Dart/3.3 (dart:io)
x-user-agent: android(AP2A.<hash>-NNN);<brand>;<app_version>;<region>
X-User-Agent: android(SP1A.210812.016.C1);<brand>;99.0.0(99999);<region>
bmw-units-preferences: d=KM;v=L;p=B;ec=KWH100KM;fc=L100KM;em=GKM;
24-hour-format: true
```

Notes:

- `<brand>` is the logical vehicle brand (e.g. `bmw`, `mini`).
- `<app_version>` is region-specific (currently `4.9.2(36892)` for both NA/ROW).
- `<region>` is the two-letter ConnectedDrive region (`na` or `row`).
- The lowercase `x-user-agent` uses a deterministic host hash plus a
  per-process random suffix (format `AP2A.XXXXXX.XXX-NNN`).
- An additional header (`X-User-Agent`) is injected by the transport decorator to
  mimic the Android Connected app build, matching the hard-coded string in the
  Go implementation.

Per-request headers are added as needed (for example `bmw-vin` for state calls
or `Accept: application/json` when performing remote commands).

## Query Parameters & Timestamp

EVCC timestamps every telemetry request with UNIX epoch milliseconds and sets
`apptimezone=120` (two hours) when calling `/eadrax-vcs/v4` endpoints. This is a
static mimic of the official app behaviour.

## Error Handling

- JSON parsing errors and HTTP status codes ≥ 400 are surfaced directly; the Go
  helper wraps errors with contextual messages (e.g. `StatusCode Message`).
- `bmw-vin` header is required for state and remote-command endpoints; EVCC
  aborts if the header is missing.
- The client does not retry failed calls unless the upstream helper is wrapped
  with `util.Cached` (see `telemetry.md`).
