from __future__ import annotations

import asyncio
from typing import Any

import typer

from gulp_cli.extension_helpers import call_custom_endpoint
from gulp_cli.output import print_records, print_result
from gulp_cli.utils import comma_split, parse_json_option


def _required_csv(raw: str, *, field_name: str) -> list[str]:
    values = comma_split(raw)
    if not values:
        raise typer.BadParameter(
            f"--{field_name} must contain at least one value",
            param_hint=f"--{field_name}",
        )
    return values


def _optional_csv(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return comma_split(raw)


def _story_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in records:
        rows.append(
            {
                "id": item.get("id", "-"),
                "name": item.get("name", "-"),
                "operation_id": item.get("operation_id", "-"),
                "entries": len(item.get("entries") or []),
                "highlights": len(item.get("highlights") or []),
                "user_id": item.get("user_id", "-"),
                "private": item.get("private", False),
            }
        )
    return rows


def register_extension(
    *,
    command_groups: dict[str, typer.Typer],
    get_client: Any,
    **_: Any,
) -> None:
    collab_app = command_groups.get("collab")
    if collab_app is None:
        raise RuntimeError("Collab command group not available")

    story_app = typer.Typer(help="Extension story commands")
    collab_app.add_typer(
        story_app,
        name="story",
        rich_help_panel="Extension Commands",
    )

    @story_app.command("create", rich_help_panel="Extension Commands")
    def story_create(
        operation_id: str,
        name: str = typer.Option(..., "--name", help="Story title"),
        doc_ids: str = typer.Option(
            ...,
            "--doc-ids",
            help="Comma-separated target document IDs",
        ),
        highlight_ids: str | None = typer.Option(
            None,
            "--highlight-ids",
            help="Comma-separated highlight IDs",
        ),
        include_whole_documents: bool = typer.Option(
            False,
            "--include-whole-documents",
            help="Include full document fields in story entries",
        ),
        description: str | None = typer.Option(None, "--description"),
        tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
        glyph_id: str | None = typer.Option(None, "--glyph-id"),
        color: str | None = typer.Option(None, "--color"),
        private: bool = typer.Option(False, "--private"),
        req_id: str | None = typer.Option(None, "--req-id"),
        wait: bool = typer.Option(False, "--wait", help="Wait for completion when request is async"),
        timeout: int = typer.Option(120, "--timeout", min=0, help="Wait timeout in seconds (0 means no timeout)"),
        verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
    ) -> None:
        """Extension: create a story object."""

        async def _run() -> None:
            payload: dict[str, Any] = {
                "doc_ids": _required_csv(doc_ids, field_name="doc-ids"),
            }
            parsed_highlights = _optional_csv(highlight_ids)
            if parsed_highlights is not None:
                payload["highlight_ids"] = parsed_highlights
            if description is not None:
                payload["description"] = description
            parsed_tags = _optional_csv(tags)
            if parsed_tags is not None:
                payload["tags"] = parsed_tags

            async with get_client() as client:
                params: dict[str, Any] = {
                    "operation_id": operation_id,
                    "ws_id": client.ws_id,
                    "name": name,
                    "include_whole_documents": include_whole_documents,
                    "private": private,
                }
                if glyph_id is not None:
                    params["glyph_id"] = glyph_id
                if color is not None:
                    params["color"] = color
                if req_id is not None:
                    params["req_id"] = req_id

                result = await call_custom_endpoint(
                    client,
                    method="POST",
                    path="/story_create",
                    params=params,
                    json_body=payload,
                    ensure_websocket=True,
                    wait=wait,
                    timeout=timeout,
                )
                print_result(result, verbose=verbose)

        asyncio.run(_run())

    @story_app.command("update", rich_help_panel="Extension Commands")
    def story_update(
        obj_id: str,
        name: str | None = typer.Option(None, "--name"),
        doc_ids: str | None = typer.Option(None, "--doc-ids", help="Comma-separated target document IDs"),
        highlight_ids: str | None = typer.Option(None, "--highlight-ids", help="Comma-separated highlight IDs"),
        include_whole_documents: bool = typer.Option(False, "--include-whole-documents", help="Include full document fields in story entries"),
        description: str | None = typer.Option(None, "--description"),
        tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
        glyph_id: str | None = typer.Option(None, "--glyph-id"),
        color: str | None = typer.Option(None, "--color"),
        req_id: str | None = typer.Option(None, "--req-id"),
        wait: bool = typer.Option(False, "--wait", help="Wait for completion when request is async"),
        timeout: int = typer.Option(120, "--timeout", min=0, help="Wait timeout in seconds (0 means no timeout)"),
        verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
    ) -> None:
        """Extension: update an existing story."""

        async def _run() -> None:
            has_update = any(
                value is not None
                for value in [
                    name,
                    doc_ids,
                    highlight_ids,
                    description,
                    tags,
                    glyph_id,
                    color,
                ]
            )
            if not has_update:
                raise typer.BadParameter(
                    "Provide at least one update field (--name/--doc-ids/--highlight-ids/--description/--tags/--glyph-id/--color)"
                )

            payload: dict[str, Any] = {}
            if doc_ids is not None:
                payload["doc_ids"] = _required_csv(doc_ids, field_name="doc-ids")
            parsed_highlights = _optional_csv(highlight_ids)
            if parsed_highlights is not None:
                payload["highlight_ids"] = parsed_highlights
            if description is not None:
                payload["description"] = description
            parsed_tags = _optional_csv(tags)
            if parsed_tags is not None:
                payload["tags"] = parsed_tags

            async with get_client() as client:
                params: dict[str, Any] = {
                    "obj_id": obj_id,
                    "ws_id": client.ws_id,
                    "include_whole_documents": include_whole_documents,
                }
                if name is not None:
                    params["name"] = name
                if glyph_id is not None:
                    params["glyph_id"] = glyph_id
                if color is not None:
                    params["color"] = color
                if req_id is not None:
                    params["req_id"] = req_id

                result = await call_custom_endpoint(
                    client,
                    method="PATCH",
                    path="/story_update",
                    params=params,
                    json_body=payload,
                    ensure_websocket=True,
                    wait=wait,
                    timeout=timeout,
                )
                print_result(result, verbose=verbose)

        asyncio.run(_run())

    @story_app.command("delete", rich_help_panel="Extension Commands")
    def story_delete(
        obj_id: str,
        req_id: str | None = typer.Option(None, "--req-id"),
        wait: bool = typer.Option(False, "--wait", help="Wait for completion when request is async"),
        timeout: int = typer.Option(120, "--timeout", min=0, help="Wait timeout in seconds (0 means no timeout)"),
        verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
    ) -> None:
        """Extension: delete a story by id."""

        async def _run() -> None:
            async with get_client() as client:
                params: dict[str, Any] = {
                    "obj_id": obj_id,
                    "ws_id": client.ws_id,
                }
                if req_id is not None:
                    params["req_id"] = req_id

                result = await call_custom_endpoint(
                    client,
                    method="DELETE",
                    path="/story_delete",
                    params=params,
                    ensure_websocket=True,
                    wait=wait,
                    timeout=timeout,
                )
                print_result(result, verbose=verbose)

        asyncio.run(_run())

    @story_app.command("get", rich_help_panel="Extension Commands")
    def story_get(
        operation_id: str,
        obj_id: str,
        req_id: str | None = typer.Option(None, "--req-id"),
        verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
    ) -> None:
        """Extension: get a story by id."""

        async def _run() -> None:
            async with get_client() as client:
                params: dict[str, Any] = {
                    "operation_id": operation_id,
                    "obj_id": obj_id,
                }
                if req_id is not None:
                    params["req_id"] = req_id

                result = await call_custom_endpoint(
                    client,
                    method="GET",
                    path="/story_get_by_id",
                    params=params,
                )
                print_result(result, verbose=verbose)

        asyncio.run(_run())

    @story_app.command("list", rich_help_panel="Extension Commands")
    def story_list(
        operation_id: str,
        flt: str | None = typer.Option(None, "--flt", help="GulpCollabFilter JSON object"),
        req_id: str | None = typer.Option(None, "--req-id"),
        as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
        verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
    ) -> None:
        """Extension: list stories for an operation."""

        async def _run() -> None:
            flt_obj = parse_json_option(flt, field_name="flt") or {}
            async with get_client() as client:
                params: dict[str, Any] = {
                    "operation_id": operation_id,
                }
                if req_id is not None:
                    params["req_id"] = req_id

                result = await call_custom_endpoint(
                    client,
                    method="POST",
                    path="/story_list",
                    params=params,
                    json_body=flt_obj,
                )

                if as_json or verbose:
                    print_result(result, verbose=True)
                    return

                if isinstance(result, dict) and isinstance(result.get("data"), list):
                    print_records(_story_rows(result.get("data", [])), title="Stories")
                    return

                print_result(result, verbose=True)

        asyncio.run(_run())
