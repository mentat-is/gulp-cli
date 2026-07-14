from __future__ import annotations

import asyncio
import json
from typing import Any

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_error, print_json, print_records, print_result
from gulp_cli.utils import comma_split, parse_json_option

app = typer.Typer(help="Collaboration objects commands")
note_app = typer.Typer(help="GulpNote commands")
link_app = typer.Typer(help="GulpLink commands")
highlight_app = typer.Typer(help="GulpHighlight commands")

app.add_typer(note_app, name="note")
app.add_typer(link_app, name="link")
app.add_typer(highlight_app, name="highlight")


def _short_text(value: Any, limit: int = 100) -> str:
    if value is None:
        return "-"
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _as_compact(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return str(value)


def _note_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in records:
        rows.append(
            {
                "id": item.get("id", "-"),
                "operation_id": item.get("operation_id", "-"),
                "user_id": item.get("user_id", "-"),
                "server_id": item.get("server_id", "-"),
                "context_id": item.get("context_id", "-"),
                "source_id": item.get("source_id", "-"),
                "time_pin": item.get("time_pin", "-"),
                "text": _short_text(item.get("text")),
            }
        )
    return rows


def _link_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in records:
        rows.append(
            {
                "id": item.get("id", "-"),
                "operation_id": item.get("operation_id", "-"),
                "user_id": item.get("user_id", "-"),
                "server_id": item.get("server_id", "-"),
                "doc_id_from": item.get("doc_id_from", "-"),
                "doc_ids": _as_compact(item.get("doc_ids")),
            }
        )
    return rows


def _highlight_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in records:
        rows.append(
            {
                "id": item.get("id", "-"),
                "operation_id": item.get("operation_id", "-"),
                "user_id": item.get("user_id", "-"),
                "server_id": item.get("server_id", "-"),
                "time_range": _as_compact(item.get("time_range")),
            }
        )
    return rows


def _parse_time_range(value: str) -> list[int]:
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if len(parts) != 2:
        raise typer.BadParameter("time range must be in format START_NS,END_NS")
    try:
        start_ns = int(parts[0])
        end_ns = int(parts[1])
    except ValueError as exc:
        raise typer.BadParameter("time range values must be integers") from exc
    if end_ns < start_ns:
        raise typer.BadParameter("END_NS must be >= START_NS")
    return [start_ns, end_ns]


async def _bulk_delete(
    operation_id: str,
    obj_type: str,
    flt_raw: str | None,
    delete_all: bool,
) -> None:
    if not delete_all and not flt_raw:
        raise typer.BadParameter("Provide --flt or pass --all to delete all matching objects of this type in the operation")

    flt = parse_json_option(flt_raw, field_name="flt") or {}
    async with get_client() as client:
        deleted = await client.plugins.object_delete_bulk(
            operation_id=operation_id,
            obj_type=obj_type,
            flt=flt,
        )
        print_result(deleted)


@note_app.command("create")
def note_create(
    operation_id: str,
    context_id: str,
    source_id: str,
    name: str,
    text: str,
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    glyph_id: str | None = typer.Option(None, "--glyph-id"),
    color: str | None = typer.Option(None, "--color"),
    private: bool = typer.Option(False, "--private"),
    time_pin: int | None = typer.Option(None, "--time-pin", help="Time pin in ns (required if --doc is not provided)"),
    doc: str | None = typer.Option(None, "--doc", help="JSON object for associated document (required if --time-pin is not provided)"),
) -> None:
    async def _run() -> None:
        if time_pin is None and doc is None:
            raise typer.BadParameter("Either --time-pin or --doc must be provided")

        doc_obj = parse_json_option(doc, field_name="doc")
        async with get_client() as client:
            await client.ensure_websocket()
            created = await client.collab.note_create(
                operation_id=operation_id,
                context_id=context_id,
                source_id=source_id,
                name=name,
                text=text,
                tags=comma_split(tags),
                glyph_id=glyph_id,
                color=color,
                private=private,
                time_pin=time_pin,
                doc=doc_obj,
            )
            print_result(created)

    asyncio.run(_run())


@note_app.command("update")
def note_update(
    obj_id: str,
    name: str | None = typer.Option(None, "--name"),
    text: str | None = typer.Option(None, "--text"),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    glyph_id: str | None = typer.Option(None, "--glyph-id"),
    color: str | None = typer.Option(None, "--color"),
    time_pin: int | None = typer.Option(None, "--time-pin", help="Time pin in ns"),
    doc: str | None = typer.Option(None, "--doc", help="JSON object for associated document"),
) -> None:
    async def _run() -> None:
        if all(
            val is None
            for val in [name, text, tags, glyph_id, color, time_pin, doc]
        ):
            print_error("No update fields provided")
            raise typer.Exit(1)

        doc_obj = parse_json_option(doc, field_name="doc")
        parsed_tags = comma_split(tags) if tags is not None else None

        async with get_client() as client:
            await client.ensure_websocket()
            updated = await client.collab.note_update(
                obj_id=obj_id,
                name=name,
                text=text,
                tags=parsed_tags,
                glyph_id=glyph_id,
                color=color,
                time_pin=time_pin,
                doc=doc_obj,
            )
            print_result(updated)

    asyncio.run(_run())


@note_app.command("delete")
def note_delete(
    obj_id: str,
) -> None:
    async def _run() -> None:
        async with get_client() as client:
            await client.ensure_websocket()
            deleted = await client.collab.note_delete(obj_id=obj_id)
            print_result(deleted)

    asyncio.run(_run())


@note_app.command("delete-bulk")
def note_delete_bulk(
    operation_id: str,
    flt: str | None = typer.Option(None, "--flt", help="GulpCollabFilter JSON object"),
    delete_all: bool = typer.Option(False, "--all", help="Delete all notes in the operation (dangerous)"),
) -> None:
    asyncio.run(_bulk_delete(operation_id, "note", flt, delete_all))


@note_app.command("list")
def note_list(
    operation_id: str,
) -> None:
    async def _run() -> None:
        async with get_client() as client:
            records = await client.collab.note_list(operation_id=operation_id)
            print_result(records, formatter=lambda d: print_records(_note_rows(d), title="Notes"))

    asyncio.run(_run())


@link_app.command("create")
def link_create(
    operation_id: str,
    doc_id_from: str,
    doc_ids: str = typer.Option(..., "--doc-ids", help="Comma-separated target document IDs"),
    name: str | None = typer.Option(None, "--name"),
    description: str | None = typer.Option(None, "--description"),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    glyph_id: str | None = typer.Option(None, "--glyph-id"),
    color: str | None = typer.Option(None, "--color"),
    private: bool = typer.Option(False, "--private"),
) -> None:
    async def _run() -> None:
        parsed_doc_ids = comma_split(doc_ids)
        if not parsed_doc_ids:
            raise typer.BadParameter("--doc-ids must contain at least one document id")

        async with get_client() as client:
            await client.ensure_websocket()
            created = await client.collab.link_create(
                operation_id=operation_id,
                doc_id_from=doc_id_from,
                doc_ids=parsed_doc_ids,
                name=name,
                description=description,
                tags=comma_split(tags),
                glyph_id=glyph_id,
                color=color,
                private=private,
            )
            print_result(created)

    asyncio.run(_run())


@link_app.command("update")
def link_update(
    obj_id: str,
    name: str | None = typer.Option(None, "--name"),
    description: str | None = typer.Option(None, "--description"),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    glyph_id: str | None = typer.Option(None, "--glyph-id"),
    color: str | None = typer.Option(None, "--color"),
    doc_ids: str | None = typer.Option(None, "--doc-ids", help="Comma-separated target document IDs"),
) -> None:
    async def _run() -> None:
        if all(
            val is None
            for val in [name, description, tags, glyph_id, color, doc_ids]
        ):
            print_error("No update fields provided")
            raise typer.Exit(1)

        parsed_doc_ids = comma_split(doc_ids) if doc_ids is not None else None
        parsed_tags = comma_split(tags) if tags is not None else None

        async with get_client() as client:
            await client.ensure_websocket()
            updated = await client.collab.link_update(
                obj_id=obj_id,
                name=name,
                description=description,
                tags=parsed_tags,
                glyph_id=glyph_id,
                color=color,
                doc_ids=parsed_doc_ids,
            )
            print_result(updated)

    asyncio.run(_run())


@link_app.command("delete")
def link_delete(
    obj_id: str,
) -> None:
    async def _run() -> None:
        async with get_client() as client:
            await client.ensure_websocket()
            deleted = await client.collab.link_delete(obj_id=obj_id)
            print_result(deleted)

    asyncio.run(_run())


@link_app.command("delete-bulk")
def link_delete_bulk(
    operation_id: str,
    flt: str | None = typer.Option(None, "--flt", help="GulpCollabFilter JSON object"),
    delete_all: bool = typer.Option(False, "--all", help="Delete all links in the operation (dangerous)"),
) -> None:
    asyncio.run(_bulk_delete(operation_id, "link", flt, delete_all))


@link_app.command("list")
def link_list(
    operation_id: str,
) -> None:
    async def _run() -> None:
        async with get_client() as client:
            records = await client.collab.link_list(operation_id=operation_id)
            print_result(records, formatter=lambda d: print_records(_link_rows(d), title="Links"))

    asyncio.run(_run())


@highlight_app.command("create")
def highlight_create(
    operation_id: str,
    time_range: str = typer.Option(..., "--time-range", help="START_NS,END_NS"),
    name: str | None = typer.Option(None, "--name"),
    description: str | None = typer.Option(None, "--description"),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    glyph_id: str | None = typer.Option(None, "--glyph-id"),
    color: str | None = typer.Option(None, "--color"),
    private: bool = typer.Option(False, "--private"),
) -> None:
    async def _run() -> None:
        parsed_range = _parse_time_range(time_range)
        async with get_client() as client:
            await client.ensure_websocket()
            created = await client.collab.highlight_create(
                operation_id=operation_id,
                time_range=parsed_range,
                name=name,
                description=description,
                tags=comma_split(tags),
                glyph_id=glyph_id,
                color=color,
                private=private,
            )
            print_result(created)

    asyncio.run(_run())


@highlight_app.command("update")
def highlight_update(
    obj_id: str,
    name: str | None = typer.Option(None, "--name"),
    description: str | None = typer.Option(None, "--description"),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    glyph_id: str | None = typer.Option(None, "--glyph-id"),
    color: str | None = typer.Option(None, "--color"),
    time_range: str | None = typer.Option(None, "--time-range", help="START_NS,END_NS"),
) -> None:
    async def _run() -> None:
        if all(
            val is None
            for val in [name, description, tags, glyph_id, color, time_range]
        ):
            print_error("No update fields provided")
            raise typer.Exit(1)

        parsed_range = _parse_time_range(time_range) if time_range is not None else None
        parsed_tags = comma_split(tags) if tags is not None else None

        async with get_client() as client:
            await client.ensure_websocket()
            updated = await client.collab.highlight_update(
                obj_id=obj_id,
                name=name,
                description=description,
                tags=parsed_tags,
                glyph_id=glyph_id,
                color=color,
                time_range=parsed_range,
            )
            print_result(updated)

    asyncio.run(_run())


@highlight_app.command("delete")
def highlight_delete(
    obj_id: str,
) -> None:
    async def _run() -> None:
        async with get_client() as client:
            await client.ensure_websocket()
            deleted = await client.collab.highlight_delete(obj_id=obj_id)
            print_result(deleted)

    asyncio.run(_run())


@highlight_app.command("delete-bulk")
def highlight_delete_bulk(
    operation_id: str,
    flt: str | None = typer.Option(None, "--flt", help="GulpCollabFilter JSON object"),
    delete_all: bool = typer.Option(False, "--all", help="Delete all highlights in the operation (dangerous)"),
) -> None:
        asyncio.run(_bulk_delete(operation_id, "highlight", flt, delete_all))


@highlight_app.command("list")
def highlight_list(
    operation_id: str,
) -> None:
    async def _run() -> None:
        async with get_client() as client:
            records = await client.collab.highlight_list(operation_id=operation_id)
            print_result(records, formatter=lambda d: print_records(_highlight_rows(d), title="Highlights"))

    asyncio.run(_run())
