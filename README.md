# Cardata Legacyline

Custom integration scaffold for connecting Home Assistant to Cardata's Legacyline platform. Implementation work still pending.

## Installation via HACS
1. Ensure the Home Assistant instance runs 2024.4 or newer.
2. Add this repository as a custom integration in HACS (`HACS` → `Integrations` → `+` → `Custom repositories`).
3. Pick `Integration` as the category and confirm.
4. Install the "Cardata Legacyline" integration from the HACS store.
5. Restart Home Assistant.

## Development Notes
- The actual API client and feature implementation live under `docs/` for now; review those files before adding functionality.
- The integration uses the domain `cardata_legacyline`. The initial configuration flow signs in with email, password, region, and a single-use captcha token before any platforms are loaded.
- Access and refresh tokens are stored in the config entry data and refreshed automatically with the documented OAuth flow.
- On startup the integration requests the ConnectedDrive vehicle list/profile and exposes static sensors for each discovered VIN.
- Use the integration options (Configuration → Integrations → Cardata Legacyline → Configure) to toggle verbose debug logging during development.
