"""
Plugin management commands for Gulp CLI.
"""
from __future__ import annotations

import asyncio
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
                                formatter=lambda data: print_records(data, title="Installed Plugins")
            )

    asyncio.run(_run())


@app.command("list-ui")
def plugin_list_ui(
) -> None:
    """List all available UI plugins."""
    async def _run() -> None:
        async with get_client() as client:
            plugins = await client.plugins.list_ui()
            items = [_plugin_row(p) for p in plugins]
            print_result(
                items,
                                formatter=lambda data: print_records(data, title="Available UI Plugins")
            )

    asyncio.run(_run())
