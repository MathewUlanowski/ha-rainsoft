"""Fixtures for RainSoft integration tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.rainsoft.api import RainSoftDevice, RainSoftLocation
from custom_components.rainsoft.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

MOCK_EMAIL = "test@example.com"
MOCK_PASSWORD = "testpassword"
MOCK_TOKEN = "fake-auth-token-123"
MOCK_CUSTOMER_ID = 99
MOCK_DEVICE_ID = 146301


@pytest.fixture
def mock_device() -> RainSoftDevice:
    """Return a mock RainSoftDevice."""
    return RainSoftDevice(
        device_id=MOCK_DEVICE_ID,
        name="EC5",
        model="EC5",
        serial_number=123456,
        unit_size="1.0 cu ft",
        resin_type="Standard",
        status_code="OK",
        status_name="OK",
        salt_lbs=40,
        max_salt=80,
        capacity_remaining=15000,
        is_vacation_mode=False,
        regen_time=datetime(2026, 3, 5, 2, 0, tzinfo=timezone.utc),
        install_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        registered_at=datetime(2024, 1, 20, tzinfo=timezone.utc),
        daily_water_use=75,
        water_28_day=2100,
        flow_since_last_regen=500,
        lifetime_flow=150000,
        last_regen_date=datetime(2026, 3, 1, 2, 0, tzinfo=timezone.utc),
        regens_28_day=4,
        average_monthly_salt=10,
        salt_28_day=8,
        hardness=15,
        iron_level=0.5,
        pressure=60,
        drain_flow=2.5,
        months_since_service=6,
    )


@pytest.fixture
def mock_location(mock_device: RainSoftDevice) -> RainSoftLocation:
    """Return a mock RainSoftLocation."""
    return RainSoftLocation(
        location_id=1,
        name="Home",
        address="123 Main St",
        city="Springfield",
        state="IL",
        zipcode="62704",
        devices=[mock_device],
    )


@pytest.fixture
def mock_config_entry(hass):
    """Create a mock config entry."""
    from homeassistant.config_entries import ConfigEntry

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=MOCK_EMAIL,
        data={CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        source="user",
        unique_id=MOCK_EMAIL,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_api_client(mock_location: RainSoftLocation):
    """Patch RainSoftApiClient for integration tests."""
    with patch(
        "custom_components.rainsoft.RainSoftApiClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.validate_credentials = AsyncMock(return_value=True)
        client.get_locations = AsyncMock(return_value=[mock_location])
        client.set_vacation_mode = AsyncMock()
        client.close = AsyncMock()
        yield client
