"""Token storage and refresh helpers for Cardata Legacyline."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .auth import AuthClient, AuthError
from .const import CONF_REGION, DATA_TOKEN, DATA_TOKEN_EXPIRES_AT


class TokenManager:
    """Manage access tokens for a config entry, performing refresh as needed."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry_id = entry.entry_id
        self._lock = asyncio.Lock()
        session = async_get_clientsession(hass)
        self._auth_client = AuthClient(session)

    def _get_entry(self) -> ConfigEntry:
        entry = self._hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:  # pragma: no cover - defensive
            raise ConfigEntryNotReady("Config entry not available")
        return entry

    async def async_get_access_token(self) -> str:
        """Return a valid access token, refreshing if expired."""

        token_payload = await self.async_get_token()
        access_token = token_payload.get("access_token")
        if not access_token:
            raise ConfigEntryAuthFailed("Missing access token")
        return access_token

    async def async_get_token(self) -> Dict[str, Any]:
        """Return the current OAuth token payload, refreshing if required."""

        async with self._lock:
            entry = self._get_entry()
            data = dict(entry.data)
            token_payload = dict(data.get(DATA_TOKEN) or {})
            expires_at = data.get(DATA_TOKEN_EXPIRES_AT)
            expires_dt = dt_util.parse_datetime(expires_at) if expires_at else None
            now = dt_util.utcnow()

            if (
                token_payload.get("access_token")
                and expires_dt is not None
                and expires_dt > now
            ):
                return dict(token_payload)

            refresh_token = token_payload.get("refresh_token")
            region = data.get(CONF_REGION)

            if not refresh_token or not region:
                raise ConfigEntryAuthFailed("Re-authentication required")

            try:
                auth_result = await self._auth_client.async_refresh(region, refresh_token)
            except AuthError as err:
                if err.reason == "invalid_auth":
                    raise ConfigEntryAuthFailed(err.message or "Authentication failed") from err
                if err.reason == "cannot_connect":
                    raise ConfigEntryNotReady(err.message or "Cannot connect to ConnectedDrive") from err
                raise ConfigEntryNotReady(err.message or "Unexpected authentication error") from err

            new_payload = dict(auth_result.token_payload)
            new_data = {
                **data,
                DATA_TOKEN: new_payload,
                DATA_TOKEN_EXPIRES_AT: auth_result.token_expires_at,
            }

            self._hass.config_entries.async_update_entry(entry, data=new_data)

            return new_payload
