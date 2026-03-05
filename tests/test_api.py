"""Tests for the RainSoft API client."""

from __future__ import annotations

from datetime import datetime, timezone

import aiohttp
import pytest

from custom_components.rainsoft.api import (
    AuthenticationError,
    CannotConnectError,
    RainSoftApiClient,
)

from .conftest import MOCK_EMAIL, MOCK_PASSWORD, MOCK_TOKEN, mock_response


class TestLogin:
    """Tests for the login flow."""

    async def test_login_success(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        mock_session.post.return_value = mock_response(200, {"authentication_token": MOCK_TOKEN})

        token = await client._login(mock_session)
        assert token == MOCK_TOKEN

    async def test_login_invalid_credentials(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        mock_session.post.return_value = mock_response(401)

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            await client._login(mock_session)

    async def test_login_server_error(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        mock_session.post.return_value = mock_response(500)

        with pytest.raises(CannotConnectError, match="HTTP 500"):
            await client._login(mock_session)

    async def test_login_no_token_in_response(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        mock_session.post.return_value = mock_response(200, {"other": "data"})

        with pytest.raises(AuthenticationError, match="No authentication_token"):
            await client._login(mock_session)

    async def test_login_network_error(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        mock_session.post.side_effect = aiohttp.ClientError("Connection refused")

        with pytest.raises(CannotConnectError, match="Cannot connect"):
            await client._login(mock_session)


class TestTokenManagement:
    """Tests for token caching and invalidation."""

    def test_token_not_valid_initially(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        assert not client._token_is_valid()

    def test_token_valid_after_set(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        client._token = MOCK_TOKEN
        client._token_acquired = datetime.now(timezone.utc)
        assert client._token_is_valid()

    def test_token_invalid_after_invalidation(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        client._token = MOCK_TOKEN
        client._token_acquired = datetime.now(timezone.utc)
        client._invalidate_token()
        assert not client._token_is_valid()


class TestApiGet:
    """Tests for authenticated API requests."""

    async def test_api_get_success(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        client._token = MOCK_TOKEN
        client._token_acquired = datetime.now(timezone.utc)

        mock_session.get.return_value = mock_response(200, {"key": "value"})
        result = await client._api_get(mock_session, "/api/test")
        assert result == {"key": "value"}

    async def test_api_get_401_retries(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        client._token = MOCK_TOKEN
        client._token_acquired = datetime.now(timezone.utc)

        # First call returns 401, login returns new token, second call succeeds
        resp_401 = mock_response(401)
        resp_401.raise_for_status = lambda: None  # 401 doesn't raise, handled by code
        resp_ok = mock_response(200, {"result": "ok"})
        mock_session.get.side_effect = [resp_401, resp_ok]
        mock_session.post.return_value = mock_response(200, {"authentication_token": "new-token"})

        result = await client._api_get(mock_session, "/api/test")
        assert result == {"result": "ok"}

    async def test_api_get_network_error(self, mock_session):
        client = RainSoftApiClient(MOCK_EMAIL, MOCK_PASSWORD, session=mock_session)
        client._token = MOCK_TOKEN
        client._token_acquired = datetime.now(timezone.utc)

        mock_session.get.side_effect = aiohttp.ClientError("timeout")

        with pytest.raises(CannotConnectError, match="API request failed"):
            await client._api_get(mock_session, "/api/test")


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
        assert RainSoftApiClient._parse_locations({}) == []

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

    def test_parse_device_fields(self):
        data = {
            "locationListData": [
                {
                    "id": 1,
                    "name": "Home",
                    "devices": [
                        {
                            "id": 100,
                            "name": "EC5",
                            "dailyWaterUse": 75,
                            "water28Day": 2100,
                            "lifeTimeFlow": 150000,
                            "hardness": 15,
                            "ironLevel": 0.5,
                            "pressure": 60,
                            "isVacationMode": False,
                            "regenTime": "2026-03-05T02:00:00",
                        }
                    ],
                }
            ]
        }
        result = RainSoftApiClient._parse_locations(data)
        dev = result[0].devices[0]
        assert dev.daily_water_use == 75
        assert dev.water_28_day == 2100
        assert dev.lifetime_flow == 150000
        assert dev.hardness == 15
        assert dev.iron_level == 0.5
        assert dev.pressure == 60
        assert dev.is_vacation_mode is False
        assert dev.regen_time == datetime(2026, 3, 5, 2, 0, tzinfo=timezone.utc)
