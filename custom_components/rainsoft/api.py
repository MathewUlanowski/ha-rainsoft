"""RainSoft Remind API client.

Uses the mobile app's JSON API at /api/remindapp/v2/.
Caches the auth token for up to 24 hours and re-authenticates on 401 or expiry.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import aiohttp

from .const import (
    API_CUSTOMER,
    API_DEVICE,
    API_DEVICE_SETTINGS,
    API_LOCATIONS,
    API_LOGIN,
    API_LOGOUT,
    AUTH_HEADER,
    BASE_URL,
)

TOKEN_MAX_AGE = timedelta(hours=24)

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when login fails."""


class CannotConnectError(Exception):
    """Raised when the portal is unreachable."""


@dataclass
class RainSoftDevice:
    """A single RainSoft device from the API."""

    device_id: int
    name: str
    model: str | None = None
    serial_number: int | None = None
    unit_size: str | None = None
    resin_type: str | None = None
    status_code: str | None = None
    status_name: str | None = None
    salt_lbs: int | None = None
    max_salt: int | None = None
    capacity_remaining: int | None = None
    is_vacation_mode: bool | None = None
    regen_time: datetime | None = None
    install_date: datetime | None = None
    registered_at: datetime | None = None
    # Water usage
    daily_water_use: int | None = None
    water_28_day: int | None = None
    flow_since_last_regen: int | None = None
    lifetime_flow: int | None = None
    # Regeneration
    last_regen_date: datetime | None = None
    regens_28_day: int | None = None
    # Salt
    average_monthly_salt: int | None = None
    salt_28_day: int | None = None
    # Water quality / system
    hardness: int | None = None
    iron_level: float | None = None
    pressure: int | None = None
    drain_flow: float | None = None
    # Service
    months_since_service: int | None = None


@dataclass
class RainSoftLocation:
    """A location (home) containing devices."""

    location_id: int
    name: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zipcode: str | None = None
    devices: list[RainSoftDevice] = field(default_factory=list)


