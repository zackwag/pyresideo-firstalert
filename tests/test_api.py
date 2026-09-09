"""Tests for api.py (no Home Assistant dependency, HTTP mocked via aioresponses)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import aiohttp
import pytest
from aioresponses import aioresponses
from resideo_firstalert_api.api import (
    ResideoApiClient,
    ResideoApiError,
    ResideoAuthError,
    ResideoConnectionError,
)
from resideo_firstalert_api.const import (
    ALARM_STATE_ALARM,
    API_ACCOUNTS_ENDPOINT,
    API_ACTIVITY_FEED_URL,
    API_BASE_URL,
    API_DEVICE_STATE_ENDPOINT,
    OAUTH_TOKEN_URL,
)

ACCOUNTS_URL = f"{API_BASE_URL}{API_ACCOUNTS_ENDPOINT}"
ACTIVITY_FEED_PATTERN = re.compile(re.escape(API_ACTIVITY_FEED_URL) + r"(\?.*)?$")


def _device_state_url(device_id: str) -> str:
    return f"{API_BASE_URL}{API_DEVICE_STATE_ENDPOINT.format(device_id=device_id)}"


def _token_response(access_token: str = "access-1", refresh_token: str | None = None) -> dict:
    payload = {"access_token": access_token, "expires_in": 3600, "token_type": "Bearer"}
    if refresh_token:
        payload["refresh_token"] = refresh_token
    return payload


def _accounts_response(devices: list[dict]) -> dict:
    return {
        "data": {
            "id": "user-123",
            "consumerUsers": [
                {
                    "consumerAccount": {
                        "locations": [
                            {
                                "name": "Home",
                                "consumerDevices": devices,
                            }
                        ]
                    }
                }
            ],
        },
        "errors": [],
    }


def _consumer_device(device_id: str, name: str = "Living Room Detector") -> dict:
    return {
        "id": f"consumer-{device_id}",
        "name": name,
        "device": {"deviceId": device_id, "globalDeviceType": "Citadel_SC5"},
    }


def _device_state_response(
    *,
    device_id: str = "DEVICE1",
    smoke: str = "idle",
    include_smoke_key: bool = True,
) -> dict:
    alarm_state = {
        "co": {"eventSource": "self", "tStampEpoch": 1766247701, "deviceState": "idle"},
        "test": {"eventSource": "self", "tStampEpoch": 1766034736, "deviceState": "idle"},
        "malfunction": {
            "eventSource": "self",
            "tStampEpoch": 1766247701,
            "deviceState": "none",
        },
        "battery": {
            "eventSource": "self",
            "tStampEpoch": 1766247701,
            "deviceState": "good",
        },
        "eol": {"eventSource": "self", "tStampEpoch": 1766247704, "deviceState": "no"},
        "power": {"eventSource": "self", "tStampEpoch": 1766029736, "deviceState": "ac"},
        "silence": {
            "eventSource": "self",
            "tStampEpoch": 1766247701,
            "deviceState": "not_silenced",
        },
    }
    if include_smoke_key:
        alarm_state["smoke"] = {
            "eventSource": "self",
            "tStampEpoch": 1766247701,
            "deviceState": smoke,
        }

    return {
        "name": device_id,
        "deviceType": "SmokeDetector",
        "sku": "SMCO600NVACA",
        "registrationStatus": "Registered",
        "isOnline": True,
        "isOnlineComputed": True,
        "isSupervisionHealthy": True,
        "dataSyncState": "Completed",
        "registrationDate": "2025-12-18T03:22:17.457+00:00",
        "lastMessageReceivedTime": "2025-12-20T17:02:30.861+00:00",
        "deviceState": {
            "desired": {},
            "reported": {
                "alarmState": alarm_state,
                "deviceConfig": {
                    "language": "en_US",
                    "room": 14,
                    "earlyWarning": True,
                    "debugLevel": "error",
                },
                "deviceInfo": {
                    "hwVerE2C": "1.0.0",
                    "hwVerExecCore": "1.0.0",
                    "hwVerSensorCore": "1.0.0",
                    "fwVerE2C": "00.07.72.00",
                    "fwVerExecCore": "01.06.38",
                    "fwVerSensorCore": "11.00",
                    "voiceFileVer": "1.0.0",
                    "runningHrs": 0,
                },
                "deviceStatus": {"rssi": -30, "ssid": "WiFiNetwork"},
                "deviceStatusFlags": {
                    "fault": False,
                    "e2Fault": False,
                    "photoFault": False,
                    "driftMalfunction": False,
                    "coFault": False,
                    "temperatureFault": False,
                    "voiceFault": False,
                    "radioFault": False,
                },
            },
        },
        "lastFirmwareUpdateTime": "2025-12-18T03:22:45.412+00:00",
    }


async def test_refresh_access_token_sets_access_token_and_expiry(session) -> None:
    client = ResideoApiClient(session, "initial-refresh-token")
    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, payload=_token_response(access_token="access-1"))
        await client._refresh_access_token()

    assert client._access_token == "access-1"
    assert client._token_expiry is not None
    assert client._token_expiry > datetime.now() + timedelta(minutes=59)


async def test_refresh_access_token_rotates_and_calls_callback(session) -> None:
    seen_tokens: list[str] = []
    client = ResideoApiClient(
        session, "old-refresh-token", on_refresh_token_updated=seen_tokens.append
    )
    with aioresponses() as m:
        m.post(
            OAUTH_TOKEN_URL,
            payload=_token_response(refresh_token="new-refresh-token"),
        )
        await client._refresh_access_token()

    assert client._refresh_token == "new-refresh-token"
    assert seen_tokens == ["new-refresh-token"]


async def test_refresh_access_token_no_callback_when_token_unchanged(session) -> None:
    seen_tokens: list[str] = []
    client = ResideoApiClient(
        session, "same-refresh-token", on_refresh_token_updated=seen_tokens.append
    )
    with aioresponses() as m:
        m.post(
            OAUTH_TOKEN_URL,
            payload=_token_response(refresh_token="same-refresh-token"),
        )
        await client._refresh_access_token()

    assert client._refresh_token == "same-refresh-token"
    assert seen_tokens == []


async def test_refresh_access_token_401_raises_auth_error(session) -> None:
    client = ResideoApiClient(session, "bad-refresh-token")
    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, status=401)
        with pytest.raises(ResideoAuthError):
            await client._refresh_access_token()


async def test_refresh_access_token_connection_error(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, exception=aiohttp.ClientConnectionError("boom"))
        with pytest.raises(ResideoConnectionError):
            await client._refresh_access_token()


async def test_get_devices_parses_account_response(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, payload=_token_response())
        m.get(
            ACCOUNTS_URL,
            payload=_accounts_response([_consumer_device("DEVICE1", "Living Room Detector")]),
        )
        devices = await client.get_devices()

    assert devices == [
        {
            "device_id": "DEVICE1",
            "name": "Living Room Detector",
            "location": "Home",
            "device_type": "Citadel_SC5",
            "consumer_device_id": "consumer-DEVICE1",
        }
    ]


async def test_get_devices_caches_within_ttl(session) -> None:
    """A second get_devices() call within the cache TTL must not hit the network."""
    client = ResideoApiClient(session, "refresh-token")
    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, payload=_token_response())
        # Registered once (no repeat=True): a second real HTTP call would fail.
        m.get(
            ACCOUNTS_URL,
            payload=_accounts_response([_consumer_device("DEVICE1")]),
        )
        first = await client.get_devices()
        second = await client.get_devices()

    assert first == second


async def test_get_devices_refetches_after_cache_expires(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, payload=_token_response(), repeat=True)
        m.get(
            ACCOUNTS_URL,
            payload=_accounts_response([_consumer_device("DEVICE1")]),
        )
        first = await client.get_devices()

        # Force the cache to look expired.
        client._devices_cache_time = datetime.now() - timedelta(hours=1)

        m.get(
            ACCOUNTS_URL,
            payload=_accounts_response([_consumer_device("DEVICE1", "Renamed Detector")]),
        )
        second = await client.get_devices()

    assert first[0]["name"] == "Living Room Detector"
    assert second[0]["name"] == "Renamed Detector"


async def test_parse_device_state_full_response(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    device_info = {
        "device_id": "DEVICE1",
        "name": "Living Room Detector",
        "location": "Home",
    }

    state = client._parse_device_state(
        _device_state_response(device_id="DEVICE1", smoke="idle"), device_info
    )

    assert state.device_id == "DEVICE1"
    assert state.name == "Living Room Detector"
    assert state.location == "Home"
    assert state.sku == "SMCO600NVACA"
    assert state.is_online is True
    assert state.is_online_computed is True
    assert state.registration_status == "Registered"
    assert state.data_sync_state == "Completed"
    assert state.debug_level == "error"
    assert state.smoke_state == "idle"
    assert state.battery_state == "good"
    assert state.power_state == "ac"
    assert state.alarm_timestamps["smoke"] == 1766247701
    assert state.alarm_timestamps["battery"] == 1766247701
    assert state.rssi == -30
    assert state.ssid == "WiFiNetwork"
    assert state.room == 14
    assert state.early_warning is True


async def test_parse_device_state_missing_field_defaults_to_safe_state(session) -> None:
    """Regression test: a missing alarmState.smoke must not look like an active alarm."""
    client = ResideoApiClient(session, "refresh-token")
    device_info = {"device_id": "DEVICE1"}

    state = client._parse_device_state(
        _device_state_response(include_smoke_key=False), device_info
    )

    assert state.smoke_state == "unknown"
    assert state.smoke_state != ALARM_STATE_ALARM
    assert state.alarm_timestamps["smoke"] is None


async def test_get_all_device_states_propagates_auth_error(session) -> None:
    """Regression test: an auth failure while polling a device must not be swallowed."""
    client = ResideoApiClient(session, "refresh-token")
    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, payload=_token_response(), repeat=True)
        m.get(
            ACCOUNTS_URL,
            payload=_accounts_response([_consumer_device("DEVICE1")]),
        )
        # First attempt gets 401, triggers a token refresh + one retry, which
        # also gets 401 - that's what should raise ResideoAuthError.
        m.get(_device_state_url("DEVICE1"), status=401)
        m.get(_device_state_url("DEVICE1"), status=401)

        with pytest.raises(ResideoAuthError):
            await client.get_all_device_states()


async def test_get_all_device_states_skips_device_with_non_auth_error(
    session, caplog: pytest.LogCaptureFixture
) -> None:
    client = ResideoApiClient(session, "refresh-token")
    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, payload=_token_response())
        m.get(
            ACCOUNTS_URL,
            payload=_accounts_response(
                [_consumer_device("DEVICE1"), _consumer_device("DEVICE2")]
            ),
        )
        m.get(_device_state_url("DEVICE1"), status=500, body="boom")
        m.get(_device_state_url("DEVICE2"), payload=_device_state_response(device_id="DEVICE2"))

        states = await client.get_all_device_states()

    assert list(states) == ["DEVICE2"]
    assert "DEVICE1" in caplog.text


# ---------------------------------------------------------------------------
# 1. _ensure_token reuses a valid token without refreshing
# ---------------------------------------------------------------------------
async def test_ensure_token_reuses_valid_token(session) -> None:
    """A non-expired token is returned without hitting the network."""
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "still-valid"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    # No aioresponses context -- any real HTTP would raise.
    token = await client._ensure_token()
    assert token == "still-valid"


# ---------------------------------------------------------------------------
# 2. _ensure_token refreshes when token is expired
# ---------------------------------------------------------------------------
async def test_ensure_token_refreshes_expired_token(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "stale"
    client._token_expiry = datetime.now() - timedelta(hours=1)

    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, payload=_token_response(access_token="fresh"))
        token = await client._ensure_token()

    assert token == "fresh"


# ---------------------------------------------------------------------------
# 3. _request retries on 401 then succeeds on second attempt
# ---------------------------------------------------------------------------
async def test_request_retries_on_401_then_succeeds(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "old-token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    with aioresponses() as m:
        # First attempt returns 401, triggering a refresh+retry.
        m.get(ACCOUNTS_URL, status=401)
        m.post(OAUTH_TOKEN_URL, payload=_token_response(access_token="new-token"))
        m.get(ACCOUNTS_URL, payload={"ok": True})

        result = await client._request("GET", API_ACCOUNTS_ENDPOINT)

    assert result == {"ok": True}


# ---------------------------------------------------------------------------
# 4. _request raises ResideoApiError on non-200/non-401 status
# ---------------------------------------------------------------------------
async def test_request_raises_api_error_on_non_200(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    with aioresponses() as m:
        m.get(ACCOUNTS_URL, status=500, body="server error")
        with pytest.raises(ResideoApiError, match="500"):
            await client._request("GET", API_ACCOUNTS_ENDPOINT)


# ---------------------------------------------------------------------------
# 5. _request raises ResideoConnectionError on aiohttp.ClientError
# ---------------------------------------------------------------------------
async def test_request_raises_connection_error_on_client_error(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    with aioresponses() as m:
        m.get(ACCOUNTS_URL, exception=aiohttp.ClientConnectionError("gone"))
        with pytest.raises(ResideoConnectionError):
            await client._request("GET", API_ACCOUNTS_ENDPOINT)


# ---------------------------------------------------------------------------
# 6. get_device_state returns raw response dict
# ---------------------------------------------------------------------------
async def test_get_device_state_returns_raw_dict(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    raw = _device_state_response(device_id="DEV1")
    with aioresponses() as m:
        m.get(_device_state_url("DEV1"), payload=raw)
        result = await client.get_device_state("DEV1")

    assert result == raw


# ---------------------------------------------------------------------------
# 7. get_accounts returns raw response dict
# ---------------------------------------------------------------------------
async def test_get_accounts_returns_raw_dict(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    payload = _accounts_response([_consumer_device("D1")])
    with aioresponses() as m:
        m.get(ACCOUNTS_URL, payload=payload)
        result = await client.get_accounts()

    assert result == payload


# ---------------------------------------------------------------------------
# 8. get_activity_feed returns list when API returns a list
# ---------------------------------------------------------------------------
async def test_get_activity_feed_returns_list(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    events = [{"id": "evt1"}, {"id": "evt2"}]
    with aioresponses() as m:
        m.get(ACTIVITY_FEED_PATTERN, payload=events)
        result = await client.get_activity_feed("DEV1")

    assert result == events


# ---------------------------------------------------------------------------
# 9. get_activity_feed extracts events when API returns dict with "events"
# ---------------------------------------------------------------------------
async def test_get_activity_feed_extracts_events_from_dict(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    events = [{"id": "evt1"}]
    with aioresponses() as m:
        m.get(ACTIVITY_FEED_PATTERN, payload={"events": events, "total": 1})
        result = await client.get_activity_feed("DEV1")

    assert result == events


# ---------------------------------------------------------------------------
# 10. get_activity_feed returns empty list on non-200 status
# ---------------------------------------------------------------------------
async def test_get_activity_feed_returns_empty_on_non_200(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    with aioresponses() as m:
        m.get(ACTIVITY_FEED_PATTERN, status=500)
        result = await client.get_activity_feed("DEV1")

    assert result == []


# ---------------------------------------------------------------------------
# 11. get_activity_feed returns empty list on connection error
# ---------------------------------------------------------------------------
async def test_get_activity_feed_returns_empty_on_connection_error(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    with aioresponses() as m:
        m.get(ACTIVITY_FEED_PATTERN, exception=aiohttp.ClientConnectionError("fail"))
        result = await client.get_activity_feed("DEV1")

    assert result == []


# ---------------------------------------------------------------------------
# 12. get_activity_feed retries on 401
# ---------------------------------------------------------------------------
async def test_get_activity_feed_retries_on_401(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "old-token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    events = [{"id": "evt-retry"}]
    with aioresponses() as m:
        m.get(ACTIVITY_FEED_PATTERN, status=401)
        m.post(OAUTH_TOKEN_URL, payload=_token_response(access_token="new-token"))
        m.get(ACTIVITY_FEED_PATTERN, payload=events)
        result = await client.get_activity_feed("DEV1")

    assert result == events


# ---------------------------------------------------------------------------
# 13. _parse_device_state parses fault flags correctly (some set to True)
# ---------------------------------------------------------------------------
async def test_parse_device_state_fault_flags(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    raw = _device_state_response()
    # Flip a few fault flags to True.
    flags = raw["deviceState"]["reported"]["deviceStatusFlags"]
    flags["fault"] = True
    flags["coFault"] = True
    flags["radioFault"] = True

    state = client._parse_device_state(raw, {"device_id": "DEVICE1"})

    assert state.fault is True
    assert state.co_fault is True
    assert state.radio_fault is True
    # The rest should remain False.
    assert state.e2_fault is False
    assert state.photo_fault is False
    assert state.drift_malfunction is False
    assert state.temperature_fault is False
    assert state.voice_fault is False


# ---------------------------------------------------------------------------
# 14. _parse_device_state parses firmware/hardware versions
# ---------------------------------------------------------------------------
async def test_parse_device_state_firmware_hardware_versions(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    raw = _device_state_response()
    state = client._parse_device_state(raw, {"device_id": "DEVICE1"})

    assert state.firmware_version == "00.07.72.00"
    assert state.fw_ver_exec_core == "01.06.38"
    assert state.fw_ver_sensor_core == "11.00"
    assert state.hw_ver_e2c == "1.0.0"
    assert state.hw_ver_exec_core == "1.0.0"
    assert state.hw_ver_sensor_core == "1.0.0"
    assert state.voice_file_ver == "1.0.0"
    assert state.running_hours == 0


# ---------------------------------------------------------------------------
# 15. _parse_device_state handles completely empty reported section
# ---------------------------------------------------------------------------
async def test_parse_device_state_empty_reported(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    raw = {
        "name": "EMPTY",
        "deviceType": "SmokeDetector",
        "deviceState": {"desired": {}, "reported": {}},
    }
    state = client._parse_device_state(raw, {"device_id": "EMPTY", "name": "Empty"})

    assert state.device_id == "EMPTY"
    assert state.name == "Empty"
    assert state.smoke_state == "unknown"
    assert state.co_state == "unknown"
    assert state.battery_state == "unknown"
    assert state.rssi is None
    assert state.ssid is None
    assert state.firmware_version is None
    assert state.fault is False
    assert state.early_warning is None
    assert state.room is None


# ---------------------------------------------------------------------------
# 16. get_devices handles empty account (no consumerUsers)
# ---------------------------------------------------------------------------
async def test_get_devices_empty_account(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    client._access_token = "token"
    client._token_expiry = datetime.now() + timedelta(hours=1)

    with aioresponses() as m:
        m.get(ACCOUNTS_URL, payload={"data": {"id": "user-123"}, "errors": []})
        devices = await client.get_devices()

    assert devices == []


# ---------------------------------------------------------------------------
# 17. _refresh_access_token raises ResideoAuthError on 403
# ---------------------------------------------------------------------------
async def test_refresh_access_token_403_raises_auth_error(session) -> None:
    client = ResideoApiClient(session, "bad-refresh-token")
    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, status=403)
        with pytest.raises(ResideoAuthError):
            await client._refresh_access_token()


# ---------------------------------------------------------------------------
# 18. _refresh_access_token raises ResideoApiError on 500
# ---------------------------------------------------------------------------
async def test_refresh_access_token_500_raises_api_error(session) -> None:
    client = ResideoApiClient(session, "refresh-token")
    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, status=500)
        with pytest.raises(ResideoApiError, match="500"):
            await client._refresh_access_token()
