"""Sensors for Cardata Legacyline vehicles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_vehicle_coordinator
from .const import DOMAIN
from .vehicle_manager import VehicleCoordinator, VehicleSummary


@dataclass
class VehicleSensorDescription(SensorEntityDescription):
    """Describe a Cardata vehicle sensor."""

    value_fn: Callable[[VehicleSummary], Any] = lambda _: None


SENSOR_DESCRIPTIONS: tuple[VehicleSensorDescription, ...] = (
    VehicleSensorDescription(
        key="model",
        translation_key="model",
        icon="mdi:car-info",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda summary: summary.model,
    ),
    VehicleSensorDescription(
        key="brand",
        translation_key="brand",
        icon="mdi:car",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda summary: summary.brand,
    ),
    VehicleSensorDescription(
        key="drive_train",
        translation_key="drive_train",
        icon="mdi:engine",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda summary: summary.drive_train,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up vehicle sensors for a config entry."""

    coordinator = get_vehicle_coordinator(hass, entry.entry_id)
    known_vins: set[str] = set()

    @callback
    def _async_add_entities() -> None:
        data = coordinator.data or {}
        new_entities: list[CardataVehicleSensor] = []
        for vin in data:
            if vin in known_vins:
                continue
            known_vins.add(vin)
            for description in SENSOR_DESCRIPTIONS:
                new_entities.append(
                    CardataVehicleSensor(coordinator, entry, vin, description)
                )
        if new_entities:
            async_add_entities(new_entities)

    _async_add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_entities))


class CardataVehicleSensor(CoordinatorEntity[dict[str, VehicleSummary]], SensorEntity):
    """Sensor representing a piece of vehicle metadata."""

    def __init__(
        self,
        coordinator: VehicleCoordinator,
        entry: ConfigEntry,
        vin: str,
        description: VehicleSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._vin = vin
        self._attr_unique_id = f"{entry.entry_id}_{vin}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def _summary(self) -> VehicleSummary | None:
        return (self.coordinator.data or {}).get(self._vin)

    @property
    def native_value(self) -> Any:
        summary = self._summary
        if not summary:
            return None
        return self.entity_description.value_fn(summary)

    @property
    def device_info(self) -> DeviceInfo | None:
        summary = self._summary
        if not summary:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, summary.vin)},
            name=summary.device_name,
            manufacturer=summary.manufacturer,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        summary = self._summary
        if not summary:
            return None
        return {
            "vin": summary.vin,
            "vehicle_type": summary.app_vehicle_type,
        }
