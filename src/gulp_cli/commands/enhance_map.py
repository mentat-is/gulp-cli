from __future__ import annotations

import asyncio

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_records, print_result
from gulp_cli.utils import parse_json_option

app = typer.Typer(help="Enhance document map management")


@app.command("create")
def enhance_map_create(
    gulp_event_code: int = typer.Argument(..., help="gulp.event_code to map"),
    plugin: str = typer.Argument(..., help="Plugin name"),
    glyph_id: str | None = typer.Option(None, "--glyph-id", help="Glyph ID to map"),
    color: str | None = typer.Option(None, "--color", help="Color to map (e.g. #ff0000)"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Create an enhance map entry for plugin+event code."""

    async def _run() -> None:
        if glyph_id is None and color is None:
            raise typer.BadParameter("At least one of --glyph-id or --color must be provided")

        async with get_client() as client:
            data = await client.plugins.enhance_map_create(
                gulp_event_code=gulp_event_code,
                plugin=plugin,
                glyph_id=glyph_id,
                color=color,
            )
            print_result(data, verbose=verbose)

    asyncio.run(_run())


@app.command("update")
def enhance_map_update(
    obj_id: str = typer.Argument(..., help="Enhance map object id"),
    glyph_id: str | None = typer.Option(None, "--glyph-id", help="New glyph ID"),
    color: str | None = typer.Option(None, "--color", help="New color"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Update an enhance map entry."""

    async def _run() -> None:
        if glyph_id is None and color is None:
            raise typer.BadParameter("At least one of --glyph-id or --color must be provided")

        async with get_client() as client:
            data = await client.plugins.enhance_map_update(
                obj_id=obj_id,
                glyph_id=glyph_id,
                color=color,
            )
            print_result(data, verbose=verbose)

    asyncio.run(_run())


@app.command("delete")
def enhance_map_delete(
    obj_id: str = typer.Argument(..., help="Enhance map object id"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Delete an enhance map entry."""

    async def _run() -> None:
        async with get_client() as client:
            data = await client.plugins.enhance_map_delete(obj_id=obj_id)
            print_result(data, verbose=verbose)

    asyncio.run(_run())


@app.command("get")
def enhance_map_get(
    obj_id: str = typer.Argument(..., help="Enhance map object id"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Get one enhance map entry by id."""

    async def _run() -> None:
        async with get_client() as client:
            data = await client.plugins.enhance_map_get(obj_id=obj_id)
            print_result(data, verbose=verbose)

    asyncio.run(_run())


@app.command("list")
def enhance_map_list(
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpCollabFilter"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """List enhance map entries, optionally filtered."""

    async def _run() -> None:
        flt_parsed = parse_json_option(flt, field_name="flt")
        async with get_client() as client:
            data = await client.plugins.enhance_map_list(flt=flt_parsed)
            print_result(
                data,
                verbose=verbose,
                formatter=lambda items: print_records(items, title="Enhance Document Maps"),
            )

    asyncio.run(_run())
