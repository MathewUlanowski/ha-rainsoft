"""Tests for the RainSoft coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.rainsoft.api import (
    AuthenticationError,
    CannotConnectError,
    RainSoftDevice,
    RainSoftLocation,
)
from custom_components.rainsoft.coordinator import RainSoftCoordinator

from .conftest import MOCK_DEVICE_ID


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_device, mock_location):
    """Create a coordinator with a mock client."""
    client = AsyncMock()
    client.get_locations = AsyncMock(return_value=[mock_location])
    coord = RainSoftCoordinator(
        hass, client, mock_device, mock_location, scan_interval_minutes=30
    )
    return coord


class TestCoordinator:
    """Tests for RainSoftCoordinator."""

    async def test_update_returns_device(self, coordinator, mock_device):
        result = await coordinator._async_update_data()
        assert result.device_id == MOCK_DEVICE_ID
        assert result.salt_lbs == mock_device.salt_lbs

    async def test_update_device_not_found(self, coordinator):
        empty_location = RainSoftLocation(
            location_id=1, name="Home", devices=[]
        )
        coordinator.client.get_locations.return_value = [empty_location]

        with pytest.raises(UpdateFailed, match="not found"):
            await coordinator._async_update_data()

    async def test_update_auth_error(self, coordinator):
        coordinator.client.get_locations.side_effect = AuthenticationError("expired")

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    async def test_update_connection_error(self, coordinator):
        coordinator.client.get_locations.side_effect = CannotConnectError("DNS timeout")

        with pytest.raises(UpdateFailed, match="Error communicating"):
            await coordinator._async_update_data()

    async def test_update_finds_correct_device(self, coordinator):
        other_device = RainSoftDevice(device_id=999, name="Other")
        target_device = RainSoftDevice(device_id=MOCK_DEVICE_ID, name="Target", salt_lbs=55)
        location = RainSoftLocation(
            location_id=1, name="Home", devices=[other_device, target_device]
        )
        coordinator.client.get_locations.return_value = [location]

        result = await coordinator._async_update_data()
        assert result.device_id == MOCK_DEVICE_ID
        assert result.name == "Target"
