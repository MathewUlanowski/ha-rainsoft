"""Tests for the RainSoft API client."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.rainsoft.api import (
    AuthenticationError,
    CannotConnectError,
    RainSoftApiClient,
)

from .conftest import MOCK_EMAIL, MOCK_PASSWORD, MOCK_TOKEN


@pytest.fixture
def api_client():
    """Return a fresh API client."""
    return RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD)


def _mock_response(status=200, json_data=None):
    """Create a mock aiohttp response."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=status
        )
    # Support async context manager
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


class TestLogin:
    """Tests for the login flow."""

    async def test_login_success(self, api_client):
        login_resp = _mock_response(200, {"authentication_token": MOCK_TOKEN})

        with patch.object(aiohttp.ClientSession, "post", return_value=login_resp):
            session = await api_client._get_session()
            token = await api_client._login(session)

        assert token == MOCK_TOKEN

    async def test_login_invalid_credentials(self, api_client):
        login_resp = _mock_response(401)

        with patch.object(aiohttp.ClientSession, "post", return_value=login_resp):
            session = await api_client._get_session()
            with pytest.raises(AuthenticationError, match="Invalid email or password"):
                await api_client._login(session)

    async def test_login_server_error(self, api_client):
        login_resp = _mock_response(500)

        with patch.object(aiohttp.ClientSession, "post", return_value=login_resp):
            session = await api_client._get_session()
            with pytest.raises(CannotConnectError, match="HTTP 500"):
                await api_client._login(session)

    async def test_login_no_token_in_response(self, api_client):
        login_resp = _mock_response(200, {"some_other_field": "value"})

        with patch.object(aiohttp.ClientSession, "post", return_value=login_resp):
            session = await api_client._get_session()
            with pytest.raises(AuthenticationError, match="No authentication_token"):
                await api_client._login(session)

    async def test_login_network_error(self, api_client):
        with patch.object(
            aiohttp.ClientSession,
            "post",
            side_effect=aiohttp.ClientError("Connection refused"),
        ):
            session = await api_client._get_session()
            with pytest.raises(CannotConnectError, match="Cannot connect"):
                await api_client._login(session)


class TestTokenManagement:
    """Tests for token caching and invalidation."""

    def test_token_not_valid_initially(self, api_client):
        assert not api_client._token_is_valid()

    def test_token_valid_after_set(self, api_client):
        api_client._token = MOCK_TOKEN
        api_client._token_acquired = datetime.now(timezone.utc)
        assert api_client._token_is_valid()

    def test_token_invalid_after_invalidation(self, api_client):
        api_client._token = MOCK_TOKEN
        api_client._token_acquired = datetime.now(timezone.utc)
        api_client._invalidate_token()
        assert not api_client._token_is_valid()


class TestParseDatetime:
    """Tests for datetime parsing."""

    def test_parse_iso_datetime(self):
        result = RainSoftApiClient._parse_datetime("2026-03-04T12:30:00")
        assert result == datetime(2026, 3, 4, 12, 30, tzinfo=timezone.utc)

    def test_parse_datetime_with_tz(self):
        result = RainSoftApiClient._parse_datetime("2026-03-04T12:30:00+00:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_parse_none(self):
        assert RainSoftApiClient._parse_datetime(None) is None

    def test_parse_empty(self):
        assert RainSoftApiClient._parse_datetime("") is None

    def test_parse_invalid(self):
        assert RainSoftApiClient._parse_datetime("not-a-date") is None


class TestParseLocations:
    """Tests for location/device parsing."""

    def test_parse_empty(self):
        result = RainSoftApiClient._parse_locations({})
        assert result == []

    def test_parse_location_with_device(self):
        data = {
            "locationListData": [
                {
                    "id": 1,
                    "name": "Home",
                    "addR_1": "123 Main St",
                    "addR_2": "",
                    "city": "Springfield",
                    "state": "IL",
                    "zipcode": "62704",
                    "devices": [
                        {
                            "id": 100,
                            "name": "EC5",
                            "model": "EC5",
                            "saltLbs": 40,
                            "maxSalt": 80,
                            "systemStatusCode": "OK",
                            "systemStatusName": "OK",
                        }
                    ],
                }
            ]
        }
        result = RainSoftApiClient._parse_locations(data)
        assert len(result) == 1
        assert result[0].name == "Home"
        assert result[0].address == "123 Main St"
        assert len(result[0].devices) == 1
        assert result[0].devices[0].device_id == 100
        assert result[0].devices[0].salt_lbs == 40

    def test_parse_multiple_locations(self):
        data = {
            "locationListData": [
                {"id": 1, "name": "Home", "devices": [{"id": 100, "name": "EC5"}]},
                {"id": 2, "name": "Office", "devices": [{"id": 200, "name": "EC4"}]},
            ]
        }
        result = RainSoftApiClient._parse_locations(data)
        assert len(result) == 2
        assert result[0].devices[0].device_id == 100
        assert result[1].devices[0].device_id == 200
