from __future__ import annotations

import asyncio
from typing import Any

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_result
from gulp_cli.utils import comma_split, parse_json_option

app = typer.Typer(help="Enrichment and tagging commands")


@app.command("tag")
def enrich_tag(
    operation_id: str,
    tags: list[str] = typer.Option(..., "--tag", help="Tag to add (repeatable)"),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpQueryFilter"
    ),
    wait: bool = typer.Option(False, "--wait", help="Wait for the async job to finish"),
) -> None:
    """Add tags to documents matching a filter."""

    async def _run() -> None:
        flt_parsed = parse_json_option(flt, field_name="flt")
        async with get_client() as client:
            result = await client.enrich.tag_documents(
                operation_id=operation_id,
                tags=tags,
                flt=flt_parsed,
                wait=wait,
            )
            print_result(result)

    asyncio.run(_run())


@app.command("untag")
def enrich_untag(
    operation_id: str,
    tags: list[str] = typer.Option(..., "--tag", help="Tag to remove (repeatable)"),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpQueryFilter"
    ),
    wait: bool = typer.Option(False, "--wait", help="Wait for the async job to finish"),
) -> None:
    """Remove tags from documents matching a filter."""

    async def _run() -> None:
        flt_parsed = parse_json_option(flt, field_name="flt")
        async with get_client() as client:
            result = await client.enrich.untag_documents(
                operation_id=operation_id,
                tags=tags,
                flt=flt_parsed,
                wait=wait,
            )
            print_result(result)

    asyncio.run(_run())


@app.command("update")
def enrich_update(
    operation_id: str,
    fields: str = typer.Option(..., "--fields", help="JSON object of field updates"),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpQueryFilter"
    ),
    wait: bool = typer.Option(False, "--wait", help="Wait for the async job to finish"),
) -> None:
    """Update fields on documents matching a filter."""

    async def _run() -> None:
        fields_parsed = parse_json_option(fields, field_name="fields")
        if fields_parsed is None:
            raise typer.BadParameter("--fields is required")
        flt_parsed = parse_json_option(flt, field_name="flt")
        async with get_client() as client:
            result = await client.enrich.update_documents(
                operation_id=operation_id,
                fields=fields_parsed,
                flt=flt_parsed,
                wait=wait,
            )
            print_result(result)

    asyncio.run(_run())


@app.command("remove")
def enrich_remove(
    operation_id: str,
    fields: str = typer.Option(
        ..., "--fields", help="Comma-separated field names to remove"
    ),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpQueryFilter"
    ),
    wait: bool = typer.Option(False, "--wait", help="Wait for the async job to finish"),
) -> None:
    """Remove enrichment markers or specific fields from documents matching a filter."""

    async def _run() -> None:
        flt_parsed = parse_json_option(flt, field_name="flt")
        field_names = comma_split(fields)
        async with get_client() as client:
            result = await client.enrich.enrich_remove(
                operation_id=operation_id,
                fields=field_names or None,
                flt=flt_parsed,
                wait=wait,
            )
            print_result(result)

    asyncio.run(_run())


@app.command("documents")
def enrich_documents(
    operation_id: str,
    plugin: str = typer.Option(..., "--plugin", help="Enrichment plugin name"),
    fields: str | None = typer.Option(
        None, "--fields", help="JSON object of fields to enrich"
    ),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpQueryFilter"
    ),
    plugin_params: str | None = typer.Option(
        None, "--plugin-params", help="JSON object for GulpPluginParameters"
    ),
    wait: bool = typer.Option(False, "--wait", help="Wait for the async job to finish"),
) -> None:
    """Run an enrichment plugin on documents matching a filter."""

    async def _run() -> None:
        fields_parsed = parse_json_option(fields, field_name="fields")
        flt_parsed = parse_json_option(flt, field_name="flt")
        plugin_params_parsed = parse_json_option(
            plugin_params, field_name="plugin-params"
        )
        async with get_client() as client:
            result = await client.enrich.enrich_documents(
                operation_id=operation_id,
                plugin=plugin,
                fields=fields_parsed,
                flt=flt_parsed,
                plugin_params=plugin_params_parsed,
                wait=wait,
            )
            print_result(result)

    asyncio.run(_run())


@app.command("single-id")
def enrich_single_id(
    operation_id: str,
    doc_id: str,
    plugin: str = typer.Option(..., "--plugin", help="Enrichment plugin name"),
    fields: str | None = typer.Option(
        None, "--fields", help="JSON object of fields to enrich"
    ),
    plugin_params: str | None = typer.Option(
        None, "--plugin-params", help="JSON object for GulpPluginParameters"
    ),
) -> None:
    """Enrich a single document by OpenSearch document ID."""

    async def _run() -> None:
        fields_parsed = parse_json_option(fields, field_name="fields")
        plugin_params_parsed = parse_json_option(
            plugin_params, field_name="plugin-params"
        )
        async with get_client() as client:
            result = await client.enrich.enrich_single_id(
                operation_id=operation_id,
                doc_id=doc_id,
                plugin=plugin,
                fields=fields_parsed,
                plugin_params=plugin_params_parsed,
            )
            print_result(result)

    asyncio.run(_run())
