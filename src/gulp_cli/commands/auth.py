from __future__ import annotations

import asyncio

import typer
from gulp_sdk.client import GulpClient

from gulp_cli.client import get_client
from gulp_cli.config import delete_session, get_selected_session, save_session
from gulp_cli.output import print_json, print_result

app = typer.Typer(help="Authentication commands")


@app.command("login")
def login(
    url: str = typer.Option(..., help="gULP base URL, e.g. http://localhost:8080"),
    username: str = typer.Option(..., "--username", "-u", help="Username"),
    password: str = typer.Option(..., "--password", "-p", help="Password"),
    force: bool = typer.Option(True, help="Invalidate existing sessions for this user"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    async def _run() -> None:
        async with GulpClient(url) as client:
            token_session = await client.auth.login(username, password, force=force)
            save_session(
                url=url.rstrip("/"),
                username=username,
                token=token_session.token,
                user_id=token_session.user_id,
                expires_at=token_session.expires_at,
            )
            print_result(
                {
                    "status": "ok",
                    "username": username,
                    "token": token_session.token,
                    "url": url.rstrip("/"),
                    "user_id": token_session.user_id,
                    "expires_at": token_session.expires_at,
                },
                verbose=verbose,
            )

    asyncio.run(_run())


@app.command("logout")
def logout(
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    session = get_selected_session()
    url = str(session.get("url") or "").strip()
    token = str(session.get("token") or "").strip()
    username = str(session.get("username") or "").strip()

    async def _run() -> None:
        if url and token:
            async with GulpClient(url, token=token) as client:
                await client.auth.logout()
        delete_session(username)
        print_result({"status": "ok", "message": f"Logged out {username}", "username": username}, verbose=verbose)

    asyncio.run(_run())


@app.command("whoami")
def whoami(
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    async def _run() -> None:
        async with get_client() as client:
            me = await client.users.me()
            print_result(me, verbose=verbose)

    asyncio.run(_run())
