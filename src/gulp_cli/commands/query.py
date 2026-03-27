from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_json, print_result
from gulp_cli.utils import parse_json_list_option, parse_json_option

app = typer.Typer(help="Query commands")


def _parse_json_or_text(raw: str, *, field_name: str) -> Any:
    text = raw.strip()
    if not text:
        raise typer.BadParameter(f"--{field_name} is required")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _merge_q_options_overrides(
    q_options: dict[str, Any] | None,
    *,
    preview: bool,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any] | None:
    merged = dict(q_options or {})
    if preview:
        merged["preview_mode"] = True
    if limit is not None:
        merged["limit"] = limit
    if offset is not None:
        merged["offset"] = offset
    if not merged:
        return None
    return merged


@app.command("raw")
def query_raw(
    operation_id: str,
    q: str = typer.Option(..., "--q", help="JSON object or array with OpenSearch DSL query/query list"),
    q_options: str | None = typer.Option(None, "--q-options", help="JSON object for GulpQueryParameters"),
    preview: bool = typer.Option(False, "--preview", help="Enable preview_mode in q_options (synchronous limited result set)"),
    limit: int | None = typer.Option(None, "--limit", min=1, help="Set q_options.limit"),
    offset: int | None = typer.Option(None, "--offset", min=0, help="Set q_options.offset"),
    wait: bool = typer.Option(False, "--wait"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    async def _run() -> None:
        q_parsed = parse_json_list_option(q, field_name="q")
        if not q_parsed:
            raise typer.BadParameter("--q is required")
        options = parse_json_option(q_options, field_name="q-options")
        options = _merge_q_options_overrides(
            options,
            preview=preview,
            limit=limit,
            offset=offset,
        )
        async with get_client() as client:
            result = await client.queries.query_raw(
                operation_id=operation_id,
                q=q_parsed,
                q_options=options,
                wait=wait,
            )
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("gulp")
def query_gulp(
    operation_id: str,
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpQueryFilter"),
    q_options: str | None = typer.Option(None, "--q-options", help="JSON object for GulpQueryParameters"),
    preview: bool = typer.Option(False, "--preview", help="Enable preview_mode in q_options (synchronous limited result set)"),
    limit: int | None = typer.Option(None, "--limit", min=1, help="Set q_options.limit"),
    offset: int | None = typer.Option(None, "--offset", min=0, help="Set q_options.offset"),
    wait: bool = typer.Option(False, "--wait"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    async def _run() -> None:
        flt_parsed = parse_json_option(flt, field_name="flt")
        options = parse_json_option(q_options, field_name="q-options")
        options = _merge_q_options_overrides(
            options,
            preview=preview,
            limit=limit,
            offset=offset,
        )
        async with get_client() as client:
            result = await client.queries.query_gulp(
                operation_id=operation_id,
                flt=flt_parsed,
                q_options=options,
                wait=wait,
            )
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("external")
def query_external(
    operation_id: str,
    plugin: str = typer.Option(..., "--plugin", help="External query plugin name"),
    q: str = typer.Option(..., "--q", help="External query payload (JSON or plain text)"),
    plugin_params: str = typer.Option(..., "--plugin-params", help="JSON object for GulpPluginParameters"),
    q_options: str | None = typer.Option(None, "--q-options", help="JSON object for GulpQueryParameters"),
    preview: bool = typer.Option(False, "--preview", help="Enable preview_mode in q_options (no ingest in external plugins that support it)"),
    limit: int | None = typer.Option(None, "--limit", min=1, help="Set q_options.limit"),
    offset: int | None = typer.Option(None, "--offset", min=0, help="Set q_options.offset"),
    wait: bool = typer.Option(False, "--wait"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Query an external data source through a query plugin."""

    async def _run() -> None:
        query_payload = _parse_json_or_text(q, field_name="q")
        plugin_params_parsed = parse_json_option(plugin_params, field_name="plugin-params")
        if not plugin_params_parsed:
            raise typer.BadParameter("--plugin-params is required")
        options = parse_json_option(q_options, field_name="q-options")
        options = _merge_q_options_overrides(
            options,
            preview=preview,
            limit=limit,
            offset=offset,
        )

        async with get_client() as client:
            result = await client.queries.query_external(
                operation_id=operation_id,
                q=query_payload,
                plugin=plugin,
                plugin_params=plugin_params_parsed,
                q_options=options,
                wait=wait,
            )
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("document-get-by-id")
def document_get_by_id(
    operation_id: str,
    doc_id: str,
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Get a single document by OpenSearch _id (query_single_id API)."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.queries.query_single_id(
                operation_id=operation_id,
                doc_id=doc_id,
            )
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("aggregation")
def query_aggregation(
    operation_id: str,
    q: str = typer.Option(..., "--q", help="JSON object with OpenSearch aggregation query"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Run a synchronous aggregation query."""

    async def _run() -> None:
        q_parsed = parse_json_option(q, field_name="q")
        if not q_parsed:
            raise typer.BadParameter("--q is required")
        async with get_client() as client:
            result = await client.queries.query_aggregation(
                operation_id=operation_id,
                q=q_parsed,
            )
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("history-get")
def query_history_get(
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Get the query history for the authenticated user."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.queries.query_history_get()
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("max-min-per-field")
def query_max_min_per_field(
    operation_id: str,
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpQueryFilter"),
    group_by: str | None = typer.Option(None, "--group-by", help="Optional field to group by (e.g. event.code)"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Get min/max values for timestamp/event fields, optionally grouped by a field."""

    async def _run() -> None:
        flt_parsed = parse_json_option(flt, field_name="flt")
        async with get_client() as client:
            result = await client.queries.query_max_min_per_field(
                operation_id=operation_id,
                flt=flt_parsed,
                group_by=group_by,
            )
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("gulp-export")
def query_gulp_export(
    operation_id: str,
    output: str = typer.Option(..., "--output", help="Output JSON file path"),
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpQueryFilter"),
    q_options: str | None = typer.Option(None, "--q-options", help="JSON object for GulpQueryParameters"),
    preview: bool = typer.Option(False, "--preview", help="Set q_options.preview_mode (ignored server-side by export API)"),
    limit: int | None = typer.Option(None, "--limit", min=1, help="Set q_options.limit"),
    offset: int | None = typer.Option(None, "--offset", min=0, help="Set q_options.offset"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Export query_gulp results into a JSON file (streamed download)."""

    async def _run() -> None:
        flt_parsed = parse_json_option(flt, field_name="flt")
        options = parse_json_option(q_options, field_name="q-options")
        options = _merge_q_options_overrides(
            options,
            preview=preview,
            limit=limit,
            offset=offset,
        )
        output_path = str(Path(output).expanduser())

        async with get_client() as client:
            saved_path = await client.queries.query_gulp_export_json(
                operation_id=operation_id,
                output_path=output_path,
                flt=flt_parsed,
                q_options=options,
            )
            print_result({"output_path": saved_path}, verbose=verbose)

    asyncio.run(_run())
