"""Config flow for the Cardata Legacyline integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .auth import AuthClient, AuthError, REGION_CONFIGS
from .const import (
    CONF_CAPTCHA,
    CONF_REGION,
    DATA_TOKEN,
    DATA_TOKEN_EXPIRES_AT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CardataLegacylineConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Cardata Legacyline config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: config_entries.ConfigEntry | None = None
        self._form_defaults: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Prompt for credentials and execute the auth handshake."""

        errors: dict[str, str] = {}

        if user_input is None:
            return self._show_user_form(errors)

        email = user_input[CONF_EMAIL].strip()
        password = user_input[CONF_PASSWORD]
        captcha = user_input[CONF_CAPTCHA].strip()
        region = user_input[CONF_REGION]

        session = async_create_clientsession(self.hass)
        client = AuthClient(session)

        try:
            auth_result = await client.async_login(email, password, captcha, region)
        except AuthError as err:
            errors["base"] = err.reason or "unknown"
            if err.message:
                _LOGGER.debug("Auth error: %s", err.message)
        except Exception as err:  # pragma: no cover - safeguard
            _LOGGER.exception("Unexpected authentication failure")
            errors["base"] = "unknown"
        else:
            unique_id = f"{email.lower()}_{auth_result.region.key}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            data = {
                CONF_EMAIL: email,
                CONF_REGION: auth_result.region.key,
                DATA_TOKEN: auth_result.token_payload,
                DATA_TOKEN_EXPIRES_AT: auth_result.token_expires_at,
            }

            if self._reauth_entry:
                self.hass.config_entries.async_update_entry(self._reauth_entry, data=data)
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            return self.async_create_entry(title=email, data=data)

        self._form_defaults = {CONF_EMAIL: email, CONF_REGION: region}
        return self._show_user_form(errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> config_entries.ConfigFlowResult:
        """Handle a reauth initiated by the integration."""

        entry_id = self.context.get("entry_id")
        if entry_id:
            self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
            if self._reauth_entry:
                self._form_defaults = {
                    CONF_EMAIL: self._reauth_entry.data.get(CONF_EMAIL, ""),
                    CONF_REGION: self._reauth_entry.data.get(CONF_REGION, "row"),
                }
        return await self.async_step_user()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Compatibility shim for legacy reauth flows."""

        return await self.async_step_user(user_input)

    @callback
    def _show_user_form(self, errors: Mapping[str, str]) -> config_entries.ConfigFlowResult:
        """Render the user credential form."""

        defaults = {
            CONF_EMAIL: self._form_defaults.get(CONF_EMAIL, ""),
            CONF_REGION: self._form_defaults.get(CONF_REGION, "row"),
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=defaults[CONF_EMAIL]): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_CAPTCHA): str,
                vol.Required(CONF_REGION, default=defaults[CONF_REGION]): vol.In(sorted(REGION_CONFIGS.keys())),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
