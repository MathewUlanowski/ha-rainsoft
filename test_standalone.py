"""Standalone test script for the RainSoft API client.

Run with:
  python test_standalone.py [email] [password]              # read-only fetch
  python test_standalone.py [email] [password] vacation on  # enable vacation mode
  python test_standalone.py [email] [password] vacation off # disable vacation mode

Requires: pip install aiohttp
"""

import asyncio
import importlib.util
import sys
import types
from dataclasses import asdict

# Bootstrap: load const.py and api.py without triggering HA imports via __init__.py
_const_spec = importlib.util.spec_from_file_location(
    "rainsoft_const", "custom_components/rainsoft/const.py"
)
_const = importlib.util.module_from_spec(_const_spec)
_const_spec.loader.exec_module(_const)

_pkg = types.ModuleType("custom_components.rainsoft")
_pkg.__path__ = ["custom_components/rainsoft"]
sys.modules["custom_components"] = types.ModuleType("custom_components")
sys.modules["custom_components.rainsoft"] = _pkg
sys.modules["custom_components.rainsoft.const"] = _const

_api_spec = importlib.util.spec_from_file_location(
    "custom_components.rainsoft.api",
    "custom_components/rainsoft/api.py",
)
_api = importlib.util.module_from_spec(_api_spec)
_api.__package__ = "custom_components.rainsoft"
sys.modules["custom_components.rainsoft.api"] = _api
_api_spec.loader.exec_module(_api)

RainSoftApiClient = _api.RainSoftApiClient


async def main() -> None:
    if len(sys.argv) >= 3:
        email = sys.argv[1]
        password = sys.argv[2]
    else:
        email = input("RainSoft Remind email: ").strip()
        password = input("Password: ").strip()

    # Check for vacation mode command
    vacation_cmd = None
    if len(sys.argv) >= 5 and sys.argv[3] == "vacation":
        vacation_cmd = sys.argv[4].lower()
        if vacation_cmd not in ("on", "off"):
            print("Usage: ... vacation [on|off]")
            return

    client = RainSoftApiClient(email=email, password=password)

    try:
        # Step 1: Validate credentials (login + logout)
        print("\n[1/3] Validating credentials...")
        await client.validate_credentials()
        print("  OK - Login/logout cycle successful")

        # Step 2: Fetch all data (login, fetch, logout)
        print("\n[2/3] Fetching locations and devices...")
        locations = await client.get_locations()

        if not locations:
            print("  No locations found!")
            return

        total_devices = sum(len(loc.devices) for loc in locations)
        print(f"  OK - Found {len(locations)} location(s), {total_devices} device(s)")
        print("  (Token was invalidated after fetch)")

        print("\n  Device details:")
        for loc in locations:
            print(f"\n  Location: {loc.name}")
            print(f"  Address: {loc.address}, {loc.city}, {loc.state} {loc.zipcode}")

            for dev in loc.devices:
                print(f"\n  {'='*56}")
                print(f"    {dev.name} ({dev.model})")
                print(f"  {'='*56}")

                for key, value in asdict(dev).items():
                    label = key.replace("_", " ").title()
                    if value is not None and value != "":
                        print(f"    {label:.<35} {value}")
                    else:
                        print(f"    {label:.<35} (empty)")

        # Step 3: Toggle vacation mode if requested
        if vacation_cmd is not None:
            all_devices = [d for loc in locations for d in loc.devices]
            enabled = vacation_cmd == "on"
            for dev in all_devices:
                print(f"\n[3/3] Setting vacation mode {'ON' if enabled else 'OFF'} for {dev.name} (ID: {dev.device_id})...")
                await client.set_vacation_mode(dev.device_id, enabled=enabled)
                print(f"  OK - Vacation mode {'enabled' if enabled else 'disabled'}")
                print("  (Token was invalidated after setting change)")

            # Re-fetch to confirm
            print("\n  Confirming change...")
            locations = await client.get_locations()
            for loc in locations:
                for dev in loc.devices:
                    status = "ON" if dev.is_vacation_mode else "OFF"
                    print(f"  {dev.name}: vacation_mode = {status}")
        else:
            print("\n[3/3] Skipped (no vacation command given)")

    except Exception as e:
        print(f"\n  ERROR: {type(e).__name__}: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
