"""Tests for the PKCE helpers and auth steps in auth.py (no network, no Home Assistant)."""

from __future__ import annotations

import base64
import hashlib
import re
from unittest.mock import Mock

import aiohttp
import pytest
from aioresponses import aioresponses

from resideo_firstalert_api.auth import (
    AUTH0_AUTHORIZE_URL,
    AUTH0_BASE_URL,
    AUTH0_CALLBACK_URL,
    AUTH0_LOGIN_URL,
    OAUTH_TOKEN_URL,
    REDIRECT_URI,
    AuthenticationError,
    ResideoAuth,
)


def test_generate_pkce_verifier_is_valid_length_and_charset() -> None:
    auth = ResideoAuth(Mock())
    auth._generate_pkce()

    # RFC 7636: code_verifier must be 43-128 characters, unreserved charset.
    assert 43 <= len(auth._code_verifier) <= 128
    assert all(c not in "+/=" for c in auth._code_verifier)


def test_generate_pkce_challenge_is_s256_of_verifier() -> None:
    auth = ResideoAuth(Mock())
    auth._generate_pkce()

    expected_digest = hashlib.sha256(auth._code_verifier.encode("ascii")).digest()
    expected_challenge = (
        base64.urlsafe_b64encode(expected_digest).decode("utf-8").rstrip("=")
    )
    assert auth._code_challenge == expected_challenge


def test_generate_pkce_state_is_random_and_nonempty() -> None:
    auth = ResideoAuth(Mock())

    auth._generate_pkce()
    first_state = auth._state
    auth._generate_pkce()
    second_state = auth._state

    assert first_state
    assert second_state
    assert first_state != second_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth() -> ResideoAuth:
    """Create a ResideoAuth with a mock session and PKCE initialized."""
    auth = ResideoAuth(Mock())
    auth._generate_pkce()
    return auth


# ---------------------------------------------------------------------------
# Step 1: _step1_authorize
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step1_authorize_returns_auth0_state() -> None:
    auth = _make_auth()
    redirect_url = f"{AUTH0_BASE_URL}/login?state=fake_auth0_state&foo=bar"
    pattern = re.compile(r"^https://login\.resideo\.com/authorize\?")

    with aioresponses() as m:
        m.get(
            pattern,
            status=302,
            headers={"Location": redirect_url},
        )
        async with aiohttp.ClientSession() as session:
            result = await auth._step1_authorize(session)

    assert result == "fake_auth0_state"


@pytest.mark.asyncio
async def test_step1_authorize_raises_on_non_302() -> None:
    auth = _make_auth()
    pattern = re.compile(r"^https://login\.resideo\.com/authorize\?")

    with aioresponses() as m:
        m.get(pattern, status=200)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(AuthenticationError, match="Expected redirect"):
                await auth._step1_authorize(session)


# ---------------------------------------------------------------------------
# Step 2: _step2_get_login_page
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step2_get_login_page_extracts_csrf_token() -> None:
    auth = _make_auth()
    login_pattern = re.compile(r"^https://login\.resideo\.com/login\?")

    with aioresponses() as m:
        m.get(
            login_pattern,
            status=200,
            headers={
                "Set-Cookie": "_csrf=test_csrf_token; Path=/usernamepassword/login",
            },
            body="<html>login page</html>",
        )
        async with aiohttp.ClientSession() as session:
            result = await auth._step2_get_login_page(session, "some_state")

    assert result == "test_csrf_token"


@pytest.mark.asyncio
async def test_step2_get_login_page_raises_when_no_csrf() -> None:
    auth = _make_auth()
    login_pattern = re.compile(r"^https://login\.resideo\.com/login\?")

    with aioresponses() as m:
        m.get(login_pattern, status=200, body="<html>no cookies</html>")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(AuthenticationError, match="No CSRF token"):
                await auth._step2_get_login_page(session, "some_state")


