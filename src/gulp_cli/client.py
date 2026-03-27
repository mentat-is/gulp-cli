from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from gulp_sdk.client import GulpClient

from gulp_cli.config import get_required_url_token


@asynccontextmanager
async def get_client() -> AsyncIterator[GulpClient]:
    url, token = get_required_url_token()
    async with GulpClient(url, token=token) as client:
        yield client
