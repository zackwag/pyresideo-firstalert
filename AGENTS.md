# Agent instructions for pyresideo-firstalert

This repo and [ha-resideo-firstalert](https://github.com/zackwag/ha-resideo-firstalert) are split along a hard boundary: **this repo is the Resideo API client; the other repo is the Home Assistant integration that consumes it.** Honor that split.

## The rule

If your change involves any of the following, it belongs **here**, not in `ha-resideo-firstalert`:

- An HTTP request to any Resideo/Auth0 host (`api.resideo.com`, `api.ha.resideo.com`, `login.resideo.com`, the SignalR notification service)
- Authentication or token handling of any kind (PKCE, refresh rotation, captcha workarounds, header/user-agent requirements)
- Parsing or shaping data that comes back from Resideo's API
- A new exception type describing an API failure mode

If your change involves any of the following, it belongs in `ha-resideo-firstalert` **instead**:

- Home Assistant config entries, config flow steps, or options flow
- Entities, coordinators, platforms (`binary_sensor`, `sensor`, `event`)
- `manifest.json`, `strings.json`, translations, diagnostics, repairs
- Anything that imports from `homeassistant.*`

Home Assistant is not a dependency of this package (see `pyproject.toml`) and must stay that way — do not add one, even transitively, even for a "just this once" convenience.

## Cross-repo changes

Most features spanning both repos follow this order, and it is not optional:

1. Land and test the change **here** first.
2. Bump this package's version and cut a release (tag `vX.Y.Z`, GitHub Release) — this publishes to PyPI automatically, gated on tests passing.
3. Only then, in `ha-resideo-firstalert`, bump the `pyresideo-firstalert==X.Y.Z` pin in both `custom_components/resideo_firstalert/manifest.json` and `requirements-test.txt`, and wire the new functionality into config flow / coordinator / entities as needed.

Never point the integration repo at an unreleased version of this package (a git ref, a local path, etc.) — HACS and pip installs resolve `manifest.json` requirements from PyPI only.

## `ha-resideo-firstalert`'s re-export shims — the thing that WILL bite you

`ha-resideo-firstalert/custom_components/resideo_firstalert/{api,auth,signalr,const}.py` are **thin re-export shims** over this package — each one just imports names from `resideo_firstalert_api` and re-lists them in `__all__`, so the rest of the integration's code can keep using stable `.api`/`.auth`/`.signalr`/`.const` import paths.

**Whenever you add a new public name here that `ha-resideo-firstalert` needs to consume, the shim's import list and `__all__` must be updated to include it, in the same change that wires it into `config_flow.py`/`coordinator.py`/etc.** Forgetting this does not fail at import time in this repo — it fails at import time in the *other* repo, at runtime, in a way neither repo's CI catches (see the incident below). If you're the one adding the feature here, you are also responsible for making sure the consuming shim isn't left stale.

**This is not hypothetical — it happened.** Browser-assisted login (`generate_pkce_pair`, `build_authorize_url`, `parse_authorization_code`, `exchange_code_for_tokens`) was added here in v1.1.0, exported from `__init__.py`, and correctly imported by a new `config_flow.py` step in `ha-resideo-firstalert` — but the `auth.py` shim's re-export list wasn't updated to match. Neither repo's test suite imports `config_flow.py` (`ha-resideo-firstalert`'s tests only cover the shim surface, not real HA config flow classes), and hassfest/HACS validation only check manifest/strings schemas, not Python imports. A released integration version (`v2.1.0`) shipped with browser login raising `ImportError` on every use, caught only by manually installing `homeassistant` and importing every module by hand — fixed in `v2.1.1`.

If you add or rename a public export here, go check the shim files in `ha-resideo-firstalert` yourself before considering the change done — don't assume a follow-up will catch it.
