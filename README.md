# pyresideo-firstalert

[![PyPI](https://img.shields.io/pypi/v/pyresideo-firstalert)](https://pypi.org/project/pyresideo-firstalert/)
[![Tests](https://github.com/zackwag/pyresideo-firstalert/actions/workflows/test.yml/badge.svg)](https://github.com/zackwag/pyresideo-firstalert/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> [!WARNING]
> **This project is no longer actively maintained.** It backed the [ha-resideo-firstalert](https://github.com/zackwag/ha-resideo-firstalert) Home Assistant integration, which I can no longer support after replacing my own First Alert smart alarms with non-smart ones and running into ongoing instability in Resideo's cloud API. The repo stays open for community PRs, reviewed on a best-effort basis.

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

### Browser-assisted login (recommended)

Resideo added a bot check (captcha) to its Auth0 login form, so the scripted
`ResideoAuth.authenticate()` flow below no longer works — it fails with
`invalid_captcha` even for correct credentials. A real browser passes the
captcha invisibly, so the workaround is to have the user sign in themselves and
hand the resulting authorization code back to your script:

```python
from resideo_firstalert_api import (
    build_authorize_url,
    exchange_code_for_tokens,
    generate_pkce_pair,
    parse_authorization_code,
)

code_verifier, code_challenge, state = generate_pkce_pair()
print("Open this URL in a browser and sign in:")
print(build_authorize_url(code_challenge, state))

# After signing in, the browser lands on a page with the authorization code
# in the address bar (e.g. "https://login.resideo.com/.../callback?code=...").
# Paste that whole address, or just the code, back into your script.
pasted = input("Paste the address bar URL or code: ")
code = parse_authorization_code(pasted, expected_state=state)

async with aiohttp.ClientSession() as session:
    tokens = await exchange_code_for_tokens(session, code, code_verifier)
    refresh_token = tokens["refresh_token"]
```

The authorization code is single-use and expires quickly, so exchange it
promptly after the user pastes it back.

### Email/password login (currently blocked by Resideo's captcha)

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
