from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_records, print_result
from gulp_cli.utils import comma_split

app = typer.Typer(help="User management")


def _human_time(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return str(value)
    return str(value)


@app.command("list")
def user_list(
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    async def _run() -> None:
        async with get_client() as client:
            users = await client.users.list()
            if as_json:
                print_result(users, verbose=verbose)
            else:
                print_result(users, verbose=verbose, formatter=lambda d: print_records(d, title="Users"))

    asyncio.run(_run())


@app.command("get")
def user_get(user_id: str,
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    async def _run() -> None:
        async with get_client() as client:
            user = await client.users.get(user_id)
            print_result(user, verbose=verbose)

    asyncio.run(_run())


@app.command("create")
def user_create(
    user_id: str,
    password: str = typer.Option(..., "--password", "-p"),
    permission: str = typer.Option("read", "--permission", help="Comma-separated permissions"),
    email: str | None = typer.Option(None, "--email"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    async def _run() -> None:
        permissions = comma_split(permission)
        if not permissions:
            raise typer.BadParameter("At least one permission is required")
        async with get_client() as client:
            user = await client.users.create(
                user_id=user_id,
                password=password,
                permission=permissions,
                email=email,
            )
            print_result(user, verbose=verbose)

    asyncio.run(_run())


@app.command("update")
def user_update(
    user_id: str,
    password: str | None = typer.Option(None, "--password", "-p"),
    permission: str | None = typer.Option(None, "--permission", help="Comma-separated permissions"),
    email: str | None = typer.Option(None, "--email"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    async def _run() -> None:
        payload: dict[str, Any] = {"user_id": user_id}
        if password:
            payload["password"] = password
        if permission is not None:
            payload["permission"] = comma_split(permission)
        if email is not None:
            payload["email"] = email
        async with get_client() as client:
            updated = await client.users.update(**payload)
            print_result(updated, verbose=verbose)

    asyncio.run(_run())


@app.command("delete")
def user_delete(
    user_id: str,
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    async def _run() -> None:
        async with get_client() as client:
            result = await client.users.delete(user_id)
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("session-list")
def user_session_list(
    user_id: str | None = typer.Option(None, "--user-id", help="Filter by user ID (admin required for other users)."),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """List active user sessions via GET /user_session_list."""

    async def _run() -> None:
        async with get_client() as client:
            sessions = await client.users.session_list(user_id=user_id)
            if as_json:
                print_result(sessions, verbose=verbose)
                return

            rows = []
            for sess in sessions:
                rows.append({
                    "user_id": sess.get("session_user_id") or sess.get("user_id"),
                    "session_id": sess.get("id"),
                    "time_expire": _human_time(sess.get("time_expire")),
                })
            print_result(rows, verbose=verbose, formatter=lambda d: print_records(d, title="User Sessions"))

    asyncio.run(_run())


@app.command("session-delete")
def user_session_delete(
    session_id: str = typer.Argument(..., help="Session ID (token) to delete."),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Delete (force-logout) a user session via DELETE /user_session_delete."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.users.session_delete(session_id)
            print_result(result, verbose=verbose)

    asyncio.run(_run())
