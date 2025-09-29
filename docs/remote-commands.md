# Remote Commands

EVCC exposes a minimal set of remote actions, mirroring the behaviour in
`vehicle/bmw/provider.go`.

## Supported commands

| EVCC Method | API Action `string` | Endpoint | Notes |
|-------------|---------------------|----------|-------|
| `ChargeEnable(true)`  | `start-charging` | `POST {CocoApiURI}/eadrax-crccs/v1/vehicles/{vin}/start-charging` | Starts charging; succeeds only if the vehicle reports a connected charger. |
| `ChargeEnable(false)` | `stop-charging`  | `POST {CocoApiURI}/eadrax-crccs/v1/vehicles/{vin}/stop-charging`  | Stops charging. |
| `WakeUp()`            | `door-lock`      | `POST {CocoApiURI}/eadrax-vrccs/v3/presentation/remote-commands/{vin}/door-lock` | EVCC uses door lock as a wake-up trigger. |

Additional actions (light flash, horn, climate, etc.) are **not** invoked by
EVCC and therefore omitted here.

## Request Format

```
POST <endpoint>
Authorization: Bearer <token>
Accept: application/json
<standard headers>

// empty body
```

## Response

The API returns a JSON object:

```json
{
  "eventId": "...",
  "creationTime": "2025-01-01T12:34:56.000Z"
}
```

EVCC does **not** poll `/eventStatus`; it treats a successful HTTP response as a
completed command. Callers should perform any necessary follow-up validation via
`GET /vehicles/state`.

## Error Handling

- Non-2xx responses bubble up as errors.
- The client enforces `bmw-vin` in the headers when required (door-lock wakeup).
- No retries are performed.
