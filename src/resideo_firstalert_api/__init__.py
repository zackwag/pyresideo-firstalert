"""Async Python client for the Resideo First Alert smart smoke/CO detector API."""

from .api import (
    DeviceState,
    Location,
    ResideoApiClient,
    ResideoApiError,
    ResideoAuthError,
    ResideoConnectionError,
)
from .auth import AuthenticationError, ResideoAuth
from .const import (
    ALARM_STATE_ALARM,
    ALARM_STATE_EOL_YES,
    ALARM_STATE_LOW,
    ALARM_STATE_NONE,
    ALARM_STATE_SILENCED,
    ALARM_STATE_TESTING,
    ALARM_STATE_UNKNOWN,
    BATTERY_STATE_MAP,
    CO_ALARM_STATES,
    POWER_STATE_MAP,
    SMOKE_ALARM_STATES,
)
from .signalr import SignalRClient

__all__ = [
    "AuthenticationError",
    "DeviceState",
    "Location",
    "ResideoApiClient",
    "ResideoApiError",
    "ResideoAuth",
    "ResideoAuthError",
    "ResideoConnectionError",
    "SignalRClient",
    "ALARM_STATE_ALARM",
    "ALARM_STATE_EOL_YES",
    "ALARM_STATE_LOW",
    "ALARM_STATE_NONE",
    "ALARM_STATE_SILENCED",
    "ALARM_STATE_TESTING",
    "ALARM_STATE_UNKNOWN",
    "BATTERY_STATE_MAP",
    "CO_ALARM_STATES",
    "POWER_STATE_MAP",
    "SMOKE_ALARM_STATES",
]
