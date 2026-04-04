from __future__ import annotations

import asyncio
from typing import Any

import typer
from gulp_sdk.api.request_utils import wait_for_request_stats
from gulp_sdk.websocket import WSMessage, WSMessageType
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn

from gulp_cli.client import get_client
from gulp_cli.output import console, print_json, print_warning, print_result
from gulp_cli.utils import parse_json_option

app = typer.Typer(help="Database and OpenSearch commands")

_WS_CONFIRM_TIMEOUT_SEC = 30.0


async def _wait_for_stats_create(
    client: Any,
    req_ids: list[str],
    timeout: float = _WS_CONFIRM_TIMEOUT_SEC,
) -> list[str]:
    req_ids = [r for r in req_ids if r]
    if not req_ids:
        return []

    ws = await client.ensure_websocket()
    events: dict[str, asyncio.Event] = {req_id: asyncio.Event() for req_id in req_ids}

    async def _on_stats(msg: WSMessage) -> None:
        ev = events.get(msg.req_id)
        if ev is not None:
            ev.set()

    ws.on_message(WSMessageType.STATS_CREATE, _on_stats)
    ws.on_message(WSMessageType.STATS_UPDATE, _on_stats)

    try:
        await asyncio.wait_for(asyncio.gather(*[ev.wait() for ev in events.values()]), timeout=timeout)
        return []
    except asyncio.TimeoutError:
        return [rid for rid, ev in events.items() if not ev.is_set()]
    finally:
        ws.off_message(WSMessageType.STATS_CREATE, _on_stats)
        ws.off_message(WSMessageType.STATS_UPDATE, _on_stats)


@app.command("rebase-by-query")
def rebase_by_query(
    operation_id: str,
    offset_msec: int = typer.Option(..., "--offset-msec", help="Milliseconds to add to timestamps (negative to subtract)"),
    flt: str | None = typer.Option(None, "--flt", help="GulpQueryFilter JSON object"),
    script: str | None = typer.Option(None, "--script", help="Custom Painless script override"),
    wait: bool = typer.Option(False, "--wait", help="Wait for rebase completion with websocket-driven progress"),
    wait_timeout: int = typer.Option(300, "--timeout", help="Seconds to wait when --wait is used"),
) -> None:
    """Rebase document timestamps in an operation using update_by_query."""

    async def _run() -> None:
        flt_obj = parse_json_option(flt, field_name="flt")
        async with get_client() as client:
            await client.ensure_websocket()

            if not wait:
                result = await client.db.rebase_by_query(
                    operation_id=operation_id,
                    ws_id=client.ws_id,
                    offset_msec=offset_msec,
                    flt=flt_obj,
                    script=script,
                    wait=False,
                )
                req_id = result.get("req_id") if isinstance(result, dict) else None
                timed_out = await _wait_for_stats_create(client, [str(req_id)] if req_id else [])
                if timed_out:
                    print_warning(
                        f"Request did not receive STATS_CREATE within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s: "
                        + ", ".join(timed_out)
                    )
                print_result(result)
                return

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
                transient=True,
            ) as progress:
                task_id = progress.add_task("rebase", total=None)

                def _ws_callback(msg: WSMessage) -> None:
                    if not isinstance(msg.data, dict):
                        return
                    obj = msg.data.get("obj", msg.data)
                    if not isinstance(obj, dict):
                        return
                    data = obj.get("data", {})
                    if not isinstance(data, dict):
                        data = {}
                    total_hits = data.get("total_hits")
                    updated = data.get("updated")
                    if isinstance(total_hits, int) and total_hits > 0 and isinstance(updated, int):
                        progress.update(task_id, total=total_hits, completed=min(updated, total_hits))
                        progress.update(task_id, description=f"rebase ({updated}/{total_hits})")
                    elif isinstance(updated, int):
                        progress.update(task_id, description=f"rebase ({updated} updated)")

                result = await client.db.rebase_by_query(
                    operation_id=operation_id,
                    ws_id=client.ws_id,
                    offset_msec=offset_msec,
                    flt=flt_obj,
                    script=script,
                    wait=False,
                )
                req_id = result.get("req_id") if isinstance(result, dict) else None
                if not req_id:
                    print_result(result)
                    return

                stats = await wait_for_request_stats(
                    client,
                    str(req_id),
                    wait_timeout,
                    ws_callback=_ws_callback,
                )
                print_result(stats)

    asyncio.run(_run())


@app.command("list-indexes")
def list_indexes() -> None:
    """List all OpenSearch datastreams/indexes (admin required)."""

    async def _run() -> None:
        async with get_client() as client:
            indexes = await client.db.list_indexes()
            print_result(indexes, formatter=lambda d: print_records(d, title="Indexes"))

    asyncio.run(_run())


@app.command("refresh-index")
def refresh_index(
    index: str,
) -> None:
    """Refresh an OpenSearch index so new documents become searchable (ingest permission required)."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.db.refresh_index(index)
            print_result(result)

    asyncio.run(_run())


@app.command("delete-index")
def delete_index(
    index: str,
    keep_operation: bool = typer.Option(False, "--keep-operation", help="Do NOT delete the associated collab operation"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Delete an OpenSearch datastream/index and (by default) its collab operation. WARNING: all data will be lost."""

    async def _run() -> None:
        if not yes:
            typer.confirm(
                f"This will permanently delete index '{index}' and all its data. Continue?",
                abort=True,
            )
        async with get_client() as client:
            result = await client.db.delete_index(
                index,
                delete_operation=not keep_operation,
            )
            print_result(result)

    asyncio.run(_run())
