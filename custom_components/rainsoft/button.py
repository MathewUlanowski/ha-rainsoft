"""Button platform for RainSoft integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BASE_URL, DOMAIN
from .coordinator import RainSoftCoordinator, RainSoftRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RainSoft buttons from a config entry."""
    runtime_data: RainSoftRuntimeData = entry.runtime_data

    entities: list[RainSoftRefreshButton] = []
    for coordinator in runtime_data.coordinators.values():
        entities.append(RainSoftRefreshButton(coordinator))

    async_add_entities(entities)


class RainSoftRefreshButton(CoordinatorEntity[RainSoftCoordinator], ButtonEntity):
    """Button to trigger an immediate data refresh."""

    _attr_has_entity_name = True
    entity_description = ButtonEntityDescription(
        key="refresh",
        translation_key="refresh",
        icon="mdi:refresh",
    )

    def __init__(self, coordinator: RainSoftCoordinator) -> None:
        super().__init__(coordinator)
        device_id = coordinator.device_id
        self._attr_unique_id = f"{device_id}_refresh"
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

    async def async_press(self) -> None:
        """Trigger an immediate coordinator refresh."""
        await self.coordinator.async_request_refresh()
