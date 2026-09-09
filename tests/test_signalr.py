"""Tests for the SignalR client."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from resideo_firstalert_api.signalr import RECORD_SEPARATOR, SignalRClient


def _make_client(
    session: aiohttp.ClientSession | None = None,
    token: str | None = "fake-token",
    on_event: MagicMock | None = None,
) -> SignalRClient:
    """Create a SignalRClient with sensible test defaults."""
    return SignalRClient(
        session=session or MagicMock(spec=aiohttp.ClientSession),
        get_access_token=lambda: token,
        on_event=on_event or MagicMock(),
    )


# ---- 1. __init__ stores parameters correctly ----


class TestInit:
    async def test_stores_session(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = SignalRClient(session, lambda: None, lambda msg: None)
        assert client._session is session

    async def test_stores_get_access_token(self):
        get_token = lambda: "tok"
        client = SignalRClient(MagicMock(), get_token, lambda msg: None)
        assert client._get_access_token is get_token

    async def test_stores_on_event(self):
        cb = MagicMock()
        client = SignalRClient(MagicMock(), lambda: None, cb)
        assert client._on_event is cb

    async def test_initial_state(self):
        client = _make_client()
        assert client._ws is None
        assert client._task is None
        assert client._stopping is False
        assert client._device_ids == []


# ---- 2-3. stop ----


class TestStop:
    async def test_stop_when_not_connected(self):
        """stop() should be a harmless no-op when never started."""
        client = _make_client()
        await client.stop()
        assert client._stopping is True
        assert client._task is None

    async def test_stop_cancels_running_task(self):
        """stop() should cancel the background task and wait for it."""
        client = _make_client()
        cancelled = asyncio.Event()

        async def _forever():
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        client._task = asyncio.create_task(_forever())
        # Give the task a moment to start
        await asyncio.sleep(0)

        await client.stop()

        assert cancelled.is_set()
        assert client._task is None
        assert client._stopping is True


# ---- 4-6. _handle_message ----


class TestHandleMessage:
    async def test_ping_sends_pong(self):
        """Type 6 (ping) should cause a pong ({type: 6}) to be sent."""
        client = _make_client()
        client._send = AsyncMock()

        await client._handle_message({"type": 6})

        client._send.assert_awaited_once_with({"type": 6})

    async def test_invocation_calls_on_event(self):
        """Type 1 (invocation) should forward the message to on_event."""
        on_event = MagicMock()
        client = _make_client(on_event=on_event)

        message = {
            "type": 1,
            "target": "DeviceStateChanged",
            "arguments": [{"deviceId": "abc123"}],
        }
        await client._handle_message(message)

        on_event.assert_called_once_with(message)

    async def test_close_message_no_crash(self):
        """Type 7 (close) should log but not raise."""
        client = _make_client()
        await client._handle_message({"type": 7, "error": "server shutting down"})


# ---- 7-8. _send edge cases ----


class TestSend:
    async def test_send_when_ws_is_none(self):
        """_send should silently do nothing when ws is None."""
        client = _make_client()
        assert client._ws is None
        await client._send({"type": 6})

    async def test_send_when_ws_is_closed(self):
        """_send should silently do nothing when ws is closed."""
        client = _make_client()
        ws = MagicMock(spec=aiohttp.ClientWebSocketResponse)
        ws.closed = True
        client._ws = ws
        await client._send({"type": 6})
        ws.send_str.assert_not_called()

    async def test_send_formats_message_with_record_separator(self):
        """_send should JSON-encode the dict and append the record separator."""
        client = _make_client()
        ws = AsyncMock(spec=aiohttp.ClientWebSocketResponse)
        ws.closed = False
        client._ws = ws

        payload = {"protocol": "json", "version": 1}
        await client._send(payload)

        expected = json.dumps(payload) + RECORD_SEPARATOR
        ws.send_str.assert_awaited_once_with(expected)


# ---- 9. _invoke ----


class TestInvoke:
    async def test_invoke_sends_correct_format(self):
        """_invoke should send a type-1 message with target and arguments."""
        client = _make_client()
        client._send = AsyncMock()

        await client._invoke("SubscribeSignalRV2", [["dev-1", "dev-2"]])

        client._send.assert_awaited_once_with(
            {
                "type": 1,
                "target": "SubscribeSignalRV2",
                "arguments": [["dev-1", "dev-2"]],
            }
        )


# ---- 10-11. _negotiate ----


class TestNegotiate:
    async def test_negotiate_returns_ws_url(self):
        """_negotiate should POST, parse connectionId, and build a wss:// URL."""
        resp_ctx = AsyncMock()
        resp_ctx.raise_for_status = MagicMock()
        resp_ctx.json = AsyncMock(
            return_value={"connectionId": "conn-42", "negotiateVersion": 1}
        )

        session = MagicMock(spec=aiohttp.ClientSession)
        # session.post is used as an async context manager
        session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=resp_ctx), __aexit__=AsyncMock(return_value=False)))

        client = _make_client(session=session, token="my-token")
        url = await client._negotiate()

        assert "conn-42" in url
        assert url.startswith("wss://")
        assert "?id=conn-42" in url

        # Verify auth header was forwarded
        call_kwargs = session.post.call_args
        assert call_kwargs.kwargs.get("headers", {}).get("Authorization") == "Bearer my-token"

    async def test_negotiate_raises_on_missing_connection_id(self):
        """_negotiate should raise RuntimeError when connectionId is absent."""
        resp_ctx = AsyncMock()
        resp_ctx.raise_for_status = MagicMock()
        resp_ctx.json = AsyncMock(return_value={"negotiateVersion": 1})

        session = MagicMock(spec=aiohttp.ClientSession)
        session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=resp_ctx), __aexit__=AsyncMock(return_value=False)))

        client = _make_client(session=session)

        with pytest.raises(RuntimeError, match="No connectionId"):
            await client._negotiate()


# ---- 12. start ----


class TestStart:
    async def test_start_sets_device_ids_and_creates_task(self):
        """start() should store device_ids and spawn a background task."""
        client = _make_client()
        # Patch _run so the task finishes instantly
        client._run = AsyncMock()

        await client.start(["dev-a", "dev-b"])

        assert client._device_ids == ["dev-a", "dev-b"]
        assert client._stopping is False
        assert client._task is not None
        # Let the task complete so it doesn't leak
        await client._task
