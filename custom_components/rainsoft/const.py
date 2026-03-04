"""Constants for the RainSoft integration."""

DOMAIN = "rainsoft"
BASE_URL = "https://remind.rainsoft.com"
DEFAULT_SCAN_INTERVAL = 30  # minutes

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

# API paths
API_LOGIN = "/api/remindapp/v2/login"
API_LOGOUT = "/api/remindapp/v2/logout"
API_CUSTOMER = "/api/remindapp/v2/customer"
API_LOCATIONS = "/api/remindapp/v2/locations/{customer_id}"
API_DEVICE = "/api/remindapp/v2/device/{device_id}"
API_DEVICE_SETTINGS = "/api/remindapp/v2/device/{device_id}/setting_changes"

# Auth header
AUTH_HEADER = "X-Remind-Auth-Token"
