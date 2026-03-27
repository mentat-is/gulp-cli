from __future__ import annotations

import asyncio
from glob import glob
from pathlib import Path
from typing import Any

import typer
from gulp_sdk.websocket import WSMessage, WSMessageType
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn

from gulp_cli.client import get_client
from gulp_cli.output import console, print_error, print_json, print_result, print_warning
from gulp_cli.utils import parse_json_option

app = typer.Typer(help="Ingestion commands")

# How long to keep the websocket alive waiting for STATS_CREATE confirmation
# when --wait is NOT used.  Should be well above the worker task-scheduling lag.
_WS_CONFIRM_TIMEOUT_SEC = 30.0


async def _wait_for_stats_create(
    client: Any,
    req_ids: list[str],
    timeout: float = _WS_CONFIRM_TIMEOUT_SEC,
) -> list[str]:
    """Keep the websocket alive until a STATS_CREATE (or STATS_UPDATE) event is
    received for every *req_id* in the list.

    This is the websocket-native replacement for HTTP polling: the backend
    publishes STATS_CREATE the moment it creates the GulpRequestStats object,
    which is the very first thing a worker does.  Receiving that event proves
    the websocket was alive when the backend needed it.

    Returns the list of req_ids that did NOT receive confirmation within *timeout*.
    """
    req_ids = [r for r in req_ids if r]
    if not req_ids:
        return []

    ws = await client.ensure_websocket()

    # One asyncio.Event per req_id; we set it on any STATS_CREATE/STATS_UPDATE
    # message that carries the matching req_id.
    events: dict[str, asyncio.Event] = {req_id: asyncio.Event() for req_id in req_ids}

    async def _on_stats(msg: WSMessage) -> None:
        ev = events.get(msg.req_id)
        if ev is not None:
            ev.set()

    ws.on_message(WSMessageType.STATS_CREATE, _on_stats)
    ws.on_message(WSMessageType.STATS_UPDATE, _on_stats)

    try:
        await asyncio.wait_for(
            asyncio.gather(*[ev.wait() for ev in events.values()]),
            timeout=timeout,
        )
        return []
    except asyncio.TimeoutError:
        return [rid for rid, ev in events.items() if not ev.is_set()]
    finally:
        ws.off_message(WSMessageType.STATS_CREATE, _on_stats)
        ws.off_message(WSMessageType.STATS_UPDATE, _on_stats)


async def _wait_for_completion(
    client: Any,
    file_req_map: dict[str, str],
    timeout: int,
    verbose: bool,
) -> list[dict[str, Any]]:
    """Wait for every ingest request to reach a terminal status via websocket.

    Uses the SDK's ``wait_for_request_stats`` which is WS-first and only falls
    back to polling if the websocket is unavailable.

    Returns a list of result dicts (one per file) with final status.
    """
    from gulp_sdk.api.request_utils import wait_for_request_stats

    ws = await client.ensure_websocket()

    results: list[dict[str, Any]] = []
    # Rich progress bar: one task per file
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_ids: dict[str, Any] = {}
        for file_path, req_id in file_req_map.items():
            task_ids[req_id] = progress.add_task(
                Path(file_path).name, total=None
            )

        def _make_ws_callback(req_id: str):
            def _cb(msg: WSMessage) -> None:
                tid = task_ids.get(req_id)
                if tid is None:
                    return
                if msg.type == WSMessageType.INGEST_SOURCE_DONE.value:
                    ingested = 0
                    if isinstance(msg.data, dict):
                        obj = msg.data.get("obj", msg.data)
                        if isinstance(obj, dict):
                            ingested = obj.get("records_ingested", 0) or 0
                    progress.update(tid, description=f"{Path(list(file_req_map.keys())[list(file_req_map.values()).index(req_id)]).name} ({ingested} docs)")
                elif msg.type in (WSMessageType.STATS_UPDATE.value, WSMessageType.STATS_CREATE.value):
                    if isinstance(msg.data, dict):
                        obj = msg.data.get("obj", msg.data)
                        if isinstance(obj, dict):
                            pct = obj.get("ingest_percentage", None)
                            if pct is not None:
                                progress.update(tid, completed=pct, total=100)
            return _cb

        wait_tasks = [
            wait_for_request_stats(
                client,
                req_id,
                timeout,
                ws_callback=_make_ws_callback(req_id),
            )
            for req_id in file_req_map.values()
        ]
        stats_list = await asyncio.gather(*wait_tasks, return_exceptions=True)

        for (file_path, req_id), stat in zip(file_req_map.items(), stats_list):
            if isinstance(stat, BaseException):
                results.append({"file": file_path, "req_id": req_id, "status": "error", "error": str(stat)})
            elif isinstance(stat, dict):
                if verbose:
                    results.append({"file": file_path, "req_id": req_id, "result": stat})
                else:
                    results.append({"file": file_path, "req_id": req_id, "status": stat.get("status", "unknown")})
            else:
                results.append({"file": file_path, "req_id": req_id, "status": "unknown"})

    return results


