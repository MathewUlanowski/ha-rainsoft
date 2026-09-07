"""Tests for RainSoft config-entry setup lifecycle handling."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import custom_components.rainsoft as rainsoft
from custom_components.rainsoft.api import AuthenticationError, CannotConnectError
from custom_components.rainsoft.const import CONF_EMAIL, CONF_PASSWORD


class _ConfigEntryAuthFailed(Exception):
    """Test stand-in for Home Assistant's ConfigEntryAuthFailed."""


class _ConfigEntryNotReady(Exception):
    """Test stand-in for Home Assistant's ConfigEntryNotReady."""


def _entry() -> MagicMock:
    entry = MagicMock()
    entry.data = {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "testpassword",
    }
    entry.options = {}
    return entry


def _hass() -> MagicMock:
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    return hass


@pytest.mark.asyncio
async def test_setup_retries_when_cloud_is_unavailable(monkeypatch):
    """A temporary RainSoft outage should ask Home Assistant to retry setup."""
    client = MagicMock()
    client.get_locations = AsyncMock(
        side_effect=CannotConnectError("Login returned HTTP 503")
    )
    client.close = AsyncMock()

    monkeypatch.setattr(rainsoft, "RainSoftApiClient", MagicMock(return_value=client))
    monkeypatch.setattr(rainsoft, "ConfigEntryNotReady", _ConfigEntryNotReady)

    with pytest.raises(_ConfigEntryNotReady, match="RainSoft cloud service unavailable"):
        await rainsoft.async_setup_entry(_hass(), _entry())

    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_starts_reauth_for_authentication_failure(monkeypatch):
    """Invalid credentials should trigger Home Assistant reauthentication."""
    client = MagicMock()
    client.get_locations = AsyncMock(side_effect=AuthenticationError("Invalid email or password"))
    client.close = AsyncMock()

    monkeypatch.setattr(rainsoft, "RainSoftApiClient", MagicMock(return_value=client))
    monkeypatch.setattr(rainsoft, "ConfigEntryAuthFailed", _ConfigEntryAuthFailed)

    with pytest.raises(_ConfigEntryAuthFailed, match="RainSoft authentication failed"):
        await rainsoft.async_setup_entry(_hass(), _entry())

    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_closes_client_when_initial_refresh_fails(monkeypatch):
    """Setup failures after discovery should still release the API client."""
    client = MagicMock()
    device = SimpleNamespace(device_id=123)
    location = SimpleNamespace(devices=[device])
    client.get_locations = AsyncMock(return_value=[location])
    client.close = AsyncMock()

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=_ConfigEntryNotReady("first refresh failed")
    )

    monkeypatch.setattr(rainsoft, "RainSoftApiClient", MagicMock(return_value=client))
    monkeypatch.setattr(rainsoft, "RainSoftCoordinator", MagicMock(return_value=coordinator))

    with pytest.raises(_ConfigEntryNotReady, match="first refresh failed"):
        await rainsoft.async_setup_entry(_hass(), _entry())

    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_successful_setup_keeps_client_for_runtime(monkeypatch):
    """A successful setup should keep the client open for coordinators."""
    client = MagicMock()
    device = SimpleNamespace(device_id=123)
    location = SimpleNamespace(devices=[device])
    client.get_locations = AsyncMock(return_value=[location])
    client.close = AsyncMock()

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    monkeypatch.setattr(rainsoft, "RainSoftApiClient", MagicMock(return_value=client))
    monkeypatch.setattr(rainsoft, "RainSoftCoordinator", MagicMock(return_value=coordinator))

    entry = _entry()
    hass = _hass()

    assert await rainsoft.async_setup_entry(hass, entry) is True

    client.close.assert_not_awaited()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()
    entry.async_on_unload.assert_called_once()
