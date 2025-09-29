"""The Cardata Legacyline integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .token_manager import TokenManager


@dataclass
class RuntimeData:
    """Runtime container stored per config entry."""

    token_manager: TokenManager


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Cardata Legacyline component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cardata Legacyline from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = RuntimeData(
        token_manager=TokenManager(hass, entry)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Cardata Legacyline config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


def get_token_manager(hass: HomeAssistant, entry_id: str) -> TokenManager:
    """Return the token manager for a specific config entry."""

    runtime: RuntimeData = hass.data[DOMAIN][entry_id]
    return runtime.token_manager
