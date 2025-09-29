# Legacy (Non-Working) API Surface (Reference Only)

The older BMW ConnectedDrive integration exposed more endpoints than the
current working implementation. These details are provided as historical
reference; BMW may have changed or withdrawn the functionality. Always validate
before building on them.

## Vehicle Profile Details (v5)

Endpoint: `GET /eadrax-vcs/v5/vehicle-data/profile`

Payload includes:

- `brand`, `bodyType`, `model`, `color`, `productionDate`.
- `vehicleSoftwareVersion`, equipment packages, driver guide links.
- `mpo` media providers and communication services.
- `chargingSettingsCapabilities`, `chargingPreferencesCapabilities`.

The working API currently uses only `model` and `driveTrain`; the remaining
fields are candidates if richer metadata is desired.

## Charging Details (v2)

Endpoint: `GET /eadrax-crccs/v2/vehicles`

Contains:

- `chargingSettings` – AC current limit, target SoC, charging mode.
- `chargingProfile` – per-weekday schedules (actions, times).

The working solution ignores these; the legacy stack provided setters.

## Remote Service Variants (v4)

Endpoint template: `/eadrax-vrccs/v4/presentation/remote-commands/<service>`
with services such as `climate-now`, `remote360`, `inCarCamera`, etc. The legacy
code polled:

- `/eadrax-vrccs/v3/presentation/remote-commands/eventStatus?eventId=<id>`
- `/eadrax-vrccs/v4/presentation/remote-commands/eventPosition?eventId=<id>`

until the execution state reached `EXECUTED` or `DELIVERED`.

## Charging Statistics & Sessions

Endpoints:

- `GET /eadrax-chs/v2/charging-statistics`
- `GET /eadrax-chs/v2/charging-sessions`

Used historically to build charging history dashboards.

## Capability Matrix

State payloads expose nested capability objects (e.g. `remoteServices` with
`state: ACTIVATED/NOT_AVAILABLE`). The working API flattens these to simple
booleans; revisit the detailed structures if nuanced capability handling is
required.

## MQTT / Streaming (Unofficial)

Some forks connected to BMW’s telemetry MQTT feeds (often referred to as
"cardata"). These require additional authentication (not covered here) and are
out of scope for the working HTTPS-only approach.

## Refresh Token Persistence

Legacy logic stored `refresh_token`, `gcid`, and session IDs separately. The
current implementation keeps only the token object. If GCID is required (e.g.
for POI uploads), the old persistence strategy may need to be revived.

## Caveats

- Treat all endpoints above as experimental; confirm BMW still accepts the
  requests before relying on them.
- Many features depend on vehicle options and remote-service activation status.
- Respect rate limits and avoid aggressive polling.
