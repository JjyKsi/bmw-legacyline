# EVCC BMW ConnectedDrive API Documentation

This documentation describes the HTTP interactions the current working
implementation uses to authenticate against BMW ConnectedDrive,
retrieve vehicle telemetry, and trigger remote actions. It is derived directly
from the EVCC Go implementation (`vehicle/bmw`) and the accompanying Go utility
packages.

## Document Structure

- `auth.md` – complete OAuth 2.0 flow (PKCE, captcha handling, refresh).
- `http-client.md` – base URLs, mandatory headers, and transport behavior.
- `telemetry.md` – read-only REST calls (vehicle list and live state) and data
  expectations.
- `remote-commands.md` – supported remote actions and their request / response
  contracts.
- `regions.md` – static configuration per region (EU/ROW vs NA).
- `data-mapping.md` – how API responses map onto EVCC’s internal vehicle
  interfaces (SoC, range, odometer, etc.).
- `legacy-features.md` – reference notes for the non-working / legacy API surface; these
  endpoints are not part of the working solution and may be deprecated, but they
  highlight additional data that could be reintroduced if the payloads still
  match.

These files are sufficient for another developer to recreate a compatible
implementation from scratch.
