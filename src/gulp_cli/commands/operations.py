from __future__ import annotations

import asyncio

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_json, print_records

app = typer.Typer(help="Operation management")


@app.command("list")
def operation_list(limit: int = typer.Option(100, "--limit", min=1, max=1000)) -> None:
    async def _run() -> None:
        async with get_client() as client:
            items = []
            async for op in client.operations.list(limit=limit):
                items.append(op.model_dump(exclude_none=True))
            print_records(items, title="Operations")

    asyncio.run(_run())


@app.command("get")
def operation_get(operation_id: str) -> None:
    async def _run() -> None:
        async with get_client() as client:
            operation = await client.operations.get(operation_id)
            print_json(operation.model_dump(exclude_none=True))

    asyncio.run(_run())


@app.command("create")
def operation_create(name: str, description: str | None = typer.Option(None, "--description")) -> None:
    async def _run() -> None:
        async with get_client() as client:
            operation = await client.operations.create(name, description=description)
            print_json(operation.model_dump(exclude_none=True))

    asyncio.run(_run())


@app.command("update")
def operation_update(operation_id: str, description: str = typer.Option(..., "--description")) -> None:
    async def _run() -> None:
        async with get_client() as client:
            operation = await client.operations.update(operation_id, description=description)
            print_json(operation.model_dump(exclude_none=True))

    asyncio.run(_run())


@app.command("delete")
def operation_delete(operation_id: str) -> None:
    async def _run() -> None:
        async with get_client() as client:
            ok = await client.operations.delete(operation_id)
            print_json({"id": operation_id, "deleted": ok})

    asyncio.run(_run())
