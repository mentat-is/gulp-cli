from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_records, print_result
from gulp_cli.utils import parse_json_option

app = typer.Typer(help="Glyph management")


@app.command("create")
def glyph_create(
    img_path: str | None = typer.Option(None, "--img-path", help="Local path to glyph image (max 16kb)"),
    name: str | None = typer.Option(None, "--name", help="Glyph name"),
    private: bool = typer.Option(False, "--private", help="Create a private glyph"),
) -> None:
    """Create a glyph from an image, or create by name only."""

    async def _run() -> None:
        if img_path is None and name is None:
            raise typer.BadParameter("At least one of --img-path or --name must be provided")

        async with get_client() as client:
            if img_path is not None:
                path = Path(img_path)
                if not path.exists():
                    raise typer.BadParameter(f"Image file not found: {img_path}")
                data = await client.collab.glyph_create(img_path=img_path, name=name, private=private)
            else:
                params = {"name": name, "private": private}
                response = await client._request("POST", "/glyph_create", params=params)
                data = response.get("data", {})

            print_result(data)

    asyncio.run(_run())


@app.command("update")
def glyph_update(
    obj_id: str = typer.Argument(..., help="Glyph object id"),
    name: str | None = typer.Option(None, "--name", help="New glyph name"),
    img_path: str | None = typer.Option(None, "--img-path", help="New image path (max 16kb)"),
) -> None:
    """Update an existing glyph."""

    async def _run() -> None:
        if name is None and img_path is None:
            raise typer.BadParameter("At least one of --name or --img-path must be provided")

        if img_path is not None:
            path = Path(img_path)
            if not path.exists():
                raise typer.BadParameter(f"Image file not found: {img_path}")

        async with get_client() as client:
            data = await client.collab.glyph_update(
                obj_id=obj_id,
                name=name,
                img_path=img_path,
            )
            print_result(data)

    asyncio.run(_run())


@app.command("delete")
def glyph_delete(
    obj_id: str = typer.Argument(..., help="Glyph object id"),
) -> None:
    """Delete a glyph."""

    async def _run() -> None:
        async with get_client() as client:
            data = await client.collab.glyph_delete(obj_id=obj_id)
            print_result(data)

    asyncio.run(_run())


@app.command("get")
def glyph_get(
    obj_id: str = typer.Argument(..., help="Glyph object id"),
) -> None:
    """Get one glyph by id."""

    async def _run() -> None:
        async with get_client() as client:
            data = await client.collab.glyph_get_by_id(obj_id=obj_id)
            print_result(data)

    asyncio.run(_run())


@app.command("list")
def glyph_list(
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpCollabFilter"),
) -> None:
    """List glyphs, optionally filtered."""

    async def _run() -> None:
        flt_parsed = parse_json_option(flt, field_name="flt")
        async with get_client() as client:
            data = await client.collab.glyph_list(flt=flt_parsed)
            print_result(
                data,
                                formatter=lambda items: print_records(items, title="Glyphs"),
            )

    asyncio.run(_run())
