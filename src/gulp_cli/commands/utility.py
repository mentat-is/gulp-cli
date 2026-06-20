from __future__ import annotations

import asyncio

import typer

from gulp_cli.client import get_client

app = typer.Typer(help="Utility commands")


@app.command("gulp-version")
def utility_gulp_version() -> None:
    """Show the connected gULP server version."""

    async def _run() -> None:
        async with get_client() as client:
            server_version = await client.version()
        print(f"{server_version}")

    asyncio.run(_run())
