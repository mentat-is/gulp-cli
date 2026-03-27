from __future__ import annotations

import asyncio
from typing import Any

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_json, print_records, print_result
from gulp_cli.utils import comma_split, parse_json_option

app = typer.Typer(help="User group management (admin required)")


@app.command("list")
def group_list(
    flt: str | None = typer.Option(None, "--flt", help="GulpCollabFilter JSON"),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """List user groups."""

    async def _run() -> None:
        flt_obj = parse_json_option(flt, field_name="flt")
        async with get_client() as client:
            groups = await client.user_groups.list(flt=flt_obj)
            if as_json:
                print_result(groups, verbose=verbose)
            else:
                print_result(groups, verbose=verbose, formatter=lambda d: print_records(d, title="User Groups"))

    asyncio.run(_run())


@app.command("get")
def group_get(
    group_id: str,
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Get a user group by ID."""

    async def _run() -> None:
        async with get_client() as client:
            group = await client.user_groups.get(group_id)
            print_result(group, verbose=verbose)

    asyncio.run(_run())


@app.command("create")
def group_create(
    name: str,
    permission: str = typer.Option(..., "--permission", help="Comma-separated permissions (read, edit, ingest, admin)"),
    description: str | None = typer.Option(None, "--description", "-d"),
    glyph_id: str | None = typer.Option(None, "--glyph-id"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Create a user group."""

    async def _run() -> None:
        perms = comma_split(permission)
        if not perms:
            raise typer.BadParameter("At least one permission is required")
        async with get_client() as client:
            group = await client.user_groups.create(
                name=name,
                permission=perms,
                description=description,
                glyph_id=glyph_id,
            )
            print_result(group, verbose=verbose)

    asyncio.run(_run())


@app.command("update")
def group_update(
    group_id: str,
    permission: str | None = typer.Option(None, "--permission", help="Comma-separated permissions to replace"),
    description: str | None = typer.Option(None, "--description", "-d"),
    glyph_id: str | None = typer.Option(None, "--glyph-id"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Update a user group's properties."""

    async def _run() -> None:
        if not any([permission, description, glyph_id]):
            raise typer.BadParameter("At least one of --permission, --description, --glyph-id must be provided")
        kwargs: dict[str, Any] = {}
        if permission is not None:
            kwargs["permission"] = comma_split(permission)
        if description is not None:
            kwargs["description"] = description
        if glyph_id is not None:
            kwargs["glyph_id"] = glyph_id
        async with get_client() as client:
            group = await client.user_groups.update(group_id, **kwargs)
            print_result(group, verbose=verbose)

    asyncio.run(_run())


@app.command("delete")
def group_delete(
    group_id: str,
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Delete a user group (users are NOT deleted)."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.user_groups.delete(group_id)
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("add-user")
def group_add_user(group_id: str, user_id: str,
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Add a user to a group."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.user_groups.add_user(group_id, user_id)
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("remove-user")
def group_remove_user(group_id: str, user_id: str,
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Remove a user from a group."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.user_groups.remove_user(group_id, user_id)
            print_result(result, verbose=verbose)

    asyncio.run(_run())
