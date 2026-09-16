"""Constants for the Resideo First Alert API."""

# OAuth Configuration
# OAUTH_CLIENT_ID is a public PKCE client identifier, not a secret - it's the
# same value shipped inside the official First Alert mobile app binary, where
# it's trivially extractable by anyone. There is no client_secret; PKCE
# public clients are designed not to need one.
OAUTH_CLIENT_ID = "SRmiA7CaYi1JgivDZdzzoZu4X5VBogGt"
OAUTH_TOKEN_URL = "https://login.resideo.com/oauth/token"

# API Configuration
# Resideo retired api.resideo.com in Sept 2026 (it now answers every call with a canned
# 503 "planned maintenance" body that never clears) and moved the consumer API to this
# host. Paths are unchanged; two extra headers are now required on every call (see
# api.py). Confirmed live: both endpoints below 401 (not 503/404) at this host when
# unauthenticated. Source: sfcodes/ha-resideo v0.3.0, which mapped the same move for
# Resideo's thermostat/leak-detector devices.
API_BASE_URL = "https://api.ha.resideo.com"
API_ACCOUNTS_ENDPOINT = "/ris-public-api/api/v1/accounts"
API_DEVICE_STATE_ENDPOINT = "/ris-public-api/api/v2/devices/smokeDetectors/{device_id}/state"
API_ACTIVITY_FEED_URL = f"{API_BASE_URL}/ds-activity-feed-api/api/v1/app/events"

# Azure APIM subscription key (prod). Mandatory on every api.ha.resideo.com call, not
# just writes - sent unconditionally by the app on every request.
API_SUBSCRIPTION_KEY = "b60885e8a9b44680a29ea1f03452878a"
# The real app's User-Agent, sent on every API call (distinct from the browser-ish UA
# used for the Auth0 web login flow in auth.py).
API_USER_AGENT = "First Alert/2440 CFNetwork/3860.600.12 Darwin/25.5.0"

# How long to reuse the account/device list before re-fetching it.
DEVICE_LIST_CACHE_SECONDS = 300

# Alarm states
ALARM_STATE_ALARM = "alarm"
ALARM_STATE_LOW = "low"
ALARM_STATE_NONE = "none"
ALARM_STATE_UNKNOWN = "unknown"
ALARM_STATE_SILENCED = "silenced"
ALARM_STATE_EOL_YES = "yes"
ALARM_STATE_TESTING = "testing"

# All smoke/CO deviceState values that indicate an active alarm condition.
SMOKE_ALARM_STATES = frozenset({
    "alarm",
    "smokeAlarm",
    "smokeEarlyWarning",
    "smokeInterconnectAlarm",
    "smokeEarlyWarningInterconnectAlarm",
})

CO_ALARM_STATES = frozenset({
    "alarm",
    "coAlarm",
    "coEarlyWarning",
    "carbonMonoxideAlarm",
    "carbonMonoxideEarlyWarning",
    "carbonMonoxideInterconnectAlarm",
    "carbonMonoxideEarlyWarningInterconnectAlarm",
})

# The API reports transitional power states during AC/DC switchovers.
POWER_STATE_MAP: dict[str, str] = {
    "ac": "ac",
    "dc": "dc",
    "battery": "battery",
    "acOnly": "ac",
    "acToDc": "dc",
    "dcToAc": "ac",
    "acLoss": "dc",
    "acRestored": "ac",
}

# The API can return "replace" or "critical" alongside "good" and "low".
BATTERY_STATE_MAP: dict[str, str] = {
    "good": "good",
    "low": "low",
    "replace": "replace",
    "critical": "critical",
}
