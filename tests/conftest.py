"""Shared pytest fixtures for pyresideo-firstalert tests."""

from __future__ import annotations

import aiohttp
import pytest


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as sess:
        yield sess
