"""Tests for RainSoft integration setup and unload."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant

from custom_components.rainsoft.const import DOMAIN
from custom_components.rainsoft.coordinator import RainSoftRuntimeData


class TestSetup:
    """Tests for integration setup."""

    async def test_setup_entry(self, hass: HomeAssistant, mock_config_entry, mock_api_client):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state.name == "LOADED"
        runtime_data: RainSoftRuntimeData = mock_config_entry.runtime_data
        assert len(runtime_data.coordinators) == 1

    async def test_unload_entry(self, hass: HomeAssistant, mock_config_entry, mock_api_client):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        assert result is True
        mock_api_client.close.assert_called_once()

    async def test_setup_creates_entities(self, hass: HomeAssistant, mock_config_entry, mock_api_client):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check that sensor entities were created
        state = hass.states.get("sensor.ec5_salt_remaining")
        assert state is not None
        assert state.state == "40"

        # Check binary sensor
        state = hass.states.get("binary_sensor.ec5_low_salt")
        assert state is not None

        # Check switch
        state = hass.states.get("switch.ec5_vacation_mode")
        assert state is not None
