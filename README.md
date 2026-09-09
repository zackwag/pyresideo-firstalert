# pyresideo-firstalert

[![PyPI](https://img.shields.io/pypi/v/pyresideo-firstalert)](https://pypi.org/project/pyresideo-firstalert/)
[![Tests](https://github.com/zackwag/pyresideo-firstalert/actions/workflows/test.yml/badge.svg)](https://github.com/zackwag/pyresideo-firstalert/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Async Python client for the Resideo First Alert smart smoke/CO detector API.

Extracted from the [ha-resideo-firstalert](https://github.com/zackwag/ha-resideo-firstalert) Home Assistant integration so the API layer can be used independently.

## Installation

```bash
pip install pyresideo-firstalert
```

## Usage

```python
import aiohttp
from resideo_firstalert_api import ResideoApiClient

async with aiohttp.ClientSession() as session:
    client = ResideoApiClient(session, refresh_token="your-token")
    states = await client.get_all_device_states()
    for device_id, state in states.items():
        print(f"{state.name}: smoke={state.smoke_state}, co={state.co_state}")
```

## Authentication

To obtain a refresh token, use the `ResideoAuth` class:

```python
from resideo_firstalert_api import ResideoAuth

async with aiohttp.ClientSession() as session:
    auth = ResideoAuth(session)
    tokens = await auth.authenticate("email@example.com", "password")
    refresh_token = tokens["refresh_token"]
```

## Real-time Events

Subscribe to real-time device state changes via SignalR:

```python
from resideo_firstalert_api import SignalRClient

client = SignalRClient(session, get_access_token=..., on_event=...)
await client.start(device_ids=["device1", "device2"])
```

## API Reference

The full API is documented in an [OpenAPI 3.1.0 spec](openapi.yaml) covering all endpoints, schemas, and alarm state enums.

## License

MIT