# ---------------------------------------------------------------------------
# Step 3: _step3_submit_credentials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step3_submit_credentials_extracts_wresult_and_wctx() -> None:
    auth = _make_auth()
    html_body = (
        '<form>'
        '<input type="hidden" name="wresult" value="token_value_here" />'
        '<input type="hidden" name="wctx" value="context_value_here" />'
        '</form>'
    )

    with aioresponses() as m:
        m.post(AUTH0_LOGIN_URL, status=200, body=html_body)
        async with aiohttp.ClientSession() as session:
            wresult, wctx = await auth._step3_submit_credentials(
                session, "auth0_state", "csrf_tok", "user@example.com", "pass"
            )

    assert wresult == "token_value_here"
    assert wctx == "context_value_here"


@pytest.mark.asyncio
async def test_step3_submit_credentials_raises_on_wrong_password() -> None:
    auth = _make_auth()

    with aioresponses() as m:
        m.post(
            AUTH0_LOGIN_URL,
            status=403,
            body="Wrong email or password",
        )
        async with aiohttp.ClientSession() as session:
            with pytest.raises(AuthenticationError, match="Invalid email or password"):
                await auth._step3_submit_credentials(
                    session, "auth0_state", "csrf_tok", "user@example.com", "bad"
                )


# ---------------------------------------------------------------------------
# Step 4: _step4_callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step4_callback_returns_location() -> None:
    auth = _make_auth()
    resume_url = "/authorize/resume?state=abc123"

    with aioresponses() as m:
        m.post(
            AUTH0_CALLBACK_URL,
            status=302,
            headers={"Location": resume_url},
        )
        async with aiohttp.ClientSession() as session:
            result = await auth._step4_callback(session, "wresult_val", "wctx_val")

    assert result == resume_url


@pytest.mark.asyncio
async def test_step4_callback_raises_on_non_302() -> None:
    auth = _make_auth()

    with aioresponses() as m:
        m.post(AUTH0_CALLBACK_URL, status=200, body="unexpected")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(AuthenticationError, match="Expected redirect from callback"):
                await auth._step4_callback(session, "wresult_val", "wctx_val")


# ---------------------------------------------------------------------------
# Step 5: _step5_resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step5_resume_extracts_code_and_verifies_state() -> None:
    auth = _make_auth()
    resume_url = f"{AUTH0_BASE_URL}/authorize/resume?state=xyz"
    redirect_location = f"{REDIRECT_URI}?code=auth_code_123&state={auth._state}"

    with aioresponses() as m:
        m.get(
            resume_url,
            status=302,
            headers={"Location": redirect_location},
        )
        async with aiohttp.ClientSession() as session:
            result = await auth._step5_resume(session, resume_url)

    assert result == "auth_code_123"


@pytest.mark.asyncio
async def test_step5_resume_raises_on_state_mismatch() -> None:
    auth = _make_auth()
    resume_url = f"{AUTH0_BASE_URL}/authorize/resume?state=xyz"
    redirect_location = f"{REDIRECT_URI}?code=auth_code_123&state=wrong_state"

    with aioresponses() as m:
        m.get(
            resume_url,
            status=302,
            headers={"Location": redirect_location},
        )
        async with aiohttp.ClientSession() as session:
            with pytest.raises(AuthenticationError, match="State mismatch"):
                await auth._step5_resume(session, resume_url)


# ---------------------------------------------------------------------------
# Step 6: _step6_exchange_code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step6_exchange_code_returns_tokens(session: aiohttp.ClientSession) -> None:
    auth = ResideoAuth(session)
    auth._generate_pkce()
    token_response = {
        "access_token": "access_123",
        "refresh_token": "refresh_456",
        "id_token": "id_789",
        "token_type": "Bearer",
        "expires_in": 86400,
    }

    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, status=200, payload=token_response)
        result = await auth._step6_exchange_code("auth_code_value")

    assert result == token_response
    assert result["access_token"] == "access_123"
    assert result["refresh_token"] == "refresh_456"


@pytest.mark.asyncio
async def test_step6_exchange_code_raises_on_non_200(session: aiohttp.ClientSession) -> None:
    auth = ResideoAuth(session)
    auth._generate_pkce()

    with aioresponses() as m:
        m.post(OAUTH_TOKEN_URL, status=400, body="invalid_grant")
        with pytest.raises(AuthenticationError, match="Token exchange failed"):
            await auth._step6_exchange_code("bad_code")
