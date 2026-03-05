"""The RainSoft integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import RainSoftApiClient
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .coordinator import RainSoftCoordinator, RainSoftRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RainSoft from a config entry."""
    client = RainSoftApiClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
    )

    # Discover locations and devices (handles login/logout internally)
    locations = await client.get_locations()

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    # Create one coordinator per device across all locations
    coordinators: dict[int, RainSoftCoordinator] = {}
    for location in locations:
        for device in location.devices:
            coordinator = RainSoftCoordinator(
                hass, client, device, location, scan_interval
            )
            await coordinator.async_config_entry_first_refresh()
            coordinators[device.device_id] = coordinator

    entry.runtime_data = RainSoftRuntimeData(
        client=client, coordinators=coordinators
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Re-create coordinators when options change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        runtime_data: RainSoftRuntimeData = entry.runtime_data
        await runtime_data.client.close()

    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update by reloading the integration."""
    await hass.config_entries.async_reload(entry.entry_id)
