from __future__ import annotations

import asyncio
import json
from glob import glob
from pathlib import Path
from typing import Any

from gulp_cli.config import get_runtime_verbose
import typer
from gulp_sdk.exceptions import NotFoundError
from gulp_sdk.websocket import WSMessage, WSMessageType
from rich.markup import escape
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn

from gulp_cli.client import get_client
from gulp_cli.output import console, print_error, print_json, print_result, print_warning
from gulp_cli.utils import parse_json_option

app = typer.Typer(help="Ingestion commands")

# How long to keep the websocket alive waiting for STATS_CREATE confirmation
# when --wait is NOT used.  Should be well above the worker task-scheduling lag.
_WS_CONFIRM_TIMEOUT_SEC = 30.0
_TERMINAL_STATUSES = {"done", "failed", "canceled"}


async def _ensure_operation_exists(
    client: Any,
    operation_id: str,
    *,
    create_if_missing: bool,
) -> None:
    """Ensure operation exists, optionally creating it when missing."""
    try:
        await client.operations.get(operation_id)
    except NotFoundError:
        if not create_if_missing:
            raise
        await client.operations.create(name=operation_id)
        if not get_runtime_verbose():
            print_warning(
                f"Operation {operation_id} was missing and has been created."
            )


def _expand_file_patterns(file_patterns: list[str]) -> list[str]:
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
    for file_path in expanded_files:
        if file_path not in seen:
            seen.add(file_path)
            unique_files.append(file_path)

    return unique_files


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
) -> list[dict[str, Any]]:
    """Wait for every ingest request to reach a terminal status via websocket only.

    This function intentionally avoids HTTP polling and relies exclusively on
    websocket packets (STATS_CREATE/STATS_UPDATE/INGEST_SOURCE_DONE/ERROR).

    Returns a list of result dicts (one per file) with final status.
    """

    ws = await client.ensure_websocket()
    req_to_file: dict[str, str] = {rid: file_path for file_path, rid in file_req_map.items()}

    def _extract_payload_obj(msg: WSMessage) -> dict[str, Any]:
        if not isinstance(msg.data, dict):
            return {}
        obj = msg.data.get("obj")
        if isinstance(obj, dict):
            return obj
        return msg.data

    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _extract_ingest_counters(payload: dict[str, Any]) -> tuple[int, int, int, bool]:
        """Extract ingestion counters from either top-level or nested stats data."""
        nested = payload.get("data")
        nested_data = nested if isinstance(nested, dict) else {}
        has_top = any(
            key in payload for key in ("records_ingested", "records_skipped", "records_failed")
        )
        has_nested = any(
            key in nested_data for key in ("records_ingested", "records_skipped", "records_failed")
        )
        ingested = _to_int(payload.get("records_ingested"))
        skipped = _to_int(payload.get("records_skipped"))
        failed = _to_int(payload.get("records_failed"))

        # GulpRequestStats packets usually keep ingestion counters in obj.data.
        ingested = max(ingested, _to_int(nested_data.get("records_ingested")))
        skipped = max(skipped, _to_int(nested_data.get("records_skipped")))
        failed = max(failed, _to_int(nested_data.get("records_failed")))
        return ingested, skipped, failed, (has_top or has_nested)

    def _status_label(status: str, ingested: int, skipped: int, failed: int) -> str:
        return f"{status}: ingested={ingested}, skipped={skipped}, failed={failed}"

    states: dict[str, dict[str, Any]] = {
        req_id: {
            "status": "ongoing",
            "ingested": 0,
            "skipped": 0,
            "failed": 0,
            "stats": {},
            "event": asyncio.Event(),
        }
        for req_id in file_req_map.values()
        if req_id
    }

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
            sid_tag = escape(f"[{req_id[:8]}]")
            task_ids[req_id] = progress.add_task(
                f"{sid_tag} {Path(file_path).name}", total=None
            )

        def _on_message(msg: WSMessage) -> None:
            req_id = msg.req_id
            state = states.get(req_id)
            if state is None:
                return

            tid = task_ids.get(req_id)
            if tid is None:
                return

            file_name = Path(req_to_file.get(req_id, req_id)).name
            sid_tag = escape(f"[{req_id[:8]}]")
            obj = _extract_payload_obj(msg)

            if msg.type == WSMessageType.INGEST_SOURCE_DONE.value:
                done_ingested, done_skipped, done_failed, _ = _extract_ingest_counters(obj)
                state["ingested"] += done_ingested
                state["skipped"] += done_skipped
                state["failed"] += done_failed
                state.setdefault("sources_done", 0)
                state["sources_done"] += 1
                progress.update(
                    tid,
                    description=(
                        f"{sid_tag} {file_name} (running: ingested={state['ingested']}, "
                        f"skipped={state['skipped']}, failed={state['failed']})"
                    ),
                )
                return

            if msg.type in (WSMessageType.STATS_CREATE.value, WSMessageType.STATS_UPDATE.value):
                state["stats"] = obj
                status = str(obj.get("status", state["status"]))
                pct = obj.get("ingest_percentage")
                if pct is not None:
                    progress.update(tid, completed=pct, total=100)

                # Request stats counters are authoritative snapshots.
                stats_ingested, stats_skipped, stats_failed, has_stats_counters = _extract_ingest_counters(obj)
                if has_stats_counters:
                    state["ingested"] = stats_ingested
                    state["skipped"] = stats_skipped
                    state["failed"] = stats_failed

                state["status"] = status
                if status in _TERMINAL_STATUSES:
                    progress.update(
                        tid,
                        completed=100,
                        total=100,
                        description=f"{sid_tag} {file_name} ({_status_label(status, state['ingested'], state['skipped'], state['failed'])})",
                    )
                    state["event"].set()
                return

            if msg.type == WSMessageType.ERROR.value:
                state["status"] = "failed"
                state["stats"] = obj
                progress.update(
                    tid,
                    completed=100,
                    total=100,
                    description=f"{sid_tag} {file_name} ({_status_label('failed', state['ingested'], state['skipped'], state['failed'])})",
                )
                state["event"].set()

        ws.on_message(WSMessageType.INGEST_SOURCE_DONE, _on_message)
        ws.on_message(WSMessageType.STATS_CREATE, _on_message)
        ws.on_message(WSMessageType.STATS_UPDATE, _on_message)
        ws.on_message(WSMessageType.ERROR, _on_message)

        deadline = None if timeout == 0 else asyncio.get_running_loop().time() + timeout
        try:
            for req_id, state in states.items():
                if deadline is None:
                    await state["event"].wait()
                else:
                    remaining = max(0.0, deadline - asyncio.get_running_loop().time())
                    if remaining == 0.0 and not state["event"].is_set():
                        continue
                    try:
                        await asyncio.wait_for(state["event"].wait(), timeout=remaining)
                    except asyncio.TimeoutError:
                        pass
        finally:
            ws.off_message(WSMessageType.INGEST_SOURCE_DONE, _on_message)
            ws.off_message(WSMessageType.STATS_CREATE, _on_message)
            ws.off_message(WSMessageType.STATS_UPDATE, _on_message)
            ws.off_message(WSMessageType.ERROR, _on_message)

        for file_path, req_id in file_req_map.items():
            tid = task_ids.get(req_id)
            state = states.get(req_id)
            sid_tag = escape(f"[{req_id[:8]}]")

            if tid is not None:
                try:
                    if state and state.get("status") in _TERMINAL_STATUSES:
                        status = str(state.get("status"))
                        progress.update(
                            tid,
                            completed=100,
                            total=100,
                            description=(
                                f"{sid_tag} {Path(file_path).name} ("
                                f"{_status_label(status, state.get('ingested', 0), state.get('skipped', 0), state.get('failed', 0))}"
                                ")"
                            ),
                        )
                    elif state and not state.get("event").is_set():
                        progress.update(
                            tid,
                            description=(
                                f"{sid_tag} {Path(file_path).name} (timeout: ingested={state.get('ingested', 0)}, "
                                f"skipped={state.get('skipped', 0)}, failed={state.get('failed', 0)})"
                            ),
                        )
                except Exception:
                    pass

            if state is None:
                results.append({"file": file_path, "req_id": req_id, "status": "unknown"})
            elif get_runtime_verbose():
                results.append(
                    {
                        "file": file_path,
                        "req_id": req_id,
                        "status": state.get("status", "unknown"),
                        "ingested": state.get("ingested", 0),
                        "skipped": state.get("skipped", 0),
                        "failed": state.get("failed", 0),
                        "result": state.get("stats", {}),
                        "ws_only": True,
                    }
                )
            else:
                results.append(
                    {
                        "file": file_path,
                        "req_id": req_id,
                        "status": state.get("status", "unknown"),
                        "ingested": state.get("ingested", 0),
                        "skipped": state.get("skipped", 0),
                        "failed": state.get("failed", 0),
                    }
                )

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
    create_operation_if_missing: bool = typer.Option(
        False,
        "--create-operation",
        help="Create operation automatically when it does not exist",
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
    wait_timeout: int = typer.Option(300, "--timeout", help="Seconds to wait for completion (only used with --wait)"),
) -> None:
    """Ingest one or more files (supports glob patterns).

    By default the command returns once the backend has confirmed every request
    via a STATS_CREATE websocket notification — no HTTP polling.  Pass --wait
    to block until ingestion fully completes, with a live progress bar.
    """

    unique_files = _expand_file_patterns(file_patterns)

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
        if reset_operation and create_operation_if_missing:
            raise typer.BadParameter(
                "--reset-operation and --create-operation are mutually exclusive"
            )

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
                print_result(previews)
                return

            if reset_operation:
                await client.operations.delete(operation_id, force=True)
                op = await client.operations.create(name=operation_id)
                if not get_runtime_verbose():
                    print_warning(
                        f"Operation {operation_id} reset (deleted and recreated)."
                    )
            else:
                await _ensure_operation_exists(
                    client,
                    operation_id,
                    create_if_missing=create_operation_if_missing,
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
                results = await _wait_for_completion(client, file_req_map, wait_timeout)
            else:
                # Default: keep websocket alive until backend confirms every
                # request as registered (STATS_CREATE event per req_id).
                req_ids = list(file_req_map.values())
                timed_out = await _wait_for_stats_create(client, req_ids)
                if timed_out and not get_runtime_verbose():
                    print_warning(
                        f"{len(timed_out)} request(s) did not receive STATS_CREATE "
                        f"within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s — backend may still be processing: "
                        + ", ".join(timed_out)
                    )
                if get_runtime_verbose():
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

            print_result(results)

    asyncio.run(_run())


@app.command("file-to-source")
def ingest_file_to_source(
    source_id: str,
    file_patterns: list[str] = typer.Argument(
        ...,
        help="One or more files or glob patterns (e.g. '*.evtx', '/path/to/dir/**/*.log')",
    ),
    plugin_params: str | None = typer.Option(None, "--plugin-params", help="JSON object for plugin_params (overrides source defaults)"),
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpIngestionFilter"),
    wait: bool = typer.Option(
        False,
        "--wait",
        help=(
            "Wait for all ingestions to complete (WS-driven progress bar). "
            "Without this flag the CLI returns as soon as the backend confirms "
            "reception of each request via STATS_CREATE websocket event."
        ),
    ),
    wait_timeout: int = typer.Option(300, "--timeout", help="Seconds to wait for completion (only used with --wait)"),
) -> None:
    """Ingest one or more files into an existing source."""

    unique_files = _expand_file_patterns(file_patterns)
    if not unique_files:
        print_error("No files found matching the provided patterns.")
        raise typer.Exit(1)

    async def _run() -> None:
        async with get_client() as client:
            await client.ensure_websocket()

            params = {
                "plugin_params": parse_json_option(plugin_params, field_name="plugin-params") or {},
                "flt": parse_json_option(flt, field_name="flt") or {},
            }

            async def _fire_one(file_path: str) -> tuple[str, str, dict[str, Any]]:
                result = await client.ingest.file_to_source(
                    source_id=source_id,
                    file_path=file_path,
                    plugin_params=params["plugin_params"] or None,
                    flt=params["flt"] or None,
                    wait=False,
                )
                if hasattr(result, "model_dump"):
                    submission = result.model_dump(exclude_none=True)
                else:
                    submission = {"req_id": getattr(result, "req_id", None)}
                req_id = str(submission.get("req_id") or "")
                return file_path, req_id, submission

            fired: list[tuple[str, str, dict[str, Any]]] = await asyncio.gather(
                *[_fire_one(path) for path in unique_files]
            )
            file_req_map: dict[str, str] = {file_path: req_id for file_path, req_id, _ in fired}
            fired_meta: dict[str, dict[str, Any]] = {req_id: payload for _, req_id, payload in fired if req_id}

            if wait:
                results = await _wait_for_completion(client, file_req_map, wait_timeout)
            else:
                req_ids = list(file_req_map.values())
                timed_out = await _wait_for_stats_create(client, req_ids)
                if timed_out and not get_runtime_verbose():
                    print_warning(
                        f"{len(timed_out)} request(s) did not receive STATS_CREATE "
                        f"within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s - backend may still be processing: "
                        + ", ".join(timed_out)
                    )
                if get_runtime_verbose():
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

            print_result(results)

    asyncio.run(_run())


@app.command("zip")
def ingest_zip(
    operation_id: str,
    zip_file: str,
    context_name: str = typer.Option("sdk_context", "--context-name"),
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpIngestionFilter"),
    reset_operation: bool = typer.Option(
        False,
        "--reset-operation",
        help="Delete and recreate the operation before ingest starts",
    ),
    create_operation_if_missing: bool = typer.Option(
        False,
        "--create-operation",
        help="Create operation automatically when it does not exist",
    ),
    wait: bool = typer.Option(False, "--wait", help="Wait for ingestion completion"),
    wait_timeout: int = typer.Option(300, "--timeout", help="Seconds to wait for completion (only used with --wait)"),
) -> None:
    """Ingest a ZIP archive into an operation."""

    async def _run() -> None:
        if reset_operation and create_operation_if_missing:
            raise typer.BadParameter(
                "--reset-operation and --create-operation are mutually exclusive"
            )

        async with get_client() as client:
            await client.ensure_websocket()

            if reset_operation:
                await client.operations.delete(operation_id, force=True)
                await client.operations.create(name=operation_id)
                if not get_runtime_verbose():
                    print_warning(
                        f"Operation {operation_id} reset (deleted and recreated)."
                    )
            else:
                await _ensure_operation_exists(
                    client,
                    operation_id,
                    create_if_missing=create_operation_if_missing,
                )

            params = {
                "context_name": context_name,
                "flt": parse_json_option(flt, field_name="flt") or {},
            }
            result = await client.ingest.zip(
                operation_id=operation_id,
                plugin_name="zip",
                zipfile_path=zip_file,
                params=params,
                wait=False,
            )

            if hasattr(result, "model_dump"):
                submission = result.model_dump(exclude_none=True)
            else:
                submission = {"req_id": getattr(result, "req_id", None)}

            req_id = str(submission.get("req_id") or "")
            if not req_id:
                # Fallback: if backend did not return req_id, surface submission as-is.
                print_result(submission)
                return

            file_req_map: dict[str, str] = {zip_file: req_id}

            if wait:
                waited = await _wait_for_completion(client, file_req_map, wait_timeout)
                print_result(waited[0] if waited else {"file": zip_file, "req_id": req_id, "status": "unknown"})
            else:
                timed_out = await _wait_for_stats_create(client, [req_id])
                if timed_out and not get_runtime_verbose():
                    print_warning(
                        f"Request did not receive STATS_CREATE within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s - backend may still be processing: {req_id}"
                    )

                if get_runtime_verbose():
                    print_result(
                        {
                            "file": zip_file,
                            "req_id": req_id,
                            "submitted": submission,
                            "ws_confirmed": req_id not in timed_out,
                        }
                    )
                else:
                    print_result({"file": zip_file, "req_id": req_id, "status": "pending"})

    asyncio.run(_run())


@app.command("raw")
def ingest_raw(
    operation_id: str,
    data: str | None = typer.Option(None, "--data", help="Raw payload text (JSON recommended)"),
    data_file: str | None = typer.Option(None, "--data-file", help="Path to file containing raw payload"),
    plugin: str = typer.Option("raw", "--plugin", help="Plugin used to process the raw payload"),
    plugin_params: str | None = typer.Option(None, "--plugin-params", help="JSON object for plugin_params"),
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpIngestionFilter"),
    req_id: str | None = typer.Option(None, "--req-id", help="Optional request ID for chunked ingestion"),
    last: bool = typer.Option(False, "--last", help="Mark this payload as the last raw chunk"),
    reset_operation: bool = typer.Option(
        False,
        "--reset-operation",
        help="Delete and recreate the operation before ingest starts",
    ),
    create_operation_if_missing: bool = typer.Option(
        False,
        "--create-operation",
        help="Create operation automatically when it does not exist",
    ),
    wait: bool = typer.Option(False, "--wait", help="Wait for ingestion completion"),
    wait_timeout: int = typer.Option(300, "--timeout", help="Seconds to wait for completion (only used with --wait)"),
) -> None:
    """Ingest raw payload into an operation."""

    if (data is None and data_file is None) or (data is not None and data_file is not None):
        raise typer.BadParameter("Provide exactly one of --data or --data-file")

    async def _run() -> None:
        if reset_operation and create_operation_if_missing:
            raise typer.BadParameter(
                "--reset-operation and --create-operation are mutually exclusive"
            )

        async with get_client() as client:
            await client.ensure_websocket()

            if reset_operation:
                await client.operations.delete(operation_id, force=True)
                await client.operations.create(name=operation_id)
                if not get_runtime_verbose():
                    print_warning(
                        f"Operation {operation_id} reset (deleted and recreated)."
                    )
            else:
                await _ensure_operation_exists(
                    client,
                    operation_id,
                    create_if_missing=create_operation_if_missing,
                )

            if data_file is not None:
                payload_data: dict[str, Any] | str | bytes = Path(data_file).read_bytes()
            else:
                assert data is not None
                try:
                    payload_data = json.loads(data)
                except json.JSONDecodeError:
                    payload_data = data

            params: dict[str, Any] = {
                "plugin_params": parse_json_option(plugin_params, field_name="plugin-params") or {},
                "flt": parse_json_option(flt, field_name="flt") or {},
                "last": last,
            }
            if req_id:
                params["req_id"] = req_id

            result = await client.ingest.raw(
                operation_id=operation_id,
                plugin_name=plugin,
                data=payload_data,
                params=params,
                wait=False,
            )

            if hasattr(result, "model_dump"):
                submission = result.model_dump(exclude_none=True)
            else:
                submission = {"req_id": getattr(result, "req_id", None)}

            resolved_req_id = str(submission.get("req_id") or "")
            if not resolved_req_id:
                print_result(submission)
                return

            request_label = data_file if data_file is not None else "raw-input"
            file_req_map: dict[str, str] = {request_label: resolved_req_id}

            if wait:
                waited = await _wait_for_completion(client, file_req_map, wait_timeout)
                print_result(
                    waited[0]
                    if waited
                    else {"file": request_label, "req_id": resolved_req_id, "status": "unknown"}
                )
            else:
                timed_out = await _wait_for_stats_create(client, [resolved_req_id])
                if timed_out and not get_runtime_verbose():
                    print_warning(
                        f"Request did not receive STATS_CREATE within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s - backend may still be processing: {resolved_req_id}"
                    )

                if get_runtime_verbose():
                    print_result(
                        {
                            "file": request_label,
                            "req_id": resolved_req_id,
                            "submitted": submission,
                            "ws_confirmed": resolved_req_id not in timed_out,
                        }
                    )
                else:
                    print_result(
                        {"file": request_label, "req_id": resolved_req_id, "status": "pending"}
                    )

    asyncio.run(_run())
