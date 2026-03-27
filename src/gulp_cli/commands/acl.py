from __future__ import annotations

import asyncio

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_json, print_result

app = typer.Typer(help="Object ACL management (owner or admin required)")


@app.command("add-user")
def acl_add_user(
    obj_id: str,
    obj_type: str = typer.Option(..., "--obj-type", help="Object collab type (e.g. note, operation, link, ...)"),
    user_id: str = typer.Option(..., "--user-id", help="User ID to grant access"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Grant a user access to an object."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.acl.add_granted_user(obj_id, obj_type, user_id)
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("remove-user")
def acl_remove_user(
    obj_id: str,
    obj_type: str = typer.Option(..., "--obj-type", help="Object collab type (e.g. note, operation, link, ...)"),
    user_id: str = typer.Option(..., "--user-id", help="User ID to revoke access"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Revoke a user's access to an object."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.acl.remove_granted_user(obj_id, obj_type, user_id)
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("add-group")
def acl_add_group(
    obj_id: str,
    obj_type: str = typer.Option(..., "--obj-type", help="Object collab type (e.g. note, operation, link, ...)"),
    group_id: str = typer.Option(..., "--group-id", help="Group ID to grant access"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Grant a group access to an object."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.acl.add_granted_group(obj_id, obj_type, group_id)
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("remove-group")
def acl_remove_group(
    obj_id: str,
    obj_type: str = typer.Option(..., "--obj-type", help="Object collab type (e.g. note, operation, link, ...)"),
    group_id: str = typer.Option(..., "--group-id", help="Group ID to revoke access"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Revoke a group's access to an object."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.acl.remove_granted_group(obj_id, obj_type, group_id)
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("make-private")
def acl_make_private(
    obj_id: str,
    obj_type: str = typer.Option(..., "--obj-type", help="Object collab type (e.g. note, operation, link, ...)"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Make an object private (only owner/admin can access it)."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.acl.make_private(obj_id, obj_type)
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("make-public")
def acl_make_public(
    obj_id: str,
    obj_type: str = typer.Option(..., "--obj-type", help="Object collab type (e.g. note, operation, link, ...)"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Make an object public (accessible by everyone; clears all explicit grants)."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.acl.make_public(obj_id, obj_type)
            print_result(result, verbose=verbose)

    asyncio.run(_run())
