"""Tests for the RainSoft config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.rainsoft.api import AuthenticationError, CannotConnectError
from custom_components.rainsoft.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

from .conftest import MOCK_EMAIL, MOCK_PASSWORD


@pytest.fixture
def mock_get_locations(mock_location):
    """Patch RainSoftApiClient for config flow tests."""
    with patch(
        "custom_components.rainsoft.config_flow.RainSoftApiClient",
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_locations = AsyncMock(return_value=[mock_location])
        client.validate_credentials = AsyncMock(return_value=True)
        client.close = AsyncMock()
        yield client


class TestUserFlow:
    """Tests for the user setup flow."""

    async def test_successful_setup(self, hass: HomeAssistant, mock_get_locations):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == f"RainSoft ({MOCK_EMAIL})"
        assert result["data"][CONF_EMAIL] == MOCK_EMAIL

    async def test_invalid_auth(self, hass: HomeAssistant, mock_get_locations):
        mock_get_locations.get_locations.side_effect = AuthenticationError("bad creds")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: "wrong"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_cannot_connect(self, hass: HomeAssistant, mock_get_locations):
        mock_get_locations.get_locations.side_effect = CannotConnectError("timeout")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_no_devices(self, hass: HomeAssistant, mock_get_locations):
        mock_get_locations.get_locations.return_value = [
            type(mock_get_locations.get_locations.return_value[0])(
                location_id=1, name="Home", devices=[]
            )
        ]
        # Return a location with no devices
        from custom_components.rainsoft.api import RainSoftLocation

        mock_get_locations.get_locations.return_value = [
            RainSoftLocation(location_id=1, name="Home", devices=[])
        ]

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "no_devices"}

    async def test_unknown_error(self, hass: HomeAssistant, mock_get_locations):
        mock_get_locations.get_locations.side_effect = RuntimeError("surprise")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}

    async def test_duplicate_entry(self, hass: HomeAssistant, mock_get_locations, mock_config_entry):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
