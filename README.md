# RainSoft Water Softener Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Monitor your RainSoft water softener through the [RainSoft Remind portal](https://remind.rainsoft.com) in Home Assistant.

> **Note:** This is an unofficial community integration. It is not affiliated with or endorsed by RainSoft / EcoWater Systems.

## Features

- Auto-discovers all locations and devices on your RainSoft Remind account
- 8 sensor entities per device (salt levels, capacity, regeneration, status)
- 1 binary sensor entity (low salt alert)
- 1 switch entity (vacation mode toggle)
- Configurable polling interval (default: 30 minutes)
- Uses the official RainSoft Remind mobile app API (no web scraping)

## Prerequisites

You need an active account on the [RainSoft Remind portal](https://remind.rainsoft.com) with at least one connected device (e.g. EC5 water softener).

## Installation

### Via HACS (Recommended)

1. Open **HACS** > **Integrations** > three-dot menu > **Custom Repositories**
2. Add `https://github.com/MathewUlanowski/ha-rainsoft` with category **Integration**
3. Search for **RainSoft** and click **Install**
4. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/rainsoft/` folder into your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **RainSoft**
3. Enter your RainSoft Remind portal email and password
4. All locations and devices on your account are discovered automatically

### Options

After setup, click **Configure** on the integration to adjust:

| Option | Default | Description |
|--------|---------|-------------|
| Polling interval | 30 min | How often to fetch data (5-1440 minutes) |

## Entities

### Sensors (per device)

| Entity | Unit | Description |
|--------|------|-------------|
| Salt Remaining | lb | Current salt level in the brine tank |
| Max Salt Capacity | lb | Maximum salt capacity |
| Capacity Remaining | grains | Remaining water softening capacity |
| Status | | Device status (e.g. "OK", "Low Salt") |
| Next Regeneration | timestamp | Next scheduled regeneration time |
| Install Date | timestamp | When the device was installed |
| Unit Size | | System size designation |
| Resin Type | | Type of resin installed |

### Binary Sensors (per device)

| Entity | On = | Description |
|--------|------|-------------|
| Low Salt | Salt level is low | Triggers when the API reports "Low Salt" status |

### Switches (per device)

| Entity | Description |
|--------|-------------|
| Vacation Mode | Toggle vacation mode on/off via the RainSoft API |

## How It Works

```mermaid
sequenceDiagram
    participant HA as Home Assistant
    participant API as RainSoft API Client
    participant RS as remind.rainsoft.com

    loop Every 30 minutes (login-fetch-logout)
        API->>RS: POST /login (credentials)
        RS-->>API: { authentication_token }
        API->>RS: GET /customer
        RS-->>API: { id: customer_id }
        API->>RS: GET /locations/{customer_id}
        RS-->>API: JSON (locations + devices)
        API->>RS: DELETE /logout (token)
        RS-->>API: 200 OK
        API-->>HA: Update sensor entities
    end
```

This integration uses the same JSON API as the RainSoft Remind mobile app. Each poll cycle follows a **login-fetch-logout** pattern — the auth token is created, used, and immediately invalidated so no tokens linger between intervals.

- **Auto-discovery** of customer ID, locations, and devices
- **Login-fetch-logout** pattern eliminates token expiry concerns
- **Multiple devices** supported with independent polling coordinators per device

## Troubleshooting

### "Invalid email or password"
Verify your credentials work at [remind.rainsoft.com](https://remind.rainsoft.com) or in the RainSoft Remind mobile app.

### "No RainSoft devices found"
Ensure your account has at least one device registered in the Remind portal.

### Entities showing "Unavailable"
The integration may temporarily lose connection to the API. It will automatically retry at the next polling interval. Check your HA logs:

```
Logger: custom_components.rainsoft
```

## Privacy & Security

- Your credentials are stored encrypted in Home Assistant's configuration store
- Credentials are only sent to `remind.rainsoft.com` (the official RainSoft portal)
- No data is sent to any third-party services

## Architecture

For a deep dive into the API, data model, auth flow, and design decisions, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Contributing

Contributions are welcome! Please open an issue or pull request on [GitHub](https://github.com/MathewUlanowski/ha-rainsoft).

## License

This project is licensed under the MIT License.
