"""RainSoft Remind API client.

Uses the mobile app's JSON API at /api/remindapp/v2/.
Each data fetch authenticates, retrieves data, then immediately logs out
so no tokens are left lingering.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp

from .const import (
    API_CUSTOMER,
    API_DEVICE_SETTINGS,
    API_LOCATIONS,
    API_LOGIN,
    API_LOGOUT,
    AUTH_HEADER,
    BASE_URL,
)

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

    Uses a login-fetch-logout pattern: each data request authenticates,
    retrieves the needed data, then immediately invalidates the token.
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
        self._request_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return or create the HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
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
                    raise CannotConnectError(
                        f"Login returned HTTP {resp.status}"
                    )

                data = await resp.json()
                token = data.get("authentication_token")
                if not token:
                    raise AuthenticationError(
                        "No authentication_token in response"
                    )

                _LOGGER.debug("Authenticated successfully")
                return token

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to RainSoft API: {err}"
            ) from err

    async def _logout(
        self, session: aiohttp.ClientSession, token: str
    ) -> None:
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

    async def _api_get(
        self, session: aiohttp.ClientSession, token: str, path: str
    ) -> dict:
        """Make an authenticated GET request."""
        url = f"{BASE_URL}{path}"

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
                    raise AuthenticationError("Token rejected")
                resp.raise_for_status()
                return await resp.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"API request failed: {err}"
            ) from err

    async def _api_post_form(
        self,
        session: aiohttp.ClientSession,
        token: str,
        path: str,
        form_data: dict,
    ) -> dict:
        """Make an authenticated form-encoded POST request."""
        url = f"{BASE_URL}{path}"

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
                    raise AuthenticationError("Token rejected")
                resp.raise_for_status()
                return await resp.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"API request failed: {err}"
            ) from err

    async def validate_credentials(self) -> bool:
        """Test login/logout cycle. Used by config flow."""
        async with self._request_lock:
            session = await self._get_session()
            token = await self._login(session)
            await self._logout(session, token)
            return True

    async def get_locations(self) -> list[RainSoftLocation]:
        """Login, fetch customer + locations, logout."""
        async with self._request_lock:
            session = await self._get_session()
            token = await self._login(session)

            try:
                # Get customer ID if we don't have it cached
                if self._customer_id is None:
                    data = await self._api_get(session, token, API_CUSTOMER)
                    cid = data.get("id")
                    if not cid:
                        raise CannotConnectError(
                            "No customer ID in profile response"
                        )
                    self._customer_id = int(cid)

                # Get locations + devices
                path = API_LOCATIONS.format(customer_id=self._customer_id)
                data = await self._api_get(session, token, path)
                return self._parse_locations(data)

            finally:
                await self._logout(session, token)

    async def set_vacation_mode(self, device_id: int, *, enabled: bool) -> None:
        """Login, toggle vacation mode on a device, logout."""
        import json as json_mod

        async with self._request_lock:
            session = await self._get_session()
            token = await self._login(session)

            try:
                path = API_DEVICE_SETTINGS.format(device_id=device_id)
                setting_changes = json_mod.dumps([
                    {
                        "vacation_mode": "1" if enabled else "0",
                        "set_at": datetime.utcnow().strftime(
                            "%Y-%m-%dT%H:%M:%S.%f"
                        )[:-3] + "Z",
                    }
                ])
                await self._api_post_form(
                    session, token, path,
                    {"settingChanges": setting_changes},
                )
            finally:
                await self._logout(session, token)

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        """Parse an ISO datetime string from the API."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
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
                        regen_time=cls._parse_datetime(
                            dev_data.get("regenTime")
                        ),
                        install_date=cls._parse_datetime(
                            dev_data.get("installDate")
                        ),
                        registered_at=cls._parse_datetime(
                            dev_data.get("registeredAt")
                        ),
                        daily_water_use=dev_data.get("dailyWaterUse"),
                        water_28_day=dev_data.get("water28Day"),
                        flow_since_last_regen=dev_data.get("flowSinceLastRegen"),
                        lifetime_flow=dev_data.get("lifeTimeFlow"),
                        last_regen_date=cls._parse_datetime(
                            dev_data.get("lastRegenDate")
                        ),
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