class RainSoftApiClient:
    """Client for the RainSoft Remind JSON API.

    Caches the auth token for up to 24 hours. If a request receives a 401
    the token is discarded and a fresh login is attempted once before failing.
    """

    def __init__(
        self,
        email: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._session = session
        self._owns_session = session is None
        self._customer_id: int | None = None
        self._token: str | None = None
        self._token_acquired: datetime | None = None
        self._request_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return or create the HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Logout any cached token and close the session if we own it."""
        if self._token and self._session and not self._session.closed:
            await self._logout(self._session, self._token)
            self._token = None
            self._token_acquired = None
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _login(self, session: aiohttp.ClientSession) -> str:
        """Authenticate and return a fresh token."""
        url = f"{BASE_URL}{API_LOGIN}"

        try:
            async with session.post(
                url,
                data={"email": self._email, "password": self._password},
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (400, 401):
                    raise AuthenticationError("Invalid email or password")
                if resp.status != 200:
                    raise CannotConnectError(f"Login returned HTTP {resp.status}")

                data = await resp.json()
                token = data.get("authentication_token")
                if not token:
                    raise AuthenticationError("No authentication_token in response")

                _LOGGER.debug("Authenticated successfully")
                return token

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(f"Cannot connect to RainSoft API: {err}") from err

    async def _logout(self, session: aiohttp.ClientSession, token: str) -> None:
        """Invalidate the auth token."""
        url = f"{BASE_URL}{API_LOGOUT}"

        try:
            async with session.delete(
                url,
                data={"authorization_token": token},
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                _LOGGER.debug("Logged out (HTTP %s)", resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            _LOGGER.debug("Logout request failed, token may linger")

    def _invalidate_token(self) -> None:
        """Discard the cached token."""
        self._token = None
        self._token_acquired = None

    def _token_is_valid(self) -> bool:
        """Return True if we have a cached token that hasn't expired."""
        if self._token is None or self._token_acquired is None:
            return False
        return datetime.now(timezone.utc) - self._token_acquired < TOKEN_MAX_AGE

    async def _ensure_token(self, session: aiohttp.ClientSession) -> str:
        """Return a valid cached token, or login to get a fresh one."""
        if self._token_is_valid():
            return self._token  # type: ignore[return-value]
        self._token = await self._login(session)
        self._token_acquired = datetime.now(timezone.utc)
        return self._token

    async def _api_get(self, session: aiohttp.ClientSession, path: str) -> dict:
        """Authenticated GET with automatic retry on 401."""
        url = f"{BASE_URL}{path}"

        for attempt in range(2):
            token = await self._ensure_token(session)
            try:
                async with session.get(
                    url,
                    headers={
                        AUTH_HEADER: token,
                        "Accept": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 401:
                        _LOGGER.debug("Token rejected (attempt %d), re-authenticating", attempt + 1)
                        self._invalidate_token()
                        if attempt == 0:
                            continue
                        raise AuthenticationError("Token rejected after re-login")
                    resp.raise_for_status()
                    return await resp.json()

            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                raise CannotConnectError(f"API request failed: {err}") from err

        raise CannotConnectError("Unexpected: exhausted retry attempts")

    async def _api_post_form(
        self,
        session: aiohttp.ClientSession,
        path: str,
        form_data: dict,
    ) -> dict:
        """Authenticated form-encoded POST with automatic retry on 401."""
        url = f"{BASE_URL}{path}"

        for attempt in range(2):
            token = await self._ensure_token(session)
            try:
                async with session.post(
                    url,
                    data=form_data,
                    headers={
                        AUTH_HEADER: token,
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 401:
                        _LOGGER.debug("Token rejected (attempt %d), re-authenticating", attempt + 1)
                        self._invalidate_token()
                        if attempt == 0:
                            continue
                        raise AuthenticationError("Token rejected after re-login")
                    resp.raise_for_status()
                    return await resp.json()

            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                raise CannotConnectError(f"API request failed: {err}") from err

        raise CannotConnectError("Unexpected: exhausted retry attempts")

    async def validate_credentials(self) -> bool:
        """Test login/logout cycle. Used by config flow."""
        async with self._request_lock:
            session = await self._get_session()
            token = await self._login(session)
            await self._logout(session, token)
            return True

    async def get_locations(self) -> list[RainSoftLocation]:
        """Fetch customer + locations + per-device details using cached token."""
        async with self._request_lock:
            session = await self._get_session()

            # Get customer ID if we don't have it cached
            if self._customer_id is None:
                data = await self._api_get(session, API_CUSTOMER)
                cid = data.get("id")
                if not cid:
                    raise CannotConnectError("No customer ID in profile response")
                self._customer_id = int(cid)

            # Get locations + devices (basic info)
            path = API_LOCATIONS.format(customer_id=self._customer_id)
            data = await self._api_get(session, path)

            # Enrich each device with detailed data from /device/{id}
            for loc_data in data.get("locationListData", []):
                for dev_data in loc_data.get("devices", []):
                    device_id = dev_data.get("id")
                    if device_id:
                        try:
                            detail_path = API_DEVICE.format(device_id=device_id)
                            detail = await self._api_get(session, detail_path)
                            # Merge detail fields into device data (detail wins)
                            dev_data.update(detail)
                        except (CannotConnectError, AuthenticationError):
                            _LOGGER.warning("Failed to fetch details for device %s", device_id)

            return self._parse_locations(data)

    async def set_vacation_mode(self, device_id: int, *, enabled: bool) -> None:
        """Toggle vacation mode on a device using cached token."""
        import json as json_mod

        async with self._request_lock:
            session = await self._get_session()
            path = API_DEVICE_SETTINGS.format(device_id=device_id)
            setting_changes = json_mod.dumps(
                [
                    {
                        "vacation_mode": "1" if enabled else "0",
                        "set_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                    }
                ]
            )
            await self._api_post_form(
                session,
                path,
                {"settingChanges": setting_changes},
            )

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        """Parse an ISO datetime string from the API as UTC."""
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None

    @classmethod
    def _parse_locations(cls, data: dict) -> list[RainSoftLocation]:
        """Parse the locations API response."""
        locations: list[RainSoftLocation] = []

        for loc_data in data.get("locationListData", []):
            devices: list[RainSoftDevice] = []

            for dev_data in loc_data.get("devices", []):
                devices.append(
                    RainSoftDevice(
                        device_id=dev_data["id"],
                        name=dev_data.get("name", ""),
                        model=dev_data.get("model"),
                        serial_number=dev_data.get("serialNumber"),
                        unit_size=dev_data.get("unitSizeName"),
                        resin_type=dev_data.get("resinTypeName"),
                        status_code=dev_data.get("systemStatusCode"),
                        status_name=dev_data.get("systemStatusName"),
                        salt_lbs=dev_data.get("saltLbs"),
                        max_salt=dev_data.get("maxSalt"),
                        capacity_remaining=dev_data.get("capacityRemaining"),
                        is_vacation_mode=dev_data.get("isVacationMode"),
                        regen_time=cls._parse_datetime(dev_data.get("regenTime")),
                        install_date=cls._parse_datetime(dev_data.get("installDate")),
                        registered_at=cls._parse_datetime(dev_data.get("registeredAt")),
                        daily_water_use=dev_data.get("dailyWaterUse"),
                        water_28_day=dev_data.get("water28Day"),
                        flow_since_last_regen=dev_data.get("flowSinceLastRegen"),
                        lifetime_flow=dev_data.get("lifeTimeFlow"),
                        last_regen_date=cls._parse_datetime(dev_data.get("lastRegenDate")),
                        regens_28_day=dev_data.get("regens28Day"),
                        average_monthly_salt=dev_data.get("averageMonthlySalt"),
                        salt_28_day=dev_data.get("salt28Day"),
                        hardness=dev_data.get("hardness"),
                        iron_level=dev_data.get("ironLevel"),
                        pressure=dev_data.get("pressure"),
                        drain_flow=dev_data.get("drainFlow"),
                        months_since_service=dev_data.get("monthsSinceService"),
                    )
                )

            addr_parts = [
                loc_data.get("addR_1", ""),
                loc_data.get("addR_2", ""),
            ]
            address = ", ".join(p.strip() for p in addr_parts if p and p.strip()) or None

            locations.append(
                RainSoftLocation(
                    location_id=loc_data["id"],
                    name=loc_data.get("name", ""),
                    address=address,
                    city=loc_data.get("city"),
                    state=loc_data.get("state"),
                    zipcode=loc_data.get("zipcode"),
                    devices=devices,
                )
            )

        return locations
