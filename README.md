# pyresideo-firstalert

Async Python client for the Resideo First Alert smart smoke/CO detector API.

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

auth = ResideoAuth(session)
tokens = await auth.authenticate("email@example.com", "password")
refresh_token = tokens["refresh_token"]
```

## Real-time Events

Subscribe to real-time device events via SignalR:

```python
from resideo_firstalert_api import SignalRClient

client = SignalRClient(session, get_access_token=..., on_event=...)
await client.start(device_ids=["device1", "device2"])
```
