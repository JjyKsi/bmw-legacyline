# Data Mapping to EVCC Interfaces

EVCC wraps the ConnectedDrive responses in `vehicle/bmw/provider.go`, exposing
them through the generic EVCC vehicle interfaces.

## Cached Status

- `statusG`: `util.Cached(api.Status)` – cache duration is configurable via the
  `cache` setting (defaults to EVCC’s global vehicle interval).
- `actionS`: direct wrapper around `api.Action`.

## Interface Implementations

| EVCC Interface Method | Source JSON Field | Notes |
|-----------------------|-------------------|-------|
| `Soc()` | `state.electricChargingState.chargingLevelPercent` | Returned as `float64`. Missing values map to `0`. |
| `Status()` | `state.electricChargingState.isChargerConnected` and `state.electricChargingState.chargingStatus` | Yields `StatusA` (disconnected), `StatusB` (connected), or `StatusC` (charging). Any API error produces `StatusNone`. |
| `Range()` | `state.electricChargingState.range` | Integer kilometres. |
| `Odometer()` | `state.currentMileage` | Converted to kilometres (float64). |
| `GetLimitSoc()` | `state.electricChargingState.chargingTarget` | Returns the configured target SoC (%). |
| `Climater()` | `state.climateControlState.activity` | `true` if activity is `HEATING` or `COOLING`. |
| `WakeUp()` | `api.Action(vin, "door-lock")` | Uses door lock as a wakeup ping. |
| `ChargeEnable(true/false)` | `api.Action(vin, "start-charging" / "stop-charging")` | No polling of event status. |

Errors returned by the HTTP calls bubble up directly to the EVCC scheduler. Any
missing JSON fields default to zero values as noted above.
