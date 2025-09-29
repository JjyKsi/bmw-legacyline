"""Authentication helpers for the Cardata Legacyline integration."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
import async_timeout
from aiohttp import ClientError
from homeassistant.util import dt as dt_util

REDIRECT_URI = "com.bmw.connected://oauth"
SCOPE = (
    "openid profile email offline_access smacc vehicle_data perseus dlm svds "
    "cesim vsapi remote_services fupo authenticate_user"
)
PKCE_CHALLENGE_METHOD = "S256"
_AUTHENTICATE_PATH = "/oauth/authenticate"
_TOKEN_PATH = "/oauth/token"
_TIMEOUT = 30
_EARLY_EXPIRY_BUFFER = timedelta(minutes=15)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegionConfig:
    """Static OAuth client metadata for a ConnectedDrive region."""

    key: str
    auth_base: str
    api_base: str
    client_id: str
    state: str
    basic_authorization: str


REGION_CONFIGS: dict[str, RegionConfig] = {
    "row": RegionConfig(
        key="row",
        auth_base="https://customer.bmwgroup.com/gcdm",
        api_base="https://cocoapi.bmwgroup.com",
        client_id="31c357a0-7a1d-4590-aa99-33b97244d048",
        state="cEG9eLAIi6Nv-aaCAniziE_B6FPoobva3qr5gukilYw",
        basic_authorization=(
            "Basic "
            "MzFjMzU3YTAtN2ExZC00NTkwLWFhOTktMzNiOTcyNDRkMDQ4OmMwZTMzOTNkLTcwYTItNGY2Zi05ZDNjLTg1MzBhZjY0ZDU1Mg=="
        ),
    ),
    "na": RegionConfig(
        key="na",
        auth_base="https://login.bmwusa.com/gcdm",
        api_base="https://cocoapi.bmwgroup.us",
        client_id="54394a4b-b6c1-45fe-b7b2-8fd3aa9253aa",
        state="rgastJbZsMtup49-Lp0FMQ",
        basic_authorization=(
            "Basic "
            "NTQzOTRhNGItYjZjMS00NWZlLWI3YjItOGZkM2FhOTI1M2FhOmQ5MmYzMWMwLWY1NzktNDRmNS1hNzdkLTk2NmY4ZjAwZTM1MQ=="
        ),
    ),
}


class AuthError(Exception):
    """Raised when the authentication handshake fails."""

    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason
        self.message = message


@dataclass
class AuthResult:
    """Container for a successful authentication."""

    region: RegionConfig
    token_payload: Dict[str, Any]
    token_expires_at: str


class AuthClient:
    """Performs the OAuth handshake against ConnectedDrive."""

    def __init__(self, session: aiohttp.ClientSession, debug_enabled: bool = False) -> None:
        self._session = session
        self._debug_enabled = debug_enabled

    async def async_login(
        self,
        email: str,
        password: str,
        captcha_token: str,
        region_key: str,
    ) -> AuthResult:
        """Authenticate against the specified region and return the token payload."""

        region = REGION_CONFIGS.get(region_key)
        if not region:
            raise AuthError("unknown", f"Unsupported region: {region_key}")

        if self._debug_enabled:
            LOGGER.debug("AuthClient: starting login for region=%s", region_key)
        try:
            return await self._async_login_region(region, email, password, captcha_token)
        except AuthError:
            raise
        except ClientError as err:  # pragma: no cover - network issues
            raise AuthError("cannot_connect", str(err)) from err
        except asyncio.TimeoutError as err:
            raise AuthError("cannot_connect") from err

    async def _async_login_region(
        self,
        region: RegionConfig,
        email: str,
        password: str,
        captcha_token: str,
    ) -> AuthResult:
        """Execute the three-step login flow for a specific region."""

        code_verifier, code_challenge = _generate_pkce_pair()
        base_form = {
            "client_id": region.client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "state": region.state,
            "scope": SCOPE,
            "nonce": "login_nonce",
            "code_challenge_method": PKCE_CHALLENGE_METHOD,
            "code_challenge": code_challenge,
        }

        authorization = await self._async_step_authenticate(
            region,
            base_form,
            email,
            password,
            captcha_token,
        )

        auth_code = await self._async_step_authorization_code(region, base_form, authorization)

        token_payload = await self._async_step_exchange_token(
            region,
            auth_code,
            code_verifier,
        )
        return self._build_auth_result(region, token_payload)

    async def async_refresh(self, region_key: str, refresh_token: str) -> AuthResult:
        """Refresh an access token using the stored refresh token."""

        region = REGION_CONFIGS.get(region_key)
        if not region:
            raise AuthError("unknown", f"Unsupported region: {region_key}")

        form = {
            "redirect_uri": REDIRECT_URI,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            token_payload = await self._async_request_token(region, form)
        except AuthError:
            raise
        except ClientError as err:  # pragma: no cover - network issues
            raise AuthError("cannot_connect", str(err)) from err
        except asyncio.TimeoutError as err:
            raise AuthError("cannot_connect") from err

        return self._build_auth_result(region, token_payload)

    async def _async_step_authenticate(
        self,
        region: RegionConfig,
        base_form: dict[str, Any],
        email: str,
        password: str,
        captcha_token: str,
    ) -> str:
        """Submit credentials and return the authorization token."""

        form = base_form | {
            "username": email,
            "password": password,
            "grant_type": "authorization_code",
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "hcaptchatoken": captcha_token,
        }

        async with async_timeout.timeout(_TIMEOUT):
            async with self._session.post(
                f"{region.auth_base}{_AUTHENTICATE_PATH}",
                data=form,
                headers=headers,
                allow_redirects=False,
            ) as response:
                if self._debug_enabled:
                    LOGGER.debug(
                        "AuthClient: authenticate status=%s", response.status
                    )
                payload = await self._decode_json_response(response)

        redirect_to = payload.get("redirect_to")
        if not redirect_to:
            raise AuthError("invalid_auth", "Missing redirect target")

        authorization = _extract_query_param(redirect_to, "authorization")
        if not authorization:
            raise AuthError("invalid_auth", "Missing authorization token")

        return authorization

    async def _async_step_authorization_code(
        self,
        region: RegionConfig,
        base_form: dict[str, Any],
        authorization: str,
    ) -> str:
        """Exchange the authorization token for a short-lived code."""

        form = base_form | {"authorization": authorization}

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with async_timeout.timeout(_TIMEOUT):
            async with self._session.post(
                f"{region.auth_base}{_AUTHENTICATE_PATH}",
                data=form,
                headers=headers,
                allow_redirects=False,
            ) as response:
                location = response.headers.get("Location")
                body = await response.text()
                if self._debug_enabled:
                    LOGGER.debug(
                        "AuthClient: authorization code status=%s", response.status
                    )

        if response.status != 302:
            # Try to surface server-side JSON errors if available.
            try:
                error_payload = json.loads(body)
            except json.JSONDecodeError:
                error_payload = None
            raise _http_error_to_auth_error(response.status, error_payload)

        code = _extract_query_param(location or "", "code")
        if not code:
            raise AuthError("invalid_auth", "Missing authorization code")

        return code

    async def _async_step_exchange_token(
        self,
        region: RegionConfig,
        code: str,
        code_verifier: str,
    ) -> Dict[str, Any]:
        """Exchange the code for access and refresh tokens."""

        form = {
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        return await self._async_request_token(region, form)

    async def _async_request_token(
        self, region: RegionConfig, form: dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke the token endpoint and return the parsed payload."""

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": region.basic_authorization,
        }

        async with async_timeout.timeout(_TIMEOUT):
            async with self._session.post(
                f"{region.auth_base}{_TOKEN_PATH}",
                data=form,
                headers=headers,
                allow_redirects=False,
            ) as response:
                if self._debug_enabled:
                    LOGGER.debug(
                        "AuthClient: token request status=%s", response.status
                    )
                payload = await self._decode_json_response(response)

        if "error" in payload:
            raise AuthError("invalid_auth", payload.get("error_description") or "Token exchange failed")

        return payload

    def _build_auth_result(self, region: RegionConfig, token_payload: Dict[str, Any]) -> AuthResult:
        """Augment token payload with expiry metadata."""

        expires_in = token_payload.get("expires_in")
        now = dt_util.utcnow()
        expires_at = now
        if isinstance(expires_in, (int, float)):
            expires_at = now + timedelta(seconds=float(expires_in))
            expires_at -= _EARLY_EXPIRY_BUFFER
            if expires_at <= now:
                expires_at = now
        token_payload["region"] = region.key

        result = AuthResult(
            region=region,
            token_payload=token_payload,
            token_expires_at=expires_at.isoformat(),
        )
        if self._debug_enabled:
            LOGGER.debug(
                "AuthClient: obtained token for region=%s expires=%s", region.key, result.token_expires_at
            )
        return result

    async def _decode_json_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Decode a JSON payload and surface HTTP errors."""

        text = await response.text()
        if response.status >= 400:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
            raise _http_error_to_auth_error(response.status, payload)

        if not text:
            return {}

        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            raise AuthError("unknown", f"Invalid JSON response: {err}") from err


def _extract_query_param(source: str, key: str) -> Optional[str]:
    """Extract a query parameter from either a URL or a raw query string."""

    if not source:
        return None

    if source.startswith("redirect_uri="):
        source = source.split("redirect_uri=", maxsplit=1)[1]
    source = unquote(source)

    parsed = urlparse(source)
    query = parsed.query or parsed.path
    values = parse_qs(query)
    if key not in values:
        return None
    return values[key][0]


def _generate_pkce_pair() -> tuple[str, str]:
    """Return a PKCE verifier/challenge pair."""

    code_verifier = secrets.token_urlsafe(64)
    challenge_digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def _http_error_to_auth_error(status: int, payload: Optional[Dict[str, Any]]) -> AuthError:
    """Translate HTTP status + payload to an AuthError."""

    if payload:
        message = payload.get("error_description") or payload.get("error")
        if payload.get("error") in {"invalid_grant", "invalid_client", "unauthorized", "invalid_request"}:
            return AuthError("invalid_auth", message)
        if payload.get("error") == "invalid_captcha":
            return AuthError("invalid_auth", message or "Invalid captcha token")
    else:
        message = None

    if 400 <= status < 500:
        return AuthError("invalid_auth", message)

    return AuthError("cannot_connect", message)
