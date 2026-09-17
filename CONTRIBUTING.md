# Contributing to pyresideo-firstalert

> [!NOTE]
> This project isn't actively maintained (see the README) — PRs are reviewed on a best-effort basis, but they are welcome.

## What lives here

`pyresideo-firstalert` is the **API layer only** — an async Python client for Resideo's First Alert cloud API. It has no dependency on Home Assistant and doesn't know it's being used by one.

It owns:

- HTTP calls to Resideo's REST API (`api.py`)
- Auth0 / OAuth2 / PKCE login and token refresh (`auth.py`)
- The SignalR real-time push client (`signalr.py`)
- Every constant, exception type, enum, and parsed data shape tied to Resideo's API (`const.py`)

It explicitly does **not** own anything Home Assistant-specific — config flows, coordinators, entities, `manifest.json`, etc. Those live in the sibling repo, [ha-resideo-firstalert](https://github.com/zackwag/ha-resideo-firstalert), which depends on this package via PyPI.

See [AGENTS.md](AGENTS.md) for the fuller rationale and a decision rule for "which repo does this change belong in."

## Dev setup

```bash
git clone https://github.com/zackwag/pyresideo-firstalert.git
cd pyresideo-firstalert
pip install -e .
pip install -r requirements-test.txt
```

## Running tests

```bash
python -m pytest tests/ -v
```

Tests use `aioresponses` to mock HTTP calls — no live Resideo account or network access needed. Test files map 1:1 to source modules (`test_api.py`, `test_auth.py`, `test_signalr.py`).

## Making a change

1. Add or update tests alongside the code change.
2. Run `python -m pytest tests/ -v` locally before opening a PR; CI runs the same suite across Python 3.11–3.13.
3. If your change affects a documented endpoint, header, or auth flow, update [`openapi.yaml`](openapi.yaml) and/or the README alongside the code — stale docs here are worse than no docs, since this is a reverse-engineered API with no official reference.
4. If your change is meant to be consumed by `ha-resideo-firstalert` (a new exported function, a changed signature, a new exception type), say so in the PR description — it needs a version bump and release here before the integration repo can pick it up (see [Releasing](#releasing)).

## Releasing

Version lives in `pyproject.toml`. Bump it (patch for fixes, minor for new functionality), merge to `main`, then cut a GitHub Release with a matching tag (`vX.Y.Z`). Publishing to PyPI is automatic on release, gated on the test suite passing first.
