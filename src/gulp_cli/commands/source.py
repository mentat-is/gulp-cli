"""
Source management commands for Gulp CLI.
"""
from __future__ import annotations

import asyncio
from typing import Any

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_result, print_records

app = typer.Typer(help="Source management")


def _source_row(source: dict[str, Any]) -> dict[str, Any]:
    """Format source for display."""
    return dict(source)


@app.command("list")
def source_list(
    operation_id: str = typer.Argument(..., help="Operation ID"),
    context_id: str = typer.Argument(..., help="Context ID"),
) -> None:
    """List sources in a context."""
    async def _run() -> None:
        async with get_client() as client:
            sources = await client.operations.source_list(operation_id, context_id)
            items = [_source_row(src) for src in sources] if isinstance(sources, list) else [_source_row(sources)]
            print_result(
                items,
                                formatter=lambda data: print_records(data, title=f"Sources in {context_id}")
            )

    asyncio.run(_run())


@app.command("get")
def source_get(
    source_id: str = typer.Argument(..., help="Source ID"),
) -> None:
    """Get source details."""
    async def _run() -> None:
        async with get_client() as client:
            source = await client.operations.source_get(source_id)
            print_result(source.model_dump(exclude_none=True) if hasattr(source, 'model_dump') else source)

    asyncio.run(_run())


@app.command("create")
def source_create(
    operation_id: str = typer.Argument(..., help="Operation ID"),
    context_id: str = typer.Argument(..., help="Context ID"),
    source_name: str = typer.Argument(..., help="Source name"),
    plugin: str | None = typer.Option(None, "--plugin", help="Plugin name"),
    description: str | None = typer.Option(None, "--description", help="Source description"),
    color: str | None = typer.Option(None, "--color", help="Source color (hex format)"),
    glyph_id: str | None = typer.Option(None, "--glyph-id", help="Glyph ID for the source"),
    fail_if_exists: bool = typer.Option(False, "--fail-if-exists", help="Fail if source already exists"),
) -> None:
    """Create a new source in a context."""
    async def _run() -> None:
        async with get_client() as client:
            source = await client.operations.source_create(
                operation_id,
                context_id,
                source_name,
                plugin=plugin,
                description=description,
                color=color,
                glyph_id=glyph_id,
                fail_if_exists=fail_if_exists,
            )
            print_result(source.model_dump(exclude_none=True) if hasattr(source, 'model_dump') else source)

    asyncio.run(_run())


@app.command("update")
def source_update(
    source_id: str = typer.Argument(..., help="Source ID"),
    description: str | None = typer.Option(None, "--description", help="Source description"),
    color: str | None = typer.Option(None, "--color", help="Source color (hex format)"),
    glyph_id: str | None = typer.Option(None, "--glyph-id", help="Glyph ID for the source"),
) -> None:
    """Update an existing source."""
    async def _run() -> None:
        if not any([description, color, glyph_id]):
            typer.echo("Error: At least one of --description, --color, or --glyph-id must be provided", err=True)
            raise typer.Exit(1)

        async with get_client() as client:
            source = await client.operations.source_update(
                source_id,
                description=description,
                color=color,
                glyph_id=glyph_id,
            )
            print_result(source.model_dump(exclude_none=True) if hasattr(source, 'model_dump') else source)

    asyncio.run(_run())


@app.command("delete")
def source_delete(
    source_id: str = typer.Argument(..., help="Source ID"),
    delete_data: bool = typer.Option(True, "--delete-data", help="Also delete related data"),
) -> None:
    """Delete a source."""
    async def _run() -> None:
        async with get_client() as client:
            result = await client.operations.source_delete(source_id, delete_data=delete_data)
            print_result(result)

    asyncio.run(_run())
