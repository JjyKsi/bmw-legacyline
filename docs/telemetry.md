# Telemetry Endpoints

EVCC performs three read-only HTTP calls to discover vehicles and obtain their
current state.

## 1. Vehicle Enumeration

```
GET {CocoApiURI}/eadrax-vcs/v4/vehicles?apptimezone=120&appDateTime=<unix_millis>
Authorization: Bearer <token>
<standard headers>
```

**Response** – JSON array. EVCC assumes the minimal schema:

```json
[
  {
    "VIN": "WBA...",
    "vin": "WBA...",          // casing varies; both handled
    "model": "...",            // may be placeholder ("CONNECTED")
    "appVehicleType": "...",   // e.g. "BEV", "PHEV", or proprietary labels
    "brand": "BMW"             // optional
  }
]
```

The VIN is required; all other fields are treated as optional.

## 2. Vehicle Profile (friendly model name)

For each VIN, EVCC requests the v5 profile endpoint to obtain the human-readable
model and drivetrain metadata.

```
GET {CocoApiURI}/eadrax-vcs/v5/vehicle-data/profile
Authorization: Bearer <token>
<standard headers>
bmw-vin: <VIN>
```

**Response** – large JSON object. EVCC currently consumes:

- `model` – marketing name (e.g. `iX xDrive50`).
- `driveTrain` – one of `ELECTRIC`, `PLUGIN_HYBRID`, `COMBUSTION`, etc.

Any failures (non-200 status, malformed JSON) are logged as warnings and the
implementation falls back to the values returned by the v4 vehicle list.

## 3. Vehicle State

```
GET {CocoApiURI}/eadrax-vcs/v4/vehicles/state?apptimezone=120&appDateTime=<unix_millis>
Authorization: Bearer <token>
<standard headers>
bmw-vin: <VIN>
```

**Relevant fields** (subset used by EVCC):

- `state.electricChargingState`
  - `chargingLevelPercent` – battery SoC (%).
  - `range` – remaining electric range (km).
  - `isChargerConnected` – boolean.
  - `chargingStatus` – `CHARGING`, `COMPLETED`, etc.
  - `chargingTarget` – target SoC (%).
- `state.currentMileage` – odometer (km).
- `state.climateControlState.activity` – `HEATING`, `COOLING`, or `OFF`.
- `state.range` (optional) – total remaining range.
- `state.chargingProfile` / `state.climateTimers` – currently ignored except for
  presence checks.

The state response is cached (`util.Cached`) with a configurable interval to
avoid hammering the API.

## Error Handling & Fallbacks

- If enumeration or state calls return an error, EVCC aborts vehicle creation.
- Missing numeric values default to zero (e.g. SoC, range, mileage) when exposed
  through the EVCC API interfaces.
- Unknown drivetrain strings default to `UNKNOWN`; the implementation does not
  attempt to derive drivetrain capabilities.
