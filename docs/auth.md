# Authentication Flow

EVCC performs an OAuth 2.0 Authorization Code flow with PKCE against BMW’s
ConnectedDrive identity service. The same flow is used for both North America
(`login.bmwusa.com`) and Rest-of-World / Europe (`customer.bmwgroup.com`).

## Prerequisites

- **Credentials**: username (email), password, and a freshly acquired hCaptcha
  token (`hcaptchatoken`). The captcha token is single-use.
- **PKCE**: EVCC generates a random verifier (`code_verifier`) and the
  corresponding SHA256-based challenge (`code_challenge`).
- **Static client metadata** (see `regions.md`): `client_id`, `state`, and the
  HTTP `Authorization` header used when exchanging the authorization code for
  tokens.
- **Redirect URI**: `com.bmw.connected://oauth`
- **Scope** (single string):

  ```text
  openid profile email offline_access smacc vehicle_data perseus dlm svds cesim vsapi remote_services fupo authenticate_user
  ```

## Step 1 – Authenticate (username/password submission)

```
POST {AuthURI}/oauth/authenticate
Content-Type: application/x-www-form-urlencoded
hcaptchatoken: <captcha token>

client_id=<ClientID>
response_type=code
redirect_uri=com.bmw.connected://oauth
state=<State>
scope=<scope string>
nonce=login_nonce
code_challenge_method=S256
code_challenge=<PKCE challenge>
username=<username>
password=<password>
grant_type=authorization_code
```

**Response**: JSON payload containing `redirect_to`, typically of the form
`redirect_uri=com.bmw.connected://oauth?authorization=<AUTH>`.

- Extract the `authorization` query parameter.
- The captcha token **must** be discarded after this call (EVCC clears it).

## Step 2 – Exchange authorization token for a code

```
POST {AuthURI}/oauth/authenticate
Content-Type: application/x-www-form-urlencoded

client_id=<ClientID>
response_type=code
redirect_uri=com.bmw.connected://oauth
state=<State>
scope=<scope string>
nonce=login_nonce
code_challenge_method=S256
code_challenge=<PKCE challenge>
authorization=<AUTH>
```

**Response**: HTTP 302 with `Location` header pointing at the redirect URI and a
`code` query parameter (`com.bmw.connected://oauth?code=<CODE>`).

## Step 3 – Token exchange

```
POST {AuthURI}/oauth/token
Content-Type: application/x-www-form-urlencoded
Authorization: <Basic token from regions.md>

code=<CODE>
code_verifier=<PKCE verifier>
redirect_uri=com.bmw.connected://oauth
grant_type=authorization_code
```

**Response (JSON)**:

```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3599,
  "refresh_token": "...",
  "gcid": "..."
}
```

EVCC stores the full token object (including `refresh_token` and calculated
expiry) in its local settings database.

## Refresh Tokens

To refresh, EVCC posts to the same token endpoint:

```
POST {AuthURI}/oauth/token
Content-Type: application/x-www-form-urlencoded
Authorization: <Basic token>

redirect_uri=com.bmw.connected://oauth
refresh_token=<stored refresh token>
grant_type=refresh_token
```

On failure (`invalid_client`, etc.) the caller must restart the full flow with a
new captcha token.

## Notes

- HTTP client does **not** follow redirects; EVCC inspects the `Location`
  header manually.
- Cookie jar and redirect handling are disabled during login (EVCC sets
  `DontFollow`).
- Token responses are wrapped with a 15-minute early expiry buffer when building
  the reusable token source (`oauth2.ReuseTokenSourceWithExpiry`).
- Any JSON field `error` / `error_description` returned during authentication is
  logged and raised as a wrapped error.
