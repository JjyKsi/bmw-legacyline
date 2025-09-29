# Region Configuration

EVCC hard-codes the OAuth client metadata for each supported ConnectedDrive
region. Use these values verbatim when reproducing the flow described in
`auth.md`.

## Rest of World / Europe (`row`)

```
AuthURI:  https://customer.bmwgroup.com/gcdm
dAPI URI: https://cocoapi.bmwgroup.com
ClientID: 31c357a0-7a1d-4590-aa99-33b97244d048
State:    cEG9eLAIi6Nv-aaCAniziE_B6FPoobva3qr5gukilYw
Basic Authorization (token exchange):
  Basic MzFjMzU3YTAtN2ExZC00NTkwLWFhOTktMzNiOTcyNDRkMDQ4OmMwZTMzOTNkLTcwYTItNGY2Zi05ZDNjLTg1MzBhZjY0ZDU1Mg==
Captcha site key (hCaptcha): 10000000-ffff-ffff-ffff-000000000001 (generic)
```

## North America (`na`)

```
AuthURI:  https://login.bmwusa.com/gcdm
dAPI URI: https://cocoapi.bmwgroup.us
ClientID: 54394a4b-b6c1-45fe-b7b2-8fd3aa9253aa
State:    rgastJbZsMtup49-Lp0FMQ
Basic Authorization (token exchange):
  Basic NTQzOTRhNGItYjZjMS00NWZlLWI3YjItOGZkM2FhOTI1M2FhOmQ5MmYzMWMwLWY1NzktNDRmNS1hNzdkLTk2NmY4ZjAwZTM1MQ==
Captcha site key (hCaptcha): dc24de9a-9844-438b-b542-60067ff4dbe9
```

### Notes

- Scope and redirect URI are identical across regions (see `auth.md`).
- EVCC currently supports only these two regions. Any other region (e.g. China)
  requires a different login flow and is out of scope.
- `app_version` strings used in HTTP headers are `4.9.2(36892)` for both
  regions.
