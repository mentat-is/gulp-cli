from __future__ import annotations

import asyncio
from typing import Any

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_json, print_records
from gulp_cli.utils import comma_split

app = typer.Typer(help="User management")


@app.command("list")
def user_list(as_json: bool = typer.Option(False, "--json", help="Output raw JSON")) -> None:
    async def _run() -> None:
        async with get_client() as client:
            users = await client.users.list()
            if as_json:
                print_json(users)
            else:
                print_records(users, title="Users")

    asyncio.run(_run())


@app.command("get")
def user_get(user_id: str) -> None:
    async def _run() -> None:
        async with get_client() as client:
            user = await client.users.get(user_id)
            print_json(user)

    asyncio.run(_run())


@app.command("create")
def user_create(
    user_id: str,
    password: str = typer.Option(..., "--password", "-p"),
    permission: str = typer.Option("read", "--permission", help="Comma-separated permissions"),
    email: str | None = typer.Option(None, "--email"),
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
            print_json(user)

    asyncio.run(_run())


@app.command("update")
def user_update(
    user_id: str,
    password: str | None = typer.Option(None, "--password", "-p"),
    permission: str | None = typer.Option(None, "--permission", help="Comma-separated permissions"),
    email: str | None = typer.Option(None, "--email"),
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
            print_json(updated)

    asyncio.run(_run())


@app.command("delete")
def user_delete(user_id: str) -> None:
    async def _run() -> None:
        async with get_client() as client:
            result = await client.users.delete(user_id)
            print_json(result)

    asyncio.run(_run())
