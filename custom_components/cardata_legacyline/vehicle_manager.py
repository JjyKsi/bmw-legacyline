"""Vehicle data fetching for Cardata Legacyline."""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Dict

import async_timeout
from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .auth import REGION_CONFIGS, RegionConfig
from .const import CONF_REGION
from .token_manager import TokenManager

_TIMEOUT = 30
_BRAND_DEFAULT = "BMW"
_APP_VERSION = "4.9.2(36892)"

LOGGER = logging.getLogger(__name__)


@dataclass
class VehicleSummary:
    """Basic information about a vehicle."""

    vin: str
    brand: str | None
    model: str | None
    drive_train: str | None
    app_vehicle_type: str | None
    raw: Dict[str, Any]

    @property
    def device_name(self) -> str:
        """Generate a friendly device name."""

        if self.model:
            return self.model
        if self.brand:
            return f"{self.brand} {self.vin[-6:]}"
        return self.vin

    @property
    def manufacturer(self) -> str:
        """Return the manufacturer for device info."""

        if self.brand:
            return self.brand.upper()
        return _BRAND_DEFAULT


class VehicleService:
    """Fetch vehicle metadata from the ConnectedDrive API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        token_manager: TokenManager,
        debug_enabled: bool,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._token_manager = token_manager
        self._session = async_get_clientsession(hass)
        region = entry.data.get(CONF_REGION, "row")
        self._x_user_agent = _generate_mobile_agent(region)
        self._X_user_agent = f"android(SP1A.210812.016.C1);bmw;99.0.0(99999);{region}"
        self._debug_enabled = debug_enabled

    async def async_fetch(self) -> dict[str, VehicleSummary]:
        """Fetch the latest vehicle summaries."""

        region_key = self._entry.data.get(CONF_REGION)
        if not region_key:
            raise ConfigEntryNotReady("Region missing from config entry")

        region = REGION_CONFIGS.get(region_key)
        if not region:
            raise ConfigEntryNotReady(f"Unsupported region: {region_key}")

        if self._debug_enabled:
            LOGGER.debug("VehicleService[%s]: fetching vehicles for region=%s", self._entry.entry_id, region_key)

        try:
            token = await self._token_manager.async_get_access_token()
        except ConfigEntryAuthFailed:
            raise
        except ConfigEntryNotReady:
            raise
        except Exception as err:  # pragma: no cover - safeguard
            raise ConfigEntryNotReady(str(err)) from err

        headers = _build_headers(token, region, self._x_user_agent, self._X_user_agent)

        try:
            vehicles = await self._async_get_vehicle_list(region, headers)
        except ConfigEntryAuthFailed:
            raise
        except ConfigEntryNotReady:
            raise

        if self._debug_enabled:
            LOGGER.debug(
                "VehicleService[%s]: enumerated %d vehicles", self._entry.entry_id, len(vehicles)
            )

        summaries: dict[str, VehicleSummary] = {}
        for vehicle in vehicles:
            vin = _extract_vin(vehicle)
            if not vin:
                continue
            if self._debug_enabled:
                LOGGER.debug("VehicleService[%s]: processing VIN %s", self._entry.entry_id, vin)

            try:
                profile = await self._async_get_vehicle_profile(region, headers, vin)
            except UpdateFailed as err:
                LOGGER.warning("Failed to fetch vehicle profile for %s: %s", vin, err)
                profile = {}
            summaries[vin] = VehicleSummary(
                vin=vin,
                brand=_as_str(vehicle.get("brand")) or _as_str(profile.get("brand")),
                model=_as_str(profile.get("model")) or _as_str(vehicle.get("model")),
                drive_train=_as_str(profile.get("driveTrain")),
                app_vehicle_type=_as_str(vehicle.get("appVehicleType")),
                raw={"enumeration": vehicle, "profile": profile},
            )

        return summaries

    async def _async_get_vehicle_list(
        self,
        region: RegionConfig,
        headers: Dict[str, str],
    ) -> list[Dict[str, Any]]:
        """Call the vehicle enumeration endpoint."""

        params = {
            "apptimezone": "120",
            "appDateTime": str(int(dt_util.utcnow().timestamp() * 1000)),
        }
        url = f"{region.api_base}/eadrax-vcs/v4/vehicles"

        payload = await self._async_request(url, headers, params)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        raise UpdateFailed("Vehicle list payload malformed")

    async def _async_get_vehicle_profile(
        self,
        region: RegionConfig,
        headers: Dict[str, str],
        vin: str,
    ) -> Dict[str, Any]:
        """Call the vehicle profile endpoint and return JSON."""

        url = f"{region.api_base}/eadrax-vcs/v5/vehicle-data/profile"
        augmented_headers = {**headers, "bmw-vin": vin}
        payload = await self._async_request(url, augmented_headers)
        if isinstance(payload, dict):
            return payload
        raise UpdateFailed("Vehicle profile payload malformed")

    async def _async_request(
        self,
        url: str,
        headers: Dict[str, str],
        params: Dict[str, str] | None = None,
    ) -> Any:
        """Perform an HTTP GET and return parsed JSON."""

        try:
            async with async_timeout.timeout(_TIMEOUT):
                async with self._session.get(
                    url,
                    headers=headers,
                    params=params,
                ) as response:
                    if self._debug_enabled:
                        LOGGER.debug(
                            "VehicleService[%s]: GET %s status=%s",
                            self._entry.entry_id,
                            url,
                            response.status,
                        )
                    if response.status == 401:
                        raise ConfigEntryAuthFailed("Unauthorized")
                    if response.status >= 500:
                        raise ConfigEntryNotReady(f"Server error: {response.status}")
                    if response.status >= 400:
                        text = await response.text()
                        raise UpdateFailed(f"HTTP {response.status}: {text}")

                    if response.content_type == "application/json":
                        payload = await response.json()
                        if self._debug_enabled:
                            if isinstance(payload, dict):
                                detail = list(payload.keys())
                            elif isinstance(payload, list):
                                detail = f"list(len={len(payload)})"
                            else:
                                detail = type(payload).__name__
                            LOGGER.debug(
                                "VehicleService[%s]: response payload detail=%s",
                                self._entry.entry_id,
                                detail,
                            )
                        return payload
                    text = await response.text()
                    raise UpdateFailed("Unexpected response type")
        except ConfigEntryAuthFailed:
            raise
        except ConfigEntryNotReady:
            raise
        except asyncio.TimeoutError as err:
            raise ConfigEntryNotReady("Vehicle request timed out") from err
        except ClientError as err:
            raise UpdateFailed(str(err)) from err
        finally:
            if self._debug_enabled:
                LOGGER.debug(
                    "VehicleService[%s]: completed request to %s",
                    self._entry.entry_id,
                    url,
                )


def _build_headers(
    token: str,
    region: RegionConfig,
    x_user_agent: str,
    X_user_agent: str,
) -> Dict[str, str]:
    """Return the default header set for vehicle requests."""

    brand = "bmw"
    region_code = region.key

    return {
        "Authorization": f"Bearer {token}",
        "accept": "application/json",
        "accept-language": "en",
        "x-raw-locale": "en-US",
        "user-agent": "Dart/3.3 (dart:io)",
        "x-user-agent": x_user_agent,
        "X-User-Agent": X_user_agent,
        "bmw-units-preferences": "d=KM;v=L;p=B;ec=KWH100KM;fc=L100KM;em=GKM;",
        "24-hour-format": "true",
    }


def _generate_mobile_agent(region: str | None) -> str:
    """Create a pseudo-random mobile agent string."""

    region_code = region or "row"
    salt = random.randint(100000, 999999)
    return f"android(AP2A.{salt});bmw;{_APP_VERSION};{region_code}"


def _extract_vin(data: Dict[str, Any]) -> str | None:
    """Extract VIN from a payload with flexible casing."""

    for key in ("VIN", "vin", "Vin"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _as_str(value: Any) -> str | None:
    """Return the value as a stripped string if applicable."""

    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


class VehicleCoordinator(DataUpdateCoordinator[dict[str, VehicleSummary]]):
    """Coordinator for vehicle summaries."""

    def __init__(
        self,
        hass: HomeAssistant,
        service: VehicleService,
    ) -> None:
        self._service = service
        super().__init__(
            hass,
            LOGGER,
            name="Cardata Legacyline Vehicle Coordinator",
            update_method=self._service.async_fetch,
            update_interval=None,
        )
