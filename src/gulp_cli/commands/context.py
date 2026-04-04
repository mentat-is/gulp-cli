"""
Context management commands for Gulp CLI.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_result, print_records

app = typer.Typer(help="Context management")


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _context_row(context: dict[str, Any]) -> dict[str, Any]:
    """Format context for display."""
    row = dict(context)
    sources = row.pop("sources", None)

    flattened_sources: list[dict[str, Any]] = []
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict):
                continue
            source_row = {"id": source.get("id")}
            if source.get("name") is not None:
                source_row["name"] = source.get("name")
            flattened_sources.append(source_row)

    row["sources"] = _compact_json(flattened_sources)
    return row


@app.command("list")
def context_list(
    operation_id: str = typer.Argument(..., help="Operation ID"),
) -> None:
    """List contexts in an operation."""
    async def _run() -> None:
        async with get_client() as client:
            contexts = await client.operations.context_list(operation_id)
            items = [_context_row(ctx) for ctx in contexts] if isinstance(contexts, list) else [_context_row(contexts)]
            print_result(
                items,
                                formatter=lambda data: print_records(data, title=f"Contexts in {operation_id}")
            )

    asyncio.run(_run())


@app.command("get")
def context_get(
    context_id: str = typer.Argument(..., help="Context ID"),
) -> None:
    """Get context details."""
    async def _run() -> None:
        async with get_client() as client:
            context = await client.operations.context_get(context_id)
            print_result(context.model_dump(exclude_none=True) if hasattr(context, 'model_dump') else context)

    asyncio.run(_run())


@app.command("create")
def context_create(
    operation_id: str = typer.Argument(..., help="Operation ID"),
    context_name: str = typer.Argument(..., help="Context name"),
    description: str | None = typer.Option(None, "--description", help="Context description"),
    color: str | None = typer.Option(None, "--color", help="Context color (hex format)"),
    glyph_id: str | None = typer.Option(None, "--glyph-id", help="Glyph ID for the context"),
    fail_if_exists: bool = typer.Option(False, "--fail-if-exists", help="Fail if context already exists"),
) -> None:
    """Create a new context in an operation."""
    async def _run() -> None:
        async with get_client() as client:
            context = await client.operations.context_create(
                operation_id,
                context_name,
                description=description,
                color=color,
                glyph_id=glyph_id,
                fail_if_exists=fail_if_exists,
            )
            print_result(context.model_dump(exclude_none=True) if hasattr(context, 'model_dump') else context)

    asyncio.run(_run())


@app.command("update")
def context_update(
    context_id: str = typer.Argument(..., help="Context ID"),
    description: str | None = typer.Option(None, "--description", help="Context description"),
    color: str | None = typer.Option(None, "--color", help="Context color (hex format)"),
    glyph_id: str | None = typer.Option(None, "--glyph-id", help="Glyph ID for the context"),
) -> None:
    """Update an existing context."""
    async def _run() -> None:
        if not any([description, color, glyph_id]):
            typer.echo("Error: At least one of --description, --color, or --glyph-id must be provided", err=True)
            raise typer.Exit(1)

        async with get_client() as client:
            context = await client.operations.context_update(
                context_id,
                description=description,
                color=color,
                glyph_id=glyph_id,
            )
            print_result(context.model_dump(exclude_none=True) if hasattr(context, 'model_dump') else context)

    asyncio.run(_run())


@app.command("delete")
def context_delete(
    context_id: str = typer.Argument(..., help="Context ID"),
    delete_data: bool = typer.Option(True, "--delete-data", help="Also delete related data"),
) -> None:
    """Delete a context."""
    async def _run() -> None:
        async with get_client() as client:
            result = await client.operations.context_delete(context_id, delete_data=delete_data)
            print_result(result)

    asyncio.run(_run())
