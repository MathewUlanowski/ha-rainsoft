"""DataUpdateCoordinator for RainSoft devices."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    AuthenticationError,
    CannotConnectError,
    RainSoftApiClient,
    RainSoftDevice,
    RainSoftLocation,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class RainSoftRuntimeData:
    """Runtime data stored on the config entry."""

    client: RainSoftApiClient
    coordinators: dict[int, RainSoftCoordinator]


class RainSoftCoordinator(DataUpdateCoordinator[RainSoftDevice]):
    """Coordinator for a single RainSoft device."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: RainSoftApiClient,
        device: RainSoftDevice,
        location: RainSoftLocation,
        scan_interval_minutes: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        self.client = client
        self.device_id = device.device_id
        self.location = location

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device.device_id}",
            update_interval=timedelta(minutes=scan_interval_minutes),
        )

    async def _async_update_data(self) -> RainSoftDevice:
        """Fetch device data from the API."""
        try:
            locations = await self.client.get_locations()
            for loc in locations:
                for dev in loc.devices:
                    if dev.device_id == self.device_id:
                        return dev

            raise UpdateFailed(f"Device {self.device_id} not found in API response")
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except CannotConnectError as err:
            raise UpdateFailed(f"Error communicating with RainSoft API: {err}") from err
