"""Binary sensor platform for RainSoft integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RainSoftDevice
from .const import BASE_URL, DOMAIN
from .coordinator import RainSoftCoordinator, RainSoftRuntimeData


@dataclass(frozen=True, kw_only=True)
class RainSoftBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a RainSoft binary sensor."""

    value_fn: Callable[[RainSoftDevice], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[RainSoftBinarySensorEntityDescription, ...] = (
    RainSoftBinarySensorEntityDescription(
        key="low_salt",
        translation_key="low_salt",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:shaker-outline",
        value_fn=lambda d: (
            d.status_name.lower() == "low salt" if d.status_name else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RainSoft binary sensors from a config entry."""
    runtime_data: RainSoftRuntimeData = entry.runtime_data

    entities: list[RainSoftBinarySensor] = []
    for coordinator in runtime_data.coordinators.values():
        for description in BINARY_SENSOR_DESCRIPTIONS:
            entities.append(RainSoftBinarySensor(coordinator, description))

    async_add_entities(entities)


class RainSoftBinarySensor(
    CoordinatorEntity[RainSoftCoordinator], BinarySensorEntity
):
    """A RainSoft binary sensor entity."""

    entity_description: RainSoftBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainSoftCoordinator,
        description: RainSoftBinarySensorEntityDescription,
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
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
