"""
Mapping file management commands for Gulp CLI.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_result, print_records

app = typer.Typer(help="Mapping file management")


def _mapping_row(mapping: dict[str, Any]) -> dict[str, Any]:
    """Format mapping for display."""
    row = dict(mapping)
    # Simplify for display
    if "metadata" in row and isinstance(row["metadata"], dict):
        row["plugins"] = ", ".join(row["metadata"].get("plugin", []))
    row.pop("metadata", None)
    if isinstance(row.get("mapping_ids"), list):
        row["mapping_ids"] = ", ".join(row["mapping_ids"])
    return row


@app.command("list")
def mapping_list(
) -> None:
    """List all available mapping files."""
    async def _run() -> None:
        async with get_client() as client:
            mappings = await client.plugins.mapping_list()
            items = [_mapping_row(m) for m in mappings]
            print_result(
                items,
                                formatter=lambda data: print_records(data, title="Available Mapping Files")
            )

    asyncio.run(_run())


@app.command("upload")
def mapping_upload(
    file_path: str = typer.Argument(..., help="Path to the mapping .json file"),
    fail_if_exists: bool = typer.Option(
        False, "--fail-if-exists", help="Fail if mapping file already exists"
    ),
) -> None:
    """Upload a mapping file."""
    async def _run() -> None:
        # Check file exists
        p = Path(file_path)
        if not p.exists():
            typer.echo(f"Error: File not found: {file_path}", err=True)
            raise typer.Exit(1)

        async with get_client() as client:
            result = await client.plugins.mapping_upload(
                file_path,
                fail_if_exists=fail_if_exists,
            )
            print_result(result)

    asyncio.run(_run())


@app.command("delete")
def mapping_delete(
    filename: str = typer.Argument(..., help="Mapping filename to delete, e.g., 'custom_mapping.json'"),
) -> None:
    """Delete a mapping file."""
    async def _run() -> None:
        async with get_client() as client:
            result = await client.plugins.mapping_delete(filename)
            print_result(result)

    asyncio.run(_run())


@app.command("download")
def mapping_download(
    filename: str = typer.Argument(..., help="Mapping filename to download, e.g., 'windows.json'"),
    output_path: str = typer.Argument(..., help="Local path to save the mapping file"),
) -> None:
    """Download a mapping file."""
    async def _run() -> None:
        async with get_client() as client:
            result = await client.plugins.mapping_download(filename, output_path)
            data = {"file": result}
            print_result(data)

    asyncio.run(_run())
