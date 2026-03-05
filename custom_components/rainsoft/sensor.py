"""Sensor platform for RainSoft integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass, UnitOfPressure, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RainSoftDevice
from .const import BASE_URL, DOMAIN
from .coordinator import RainSoftCoordinator, RainSoftRuntimeData


@dataclass(frozen=True, kw_only=True)
class RainSoftSensorEntityDescription(SensorEntityDescription):
    """Describes a RainSoft sensor with a value extraction function."""

    value_fn: Callable[[RainSoftDevice], StateType | datetime | None]


SENSOR_DESCRIPTIONS: tuple[RainSoftSensorEntityDescription, ...] = (
    RainSoftSensorEntityDescription(
        key="salt_lbs",
        translation_key="salt_lbs",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.POUNDS,
        icon="mdi:shaker-outline",
        value_fn=lambda d: d.salt_lbs,
    ),
    RainSoftSensorEntityDescription(
        key="max_salt",
        translation_key="max_salt",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.POUNDS,
        icon="mdi:shaker",
        value_fn=lambda d: d.max_salt,
    ),
    RainSoftSensorEntityDescription(
        key="capacity_remaining",
        translation_key="capacity_remaining",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="grains",
        icon="mdi:gauge",
        value_fn=lambda d: d.capacity_remaining,
    ),
    RainSoftSensorEntityDescription(
        key="status",
        translation_key="status",
        icon="mdi:information-outline",
        value_fn=lambda d: d.status_name,
    ),
    RainSoftSensorEntityDescription(
        key="regen_time",
        translation_key="regen_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:recycle",
        value_fn=lambda d: d.regen_time,
    ),
    RainSoftSensorEntityDescription(
        key="install_date",
        translation_key="install_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar",
        value_fn=lambda d: d.install_date,
    ),
    RainSoftSensorEntityDescription(
        key="unit_size",
        translation_key="unit_size",
        icon="mdi:resize",
        value_fn=lambda d: d.unit_size,
    ),
    RainSoftSensorEntityDescription(
        key="resin_type",
        translation_key="resin_type",
        icon="mdi:flask-outline",
        value_fn=lambda d: d.resin_type,
    ),
    # Water usage
    RainSoftSensorEntityDescription(
        key="daily_water_use",
        translation_key="daily_water_use",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        icon="mdi:water",
        value_fn=lambda d: d.daily_water_use,
    ),
    RainSoftSensorEntityDescription(
        key="water_28_day",
        translation_key="water_28_day",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        icon="mdi:water-plus",
        value_fn=lambda d: d.water_28_day,
    ),
    RainSoftSensorEntityDescription(
        key="flow_since_last_regen",
        translation_key="flow_since_last_regen",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        icon="mdi:water-sync",
        value_fn=lambda d: d.flow_since_last_regen,
    ),
    RainSoftSensorEntityDescription(
        key="lifetime_flow",
        translation_key="lifetime_flow",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        icon="mdi:counter",
        value_fn=lambda d: d.lifetime_flow,
    ),
    # Regeneration
    RainSoftSensorEntityDescription(
        key="last_regen_date",
        translation_key="last_regen_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:history",
        value_fn=lambda d: d.last_regen_date,
    ),
    RainSoftSensorEntityDescription(
        key="regens_28_day",
        translation_key="regens_28_day",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:recycle",
        value_fn=lambda d: d.regens_28_day,
    ),
    # Salt
    RainSoftSensorEntityDescription(
        key="average_monthly_salt",
        translation_key="average_monthly_salt",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.POUNDS,
        icon="mdi:scale",
        value_fn=lambda d: d.average_monthly_salt,
    ),
    RainSoftSensorEntityDescription(
        key="salt_28_day",
        translation_key="salt_28_day",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.POUNDS,
        icon="mdi:shaker",
        value_fn=lambda d: d.salt_28_day,
    ),
    # Water quality / system
    RainSoftSensorEntityDescription(
        key="hardness",
        translation_key="hardness",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="gpg",
        icon="mdi:water-opacity",
        value_fn=lambda d: d.hardness,
    ),
    RainSoftSensorEntityDescription(
        key="iron_level",
        translation_key="iron_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ppm",
        icon="mdi:flask",
        value_fn=lambda d: d.iron_level,
    ),
    RainSoftSensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PSI,
        icon="mdi:gauge-low",
        value_fn=lambda d: d.pressure,
    ),
    RainSoftSensorEntityDescription(
        key="drain_flow",
        translation_key="drain_flow",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="gpm",
        icon="mdi:pipe-valve",
        value_fn=lambda d: d.drain_flow,
    ),
    # Service
    RainSoftSensorEntityDescription(
        key="months_since_service",
        translation_key="months_since_service",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="months",
        icon="mdi:wrench-clock",
        value_fn=lambda d: d.months_since_service,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RainSoft sensors from a config entry."""
    runtime_data: RainSoftRuntimeData = entry.runtime_data

    entities: list[RainSoftSensor] = []
    for coordinator in runtime_data.coordinators.values():
        for description in SENSOR_DESCRIPTIONS:
            entities.append(RainSoftSensor(coordinator, description))

    async_add_entities(entities)


class RainSoftSensor(CoordinatorEntity[RainSoftCoordinator], SensorEntity):
    """A RainSoft sensor entity."""

    entity_description: RainSoftSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainSoftCoordinator,
        description: RainSoftSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        device_id = coordinator.device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=coordinator.data.name if coordinator.data else f"RainSoft {device_id}",
            manufacturer="RainSoft",
            model=coordinator.data.model if coordinator.data else None,
            serial_number=(
                str(coordinator.data.serial_number) if coordinator.data and coordinator.data.serial_number else None
            ),
            configuration_url=f"{BASE_URL}",
        )

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the current sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
