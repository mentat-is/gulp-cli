from __future__ import annotations

import asyncio

import typer
from gulp_sdk.client import GulpClient

from gulp_cli.config import clear_config, load_config, save_config
from gulp_cli.output import print_json

app = typer.Typer(help="Authentication commands")


@app.command("login")
def login(
    url: str = typer.Option(..., help="gULP base URL, e.g. http://localhost:8080"),
    username: str = typer.Option(..., "--username", "-u", help="Username"),
    password: str = typer.Option(..., "--password", "-p", help="Password"),
    force: bool = typer.Option(True, help="Invalidate existing sessions for this user"),
) -> None:
    async def _run() -> None:
        async with GulpClient(url) as client:
            token_session = await client.auth.login(username, password, force=force)
            save_config(
                {
                    "url": url.rstrip("/"),
                    "token": token_session.token,
                    "user_id": token_session.user_id,
                    "expires_at": token_session.expires_at,
                }
            )
            print_json(
                {
                    "status": "ok",
                    "token": token_session.token,
                    "url": url.rstrip("/"),
                    "user_id": token_session.user_id,
                    "expires_at": token_session.expires_at,
                }
            )

    asyncio.run(_run())


@app.command("logout")
def logout() -> None:
    cfg = load_config()
    url = str(cfg.get("url") or "").strip()
    token = str(cfg.get("token") or "").strip()

    async def _run() -> None:
        if url and token:
            async with GulpClient(url, token=token) as client:
                await client.auth.logout()
        clear_config()
        print_json({"status": "ok", "message": "Logged out"})

    asyncio.run(_run())


@app.command("whoami")
def whoami() -> None:
    async def _run() -> None:
        cfg = load_config()
        url = str(cfg.get("url") or "").strip()
        token = str(cfg.get("token") or "").strip()
        if not url or not token:
            raise typer.BadParameter("Not authenticated. Run login first.")
        async with GulpClient(url, token=token) as client:
            me = await client.users.me()
            print_json(me)

    asyncio.run(_run())
