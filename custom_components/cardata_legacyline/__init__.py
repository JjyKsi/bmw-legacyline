"""The Cardata Legacyline integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEBUG, DOMAIN
from .token_manager import TokenManager
from .vehicle_manager import VehicleCoordinator, VehicleService


@dataclass
class RuntimeData:
    """Runtime container stored per config entry."""

    token_manager: TokenManager
    vehicle_coordinator: VehicleCoordinator
    debug_enabled: bool


PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Cardata Legacyline component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cardata Legacyline from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    debug_enabled = entry.options.get(CONF_DEBUG, False)
    token_manager = TokenManager(hass, entry, debug_enabled)
    vehicle_service = VehicleService(hass, entry, token_manager, debug_enabled)
    vehicle_coordinator = VehicleCoordinator(hass, vehicle_service)
    await vehicle_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = RuntimeData(
        token_manager=token_manager,
        vehicle_coordinator=vehicle_coordinator,
        debug_enabled=debug_enabled,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Cardata Legacyline config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


def get_token_manager(hass: HomeAssistant, entry_id: str) -> TokenManager:
    """Return the token manager for a specific config entry."""

    runtime: RuntimeData = hass.data[DOMAIN][entry_id]
    return runtime.token_manager


def get_vehicle_coordinator(hass: HomeAssistant, entry_id: str) -> VehicleCoordinator:
    """Return the vehicle coordinator for a config entry."""

    runtime: RuntimeData = hass.data[DOMAIN][entry_id]
    return runtime.vehicle_coordinator


def is_debug_enabled(hass: HomeAssistant, entry_id: str) -> bool:
    """Return whether verbose debug logging is enabled for the entry."""

    runtime: RuntimeData = hass.data[DOMAIN][entry_id]
    return runtime.debug_enabled