@app.command("file")
def ingest_file(
    operation_id: str,
    plugin: str,
    file_patterns: list[str] = typer.Argument(
        ...,
        help="One or more files or glob patterns (e.g. '*.evtx', '/path/to/dir/**/*.log')",
    ),
    context_name: str = typer.Option("sdk_context", "--context-name"),
    plugin_params: str | None = typer.Option(None, "--plugin-params", help="JSON object for plugin_params"),
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpIngestionFilter"),
    reset_operation: bool = typer.Option(
        False,
        "--reset-operation",
        help="Delete and recreate the operation before ingest starts",
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Run ingestion preview (no persistence) and return preview payload",
    ),
    wait: bool = typer.Option(
        False,
        "--wait",
        help=(
            "Wait for all ingestions to complete (WS-driven progress bar). "
            "Without this flag the CLI returns as soon as the backend confirms "
            "reception of each request via STATS_CREATE websocket event."
        ),
    ),
    wait_timeout: int = typer.Option(300, "--wait-timeout", help="Seconds to wait for completion (only used with --wait)"),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Print complete result JSON instead of summary",
    ),
) -> None:
    """Ingest one or more files (supports glob patterns).

    By default the command returns once the backend has confirmed every request
    via a STATS_CREATE websocket notification — no HTTP polling.  Pass --wait
    to block until ingestion fully completes, with a live progress bar.
    """

    # ------------------------------------------------------------------ #
    # Expand glob patterns                                                 #
    # ------------------------------------------------------------------ #
    expanded_files: list[str] = []
    for pattern in file_patterns:
        matches = sorted(glob(pattern, recursive=True))
        if matches:
            expanded_files.extend(matches)
        else:
            # Treat as literal path; server will report the error
            expanded_files.append(pattern)

    seen: set[str] = set()
    unique_files: list[str] = []
    for f in expanded_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    if not unique_files:
        print_error("No files found matching the provided patterns.")
        raise typer.Exit(1)

    # ------------------------------------------------------------------ #
    # Async runner                                                         #
    # ------------------------------------------------------------------ #
    async def _run() -> None:
        if preview and wait:
            raise typer.BadParameter("--preview and --wait are mutually exclusive")
        if preview and reset_operation:
            raise typer.BadParameter("--preview and --reset-operation are mutually exclusive")

        async with get_client() as client:
            # Establish WS BEFORE any ingest call so ws_id is live when the
            # worker tries to publish its first STATS_CREATE event.
            await client.ensure_websocket()

            params = {
                "plugin_params": parse_json_option(plugin_params, field_name="plugin-params") or {},
                "flt": parse_json_option(flt, field_name="flt") or {},
            }

            if preview:
                previews: list[dict[str, Any]] = []
                for file_path in unique_files:
                    data = await client.ingest.preview(
                        operation_id=operation_id,
                        plugin_name=plugin,
                        file_path=file_path,
                        params={
                            "context_name": context_name,
                            "plugin_params": params["plugin_params"],
                            "flt": params["flt"],
                            "original_file_path": str(Path(file_path).resolve()),
                        },
                    )
                    previews.append({"file": file_path, "preview": data})
                print_result(previews, verbose=verbose)
                return

            if reset_operation:
                await client.operations.delete(operation_id)
                op = await client.operations.create(name=operation_id)
                if not verbose:
                    print_warning(
                        f"Operation {operation_id} reset (deleted and recreated)."
                    )

            async def _fire_one(file_path: str) -> tuple[str, str, dict[str, Any]]:
                """Submit ingestion for one file; returns (file_path, req_id, submission)."""
                result = await client.ingest.file(
                    operation_id=operation_id,
                    plugin_name=plugin,
                    file_path=file_path,
                    context_name=context_name,
                    params={**params, "original_file_path": str(Path(file_path).resolve())},
                    wait=False,  # we handle waiting ourselves below
                )
                if hasattr(result, "model_dump"):
                    submission = result.model_dump(exclude_none=True)
                else:
                    submission = {"req_id": getattr(result, "req_id", None)}
                req_id = str(submission.get("req_id") or "")
                return file_path, req_id, submission

            # Fire all requests concurrently
            fired: list[tuple[str, str, dict[str, Any]]] = await asyncio.gather(
                *[_fire_one(path) for path in unique_files]
            )
            file_req_map: dict[str, str] = {file_path: req_id for file_path, req_id, _ in fired}
            fired_meta: dict[str, dict[str, Any]] = {req_id: payload for _, req_id, payload in fired if req_id}

            if wait:
                # --wait: block until terminal status via websocket
                results = await _wait_for_completion(client, file_req_map, wait_timeout, verbose)
            else:
                # Default: keep websocket alive until backend confirms every
                # request as registered (STATS_CREATE event per req_id).
                req_ids = list(file_req_map.values())
                timed_out = await _wait_for_stats_create(client, req_ids)
                if timed_out and not verbose:
                    print_warning(
                        f"{len(timed_out)} request(s) did not receive STATS_CREATE "
                        f"within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s — backend may still be processing: "
                        + ", ".join(timed_out)
                    )
                if verbose:
                    results = [
                        {
                            "file": fp,
                            "req_id": rid,
                            "submitted": fired_meta.get(rid, {"req_id": rid}),
                            "ws_confirmed": rid not in timed_out,
                        }
                        for fp, rid in file_req_map.items()
                    ]
                else:
                    results = [
                        {"file": fp, "req_id": rid, "status": "pending"}
                        for fp, rid in file_req_map.items()
                    ]

            print_result(results, verbose=verbose)

    asyncio.run(_run())
