"""
Plugin management commands for Gulp CLI.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_result, print_records

app = typer.Typer(help="Plugin management")


def _matches_plugin_type(plugin: dict[str, Any], plugin_type: str) -> bool:
    raw_types = plugin.get("type")

    if isinstance(raw_types, str):
        normalized = {raw_types.strip().lower()}
    elif isinstance(raw_types, list):
        normalized = {str(t).strip().lower() for t in raw_types}
    else:
        return False

    wanted = plugin_type.strip().lower()

    # Backward-compatible alias: some datasets expose external plugins as "query".
    if wanted == "external":
        return "external" in normalized or "query" in normalized
    return wanted in normalized


def _plugin_row(plugin: dict[str, Any]) -> dict[str, Any]:
    """Format plugin for display."""
    row = dict(plugin)
    # Simplify for display
    row.pop("data", None)
    row.pop("custom_parameters", None)
    row.pop("depends_on", None)
    row.pop("tags", None)
    return row


@app.command("list")
def plugin_list(
    plugin_type: Literal["extension", "external", "ingestion", "enrichment"] | None = typer.Option(
        None,
        "--plugin-type",
        help="Filter by functional plugin type",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """List all available plugins."""
    async def _run() -> None:
        async with get_client() as client:
            plugins = await client.plugins.list()
            if plugin_type is not None:
                plugins = [p for p in plugins if _matches_plugin_type(p, plugin_type)]
            items = [_plugin_row(p) for p in plugins]
            print_result(
                items,
                verbose=verbose,
                formatter=lambda data: print_records(data, title="Installed Plugins")
            )

    asyncio.run(_run())


@app.command("list-ui")
def plugin_list_ui(
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """List all available UI plugins."""
    async def _run() -> None:
        async with get_client() as client:
            plugins = await client.plugins.list_ui()
            items = [_plugin_row(p) for p in plugins]
            print_result(
                items,
                verbose=verbose,
                formatter=lambda data: print_records(data, title="Available UI Plugins")
            )

    asyncio.run(_run())


@app.command("upload")
def plugin_upload(
    file_path: str = typer.Argument(..., help="Path to the plugin .py file"),
    plugin_type: Literal["default", "extension", "ui"] = typer.Option(
        "default", "--type", help="Plugin type category"
    ),
    fail_if_exists: bool = typer.Option(
        False, "--fail-if-exists", help="Fail if plugin file already exists"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Upload a plugin file."""
    async def _run() -> None:
        # Check file exists
        p = Path(file_path)
        if not p.exists():
            typer.echo(f"Error: File not found: {file_path}", err=True)
            raise typer.Exit(1)

        async with get_client() as client:
            result = await client.plugins.upload(
                file_path,
                plugin_type=plugin_type,
                fail_if_exists=fail_if_exists,
            )
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("delete")
def plugin_delete(
    filename: str = typer.Argument(..., help="Plugin filename to delete, e.g., 'my_plugin.py'"),
    plugin_type: Literal["default", "extension", "ui"] = typer.Option(
        "default", "--type", help="Plugin type category"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Delete a plugin file."""
    async def _run() -> None:
        async with get_client() as client:
            result = await client.plugins.delete(filename, plugin_type=plugin_type)
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("download")
def plugin_download(
    filename: str = typer.Argument(..., help="Plugin filename to download, e.g., 'my_plugin.py'"),
    output_path: str = typer.Argument(..., help="Local path to save the plugin"),
    plugin_type: Literal["default", "extension", "ui"] = typer.Option(
        "default", "--type", help="Plugin type category"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Download a plugin file."""
    async def _run() -> None:
        async with get_client() as client:
            result = await client.plugins.download(
                filename,
                output_path,
                plugin_type=plugin_type,
            )
            data = {"file": result}
            print_result(data, verbose=verbose)

    asyncio.run(_run())
