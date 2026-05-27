from __future__ import annotations

import asyncio
import json
import os
import zipfile
from glob import glob, has_magic
from pathlib import Path
from typing import Any, Awaitable, Callable

from gulp_cli.config import get_runtime_verbose
import typer
from gulp_sdk.exceptions import NotFoundError
from gulp_sdk.websocket import WSMessage, WSMessageType
from rich.markup import escape
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)

from gulp_cli.client import get_client
from gulp_cli.output import (
    console,
    print_error,
    print_json,
    print_result,
    print_warning,
)
from gulp_cli.utils import parse_json_option

app = typer.Typer(help="Ingestion commands")

# How long to keep the websocket alive waiting for STATS_CREATE confirmation
# when --wait is NOT used.  Should be well above the worker task-scheduling lag.
_WS_CONFIRM_TIMEOUT_SEC = 30.0
_TERMINAL_STATUSES = {"done", "failed", "canceled"}


def _default_ingest_batch_size() -> int:
    return max(1, (os.cpu_count() or 1) * 2)


def _format_per_file_progress_line(item: dict[str, Any]) -> str:
    req_id = str(item.get("req_id") or "")
    req_tag = req_id[:8] if req_id else "no-reqid"
    file_name = Path(str(item.get("file") or "")).name or "<unknown>"
    status = str(item.get("status") or "unknown")
    ingested = int(item.get("ingested") or 0)
    skipped = int(item.get("skipped") or 0)
    failed = int(item.get("failed") or 0)
    return (
        f"[{req_tag}] {file_name}: {status} "
        f"(ingested={ingested}, skipped={skipped}, failed={failed})"
    )


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
            print_warning(f"Operation {operation_id} was missing and has been created.")


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

    return sorted(unique_files, key=str.casefold)


def _resolve_path(raw_path: str) -> Path:
    expanded = _expand_path_expression(raw_path)
    return Path(expanded).resolve()


def _expand_path_expression(raw_path: str) -> str:
    """Expand shell-style path expressions (env vars and '~')."""
    return os.path.expandvars(os.path.expanduser(raw_path.strip()))


def _expand_zip_source_patterns(
    path_patterns: list[str],
    paths_file: str | None,
) -> list[tuple[Path, Path]]:
    if path_patterns and paths_file is not None:
        raise typer.BadParameter(
            "Provide paths either as arguments or via --paths-file, not both"
        )
    if not path_patterns and paths_file is None:
        raise typer.BadParameter("Provide at least one path argument or --paths-file")

    raw_entries = list(path_patterns)
    if paths_file is not None:
        file_path = _resolve_path(paths_file)
        if not file_path.is_file():
            raise typer.BadParameter(f"Paths file not found: {file_path}")
        raw_entries.extend(
            line.strip()
            for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )

    expanded_paths: list[tuple[Path, Path]] = []
    seen: set[tuple[Path, Path]] = set()
    for raw_entry in raw_entries:
        expanded_entry = _expand_path_expression(raw_entry)
        if not expanded_entry:
            continue

        if has_magic(expanded_entry):
            pattern_path = Path(expanded_entry)
            base_dir = _resolve_glob_base(pattern_path)
            matches = [
                Path(match).resolve()
                for match in sorted(glob(expanded_entry, recursive=True))
            ]
            if not matches:
                raise typer.BadParameter(
                    f"Path mask did not match any files: {expanded_entry}"
                )

            for match in matches:
                item = (match, base_dir)
                if item not in seen:
                    seen.add(item)
                    expanded_paths.append(item)
            continue

        resolved_path = _resolve_path(expanded_entry)
        if not resolved_path.exists():
            raise typer.BadParameter(f"Path not found: {resolved_path}")

        base_dir = resolved_path.parent
        item = (resolved_path, base_dir)
        if item not in seen:
            seen.add(item)
            expanded_paths.append(item)

    return expanded_paths


def _resolve_glob_base(pattern_path: Path) -> Path:
    parts = pattern_path.parts
    if pattern_path.is_absolute():
        base_dir = Path(pattern_path.anchor)
        part_index = 1
    else:
        base_dir = Path.cwd()
        part_index = 0

    for part in parts[part_index:]:
        if has_magic(part):
            break
        base_dir /= part

    return base_dir.resolve()


def _build_zip_from_sources(
    output_zip: Path, sources: list[tuple[Path, Path]]
) -> tuple[int, list[str]]:
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    archived_entries: list[str] = []
    archived_count = 0
    seen_archive_entries: set[str] = set()
    seen_source_files: set[Path] = set()

    def _record_directory(archive_name_str: str, archive: zipfile.ZipFile) -> None:
        entry_name = f"{archive_name_str}/"
        if entry_name in seen_archive_entries:
            return
        archive.writestr(entry_name, "")
        seen_archive_entries.add(entry_name)
        archived_entries.append(entry_name)

    def _record_file(
        source_path: Path, archive_name_str: str, archive: zipfile.ZipFile
    ) -> None:
        nonlocal archived_count
        if archive_name_str in seen_archive_entries or source_path in seen_source_files:
            return
        archive.write(source_path, arcname=archive_name_str)
        seen_archive_entries.add(archive_name_str)
        seen_source_files.add(source_path)
        archived_entries.append(archive_name_str)
        archived_count += 1

    with zipfile.ZipFile(
        output_zip, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for source_path, base_dir in sources:
            try:
                archive_root = source_path.relative_to(base_dir)

                if not source_path.exists():
                    raise FileNotFoundError(source_path)

                if source_path.is_file():
                    _record_file(source_path, archive_root.as_posix(), archive)
                    continue

                child_paths = sorted(source_path.rglob("*"))
                if not child_paths:
                    _record_directory(archive_root.as_posix(), archive)
                    continue

                for current_path in child_paths:
                    try:
                        archive_name_str = current_path.relative_to(base_dir).as_posix()
                        if current_path.is_dir():
                            _record_directory(archive_name_str, archive)
                            continue
                        _record_file(current_path, archive_name_str, archive)
                    except Exception as exc:
                        print_error(
                            f"Skipping {current_path} while creating ZIP {output_zip}: {exc}"
                        )
            except Exception as exc:
                print_error(
                    f"Skipping {source_path} while creating ZIP {output_zip}: {exc}"
                )

    return archived_count, archived_entries


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
    req_to_file: dict[str, str] = {
        rid: file_path for file_path, rid in file_req_map.items()
    }

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
            key in payload
            for key in ("records_ingested", "records_skipped", "records_failed")
        )
        has_nested = any(
            key in nested_data
            for key in ("records_ingested", "records_skipped", "records_failed")
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
                done_ingested, done_skipped, done_failed, _ = _extract_ingest_counters(
                    obj
                )
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

            if msg.type in (
                WSMessageType.STATS_CREATE.value,
                WSMessageType.STATS_UPDATE.value,
            ):
                state["stats"] = obj
                status = str(obj.get("status", state["status"]))
                pct = obj.get("ingest_percentage")
                if pct is not None:
                    progress.update(tid, completed=pct, total=100)

                # Request stats counters are authoritative snapshots.
                stats_ingested, stats_skipped, stats_failed, has_stats_counters = (
                    _extract_ingest_counters(obj)
                )
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
                results.append(
                    {"file": file_path, "req_id": req_id, "status": "unknown"}
                )
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


class _IngestWsTracker:
    """Track ingest websocket events with persistent listeners for the whole run."""

    def __init__(
        self,
        ws: Any,
        *,
        source_done_is_terminal: bool = False,
        request_status_fetcher: (
            Callable[[str], Awaitable[dict[str, Any] | None]] | None
        ) = None,
    ) -> None:
        self._ws = ws
        self._source_done_is_terminal = source_done_is_terminal
        self._request_status_fetcher = request_status_fetcher
        self._states: dict[str, dict[str, Any]] = {}
        self._confirm_events: dict[str, asyncio.Event] = {}
        self._terminal_events: dict[str, asyncio.Event] = {}

        self._ws.on_message(WSMessageType.INGEST_SOURCE_DONE, self._on_message)
        self._ws.on_message(WSMessageType.STATS_CREATE, self._on_message)
        self._ws.on_message(WSMessageType.STATS_UPDATE, self._on_message)
        self._ws.on_message(WSMessageType.ERROR, self._on_message)

    @classmethod
    async def create(
        cls,
        client: Any,
        *,
        source_done_is_terminal: bool = False,
        request_status_fetcher: (
            Callable[[str], Awaitable[dict[str, Any] | None]] | None
        ) = None,
    ) -> "_IngestWsTracker":
        ws = await client.ensure_websocket()
        return cls(
            ws,
            source_done_is_terminal=source_done_is_terminal,
            request_status_fetcher=request_status_fetcher,
        )

    def close(self) -> None:
        self._ws.off_message(WSMessageType.INGEST_SOURCE_DONE, self._on_message)
        self._ws.off_message(WSMessageType.STATS_CREATE, self._on_message)
        self._ws.off_message(WSMessageType.STATS_UPDATE, self._on_message)
        self._ws.off_message(WSMessageType.ERROR, self._on_message)

    def _state(self, req_id: str) -> dict[str, Any]:
        if req_id not in self._states:
            self._states[req_id] = {
                "status": "ongoing",
                "ingested": 0,
                "skipped": 0,
                "failed": 0,
                "stats": {},
                "seen_confirm": False,
            }
        return self._states[req_id]

    @staticmethod
    def _extract_payload_obj(msg: WSMessage) -> dict[str, Any]:
        if not isinstance(msg.data, dict):
            return {}
        obj = msg.data.get("obj")
        if isinstance(obj, dict):
            return obj
        return msg.data

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _extract_ingest_counters(
        cls, payload: dict[str, Any]
    ) -> tuple[int, int, int, bool]:
        nested = payload.get("data")
        nested_data = nested if isinstance(nested, dict) else {}
        has_top = any(
            key in payload
            for key in ("records_ingested", "records_skipped", "records_failed")
        )
        has_nested = any(
            key in nested_data
            for key in ("records_ingested", "records_skipped", "records_failed")
        )
        ingested = cls._to_int(payload.get("records_ingested"))
        skipped = cls._to_int(payload.get("records_skipped"))
        failed = cls._to_int(payload.get("records_failed"))
        ingested = max(ingested, cls._to_int(nested_data.get("records_ingested")))
        skipped = max(skipped, cls._to_int(nested_data.get("records_skipped")))
        failed = max(failed, cls._to_int(nested_data.get("records_failed")))
        return ingested, skipped, failed, (has_top or has_nested)

    def _on_message(self, msg: WSMessage) -> None:
        req_id = msg.req_id
        if not req_id:
            return

        state = self._state(req_id)
        obj = self._extract_payload_obj(msg)

        if msg.type == WSMessageType.INGEST_SOURCE_DONE.value:
            done_ingested, done_skipped, done_failed, _ = self._extract_ingest_counters(
                obj
            )
            state["ingested"] += done_ingested
            state["skipped"] += done_skipped
            state["failed"] += done_failed
            if (
                self._source_done_is_terminal
                and state.get("status") not in _TERMINAL_STATUSES
            ):
                state["status"] = "done"
                state["seen_confirm"] = True

                confirm_ev = self._confirm_events.get(req_id)
                if confirm_ev is not None:
                    confirm_ev.set()

                terminal_ev = self._terminal_events.get(req_id)
                if terminal_ev is not None:
                    terminal_ev.set()
            return

        if msg.type in (
            WSMessageType.STATS_CREATE.value,
            WSMessageType.STATS_UPDATE.value,
        ):
            state["seen_confirm"] = True
            state["stats"] = obj
            status = str(obj.get("status", state["status"]))
            stats_ingested, stats_skipped, stats_failed, has_stats_counters = (
                self._extract_ingest_counters(obj)
            )
            if has_stats_counters:
                state["ingested"] = stats_ingested
                state["skipped"] = stats_skipped
                state["failed"] = stats_failed
            state["status"] = status

            confirm_ev = self._confirm_events.get(req_id)
            if confirm_ev is not None:
                confirm_ev.set()

            if status in _TERMINAL_STATUSES:
                terminal_ev = self._terminal_events.get(req_id)
                if terminal_ev is not None:
                    terminal_ev.set()
            return

        if msg.type == WSMessageType.ERROR.value:
            state["status"] = "failed"
            state["stats"] = obj
            terminal_ev = self._terminal_events.get(req_id)
            if terminal_ev is not None:
                terminal_ev.set()

    async def wait_for_confirm(self, req_id: str, timeout: float) -> bool:
        """Return True if timed out waiting for STATS_CREATE/UPDATE for req_id."""
        if not req_id:
            return False

        state = self._state(req_id)
        if state.get("seen_confirm"):
            return False

        ev = self._confirm_events.get(req_id)
        if ev is None:
            ev = asyncio.Event()
            self._confirm_events[req_id] = ev

        if timeout == 0:
            await ev.wait()
            return False

        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
            return False
        except asyncio.TimeoutError:
            return True

    async def wait_for_terminal(
        self,
        file_path: str,
        req_id: str,
        timeout: int,
    ) -> dict[str, Any]:
        if not req_id:
            return {
                "file": file_path,
                "req_id": req_id,
                "status": "unknown",
                "ingested": 0,
                "skipped": 0,
                "failed": 0,
                "result": {},
                "timed_out": False,
            }

        state = self._state(req_id)
        timed_out = False

        if state.get("status") not in _TERMINAL_STATUSES:
            ev = self._terminal_events.get(req_id)
            if ev is None:
                ev = asyncio.Event()
                self._terminal_events[req_id] = ev

            deadline = (
                None if timeout == 0 else asyncio.get_running_loop().time() + timeout
            )
            while state.get("status") not in _TERMINAL_STATUSES:
                remaining = (
                    None
                    if deadline is None
                    else max(0.0, deadline - asyncio.get_running_loop().time())
                )
                if remaining is not None and remaining == 0.0:
                    timed_out = True
                    state["status"] = "timeout"
                    break

                wait_slice = 10.0 if remaining is None else min(10.0, remaining)
                try:
                    await asyncio.wait_for(ev.wait(), timeout=wait_slice)
                    break
                except asyncio.TimeoutError:
                    # Fallback: poll current request status in case websocket terminal
                    # notifications are delayed or missed under high load.
                    if self._request_status_fetcher is not None:
                        try:
                            data = await self._request_status_fetcher(req_id)
                        except Exception:
                            data = None

                        if isinstance(data, dict):
                            polled_status = str(data.get("status", state["status"]))
                            state["stats"] = data
                            state["status"] = polled_status

                            ing = data.get("records_ingested")
                            skp = data.get("records_skipped")
                            fld = data.get("records_failed")
                            if ing is not None:
                                state["ingested"] = self._to_int(ing)
                            if skp is not None:
                                state["skipped"] = self._to_int(skp)
                            if fld is not None:
                                state["failed"] = self._to_int(fld)

                            if polled_status in _TERMINAL_STATUSES:
                                state["seen_confirm"] = True
                                confirm_ev = self._confirm_events.get(req_id)
                                if confirm_ev is not None:
                                    confirm_ev.set()
                                ev.set()
                                break

        return {
            "file": file_path,
            "req_id": req_id,
            "status": state.get("status", "unknown"),
            "ingested": state.get("ingested", 0),
            "skipped": state.get("skipped", 0),
            "failed": state.get("failed", 0),
            "result": state.get("stats", {}),
            "timed_out": timed_out,
        }


@app.command("file")
def ingest_file(
    operation_id: str,
    plugin: str,
    file_patterns: list[str] = typer.Argument(
        ...,
        help="One or more files or glob patterns (e.g. '*.evtx', '/path/to/dir/**/*.log')",
    ),
    context_name: str = typer.Option("sdk_context", "--context-name"),
    plugin_params: str | None = typer.Option(
        None, "--plugin-params", help="JSON object for plugin_params"
    ),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpIngestionFilter"
    ),
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
    wait_timeout: int = typer.Option(
        300, "--timeout", help="Seconds to wait for completion (only used with --wait)"
    ),
    show_per_file_progress: bool = typer.Option(
        True,
        "--show-per-file-progress/--no-show-per-file-progress",
        help="In --wait mode, print one line for each completed file request.",
    ),
    batch_size: int = typer.Option(
        _default_ingest_batch_size(),
        "--batch-size",
        min=1,
        help="Number of file ingestion requests to submit concurrently per batch (default: cores*2).",
    ),
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
            raise typer.BadParameter(
                "--preview and --reset-operation are mutually exclusive"
            )
        if reset_operation and create_operation_if_missing:
            raise typer.BadParameter(
                "--reset-operation and --create-operation are mutually exclusive"
            )

        async with get_client() as client:
            # Establish WS BEFORE any ingest call so ws_id is live when the
            # worker tries to publish its first STATS_CREATE event.
            await client.ensure_websocket()

            async def _fetch_request_status(req_id: str) -> dict[str, Any] | None:
                try:
                    resp = await client._request(
                        "GET", "/request_get_by_id", params={"obj_id": req_id}
                    )
                except Exception:
                    return None
                data = resp.get("data")
                return data if isinstance(data, dict) else None

            tracker = await _IngestWsTracker.create(
                client,
                source_done_is_terminal=True,
                request_status_fetcher=_fetch_request_status,
            )

            params = {
                "plugin_params": parse_json_option(
                    plugin_params, field_name="plugin-params"
                )
                or {},
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
                    params={
                        **params,
                        "original_file_path": str(Path(file_path).resolve()),
                    },
                    wait=False,  # we handle waiting ourselves below
                )
                if hasattr(result, "model_dump"):
                    submission = result.model_dump(exclude_none=True)
                else:
                    submission = {"req_id": getattr(result, "req_id", None)}
                req_id = str(submission.get("req_id") or "")
                return file_path, req_id, submission

            # Sliding window dispatcher: keep up to batch_size requests in flight.
            file_req_map: dict[str, str] = {}
            fired_meta: dict[str, dict[str, Any]] = {}
            timed_out_req_ids: set[str] = set()
            completed_by_file: dict[str, dict[str, Any]] = {}
            file_iter = iter(unique_files)
            in_flight: set[
                asyncio.Task[
                    tuple[str, str, dict[str, Any], dict[str, Any] | None, bool]
                ]
            ] = set()

            async def _submit_and_gate(
                file_path: str,
            ) -> tuple[str, str, dict[str, Any], dict[str, Any] | None, bool]:
                fpath, req_id, submission = await _fire_one(file_path)
                if wait:
                    waited = await tracker.wait_for_terminal(
                        fpath, req_id, wait_timeout
                    )
                    return fpath, req_id, submission, waited, False

                timed_out = await tracker.wait_for_confirm(
                    req_id, _WS_CONFIRM_TIMEOUT_SEC
                )
                return fpath, req_id, submission, None, timed_out

            def _schedule_next() -> bool:
                try:
                    next_file = next(file_iter)
                except StopIteration:
                    return False

                in_flight.add(asyncio.create_task(_submit_and_gate(next_file)))
                return True

            try:
                progress = None
                progress_task_id = None
                completed_count = 0
                if wait:
                    progress = Progress(
                        SpinnerColumn(),
                        TextColumn("[bold blue]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        TimeElapsedColumn(),
                        console=console,
                        transient=True,
                    )
                    progress.__enter__()
                    progress_task_id = progress.add_task(
                        "ingesting files", total=len(unique_files)
                    )

                for _ in range(min(batch_size, len(unique_files))):
                    _schedule_next()

                while in_flight:
                    done, pending = await asyncio.wait(
                        in_flight, return_when=asyncio.FIRST_COMPLETED
                    )
                    in_flight = pending

                    for done_task in done:
                        file_path, req_id, submission, waited, timed_out = (
                            await done_task
                        )
                        file_req_map[file_path] = req_id
                        if req_id:
                            fired_meta[req_id] = submission
                        if timed_out and req_id:
                            timed_out_req_ids.add(req_id)
                        if waited is not None:
                            completed_by_file[file_path] = waited
                            completed_count += 1
                            if show_per_file_progress:
                                console.print(_format_per_file_progress_line(waited))
                            if progress is not None and progress_task_id is not None:
                                progress.update(
                                    progress_task_id,
                                    advance=1,
                                    description=(
                                        f"ingesting files (done={completed_count}/{len(unique_files)}, "
                                        f"running={len(in_flight)})"
                                    ),
                                )

                        _schedule_next()
            finally:
                if wait and progress is not None:
                    progress.__exit__(None, None, None)
                tracker.close()

            if wait:
                results = [
                    completed_by_file.get(
                        fp,
                        {
                            "file": fp,
                            "req_id": file_req_map.get(fp, ""),
                            "status": "unknown",
                            "ingested": 0,
                            "skipped": 0,
                            "failed": 0,
                            "result": {},
                            "timed_out": False,
                        },
                    )
                    for fp in unique_files
                ]
                if not get_runtime_verbose():
                    results = [
                        {
                            "file": item.get("file"),
                            "req_id": item.get("req_id"),
                            "status": item.get("status", "unknown"),
                            "ingested": item.get("ingested", 0),
                            "skipped": item.get("skipped", 0),
                            "failed": item.get("failed", 0),
                        }
                        for item in results
                    ]
                else:
                    results = [
                        {
                            "file": item.get("file"),
                            "req_id": item.get("req_id"),
                            "status": item.get("status", "unknown"),
                            "ingested": item.get("ingested", 0),
                            "skipped": item.get("skipped", 0),
                            "failed": item.get("failed", 0),
                            "result": item.get("result", {}),
                            "ws_only": True,
                        }
                        for item in results
                    ]
            else:
                timed_out_set = set(timed_out_req_ids)
                if timed_out_set and not get_runtime_verbose():
                    print_warning(
                        f"{len(timed_out_set)} request(s) did not receive STATS_CREATE "
                        f"within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s — backend may still be processing: "
                        + ", ".join(sorted(timed_out_set))
                    )
                if get_runtime_verbose():
                    results = [
                        {
                            "file": fp,
                            "req_id": rid,
                            "submitted": fired_meta.get(rid, {"req_id": rid}),
                            "ws_confirmed": rid not in timed_out_set,
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
    plugin_params: str | None = typer.Option(
        None,
        "--plugin-params",
        help="JSON object for plugin_params (overrides source defaults)",
    ),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpIngestionFilter"
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
    wait_timeout: int = typer.Option(
        300, "--timeout", help="Seconds to wait for completion (only used with --wait)"
    ),
    show_per_file_progress: bool = typer.Option(
        True,
        "--show-per-file-progress/--no-show-per-file-progress",
        help="In --wait mode, print one line for each completed file request.",
    ),
    batch_size: int = typer.Option(
        _default_ingest_batch_size(),
        "--batch-size",
        min=1,
        help="Number of file ingestion requests to submit concurrently per batch (default: cores*2).",
    ),
) -> None:
    """Ingest one or more files into an existing source."""

    unique_files = _expand_file_patterns(file_patterns)
    if not unique_files:
        print_error("No files found matching the provided patterns.")
        raise typer.Exit(1)

    async def _run() -> None:
        async with get_client() as client:
            await client.ensure_websocket()

            async def _fetch_request_status(req_id: str) -> dict[str, Any] | None:
                try:
                    resp = await client._request(
                        "GET", "/request_get_by_id", params={"obj_id": req_id}
                    )
                except Exception:
                    return None
                data = resp.get("data")
                return data if isinstance(data, dict) else None

            tracker = await _IngestWsTracker.create(
                client,
                source_done_is_terminal=True,
                request_status_fetcher=_fetch_request_status,
            )

            params = {
                "plugin_params": parse_json_option(
                    plugin_params, field_name="plugin-params"
                )
                or {},
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

            file_req_map: dict[str, str] = {}
            fired_meta: dict[str, dict[str, Any]] = {}
            timed_out_req_ids: set[str] = set()
            completed_by_file: dict[str, dict[str, Any]] = {}
            file_iter = iter(unique_files)
            in_flight: set[
                asyncio.Task[
                    tuple[str, str, dict[str, Any], dict[str, Any] | None, bool]
                ]
            ] = set()

            async def _submit_and_gate(
                file_path: str,
            ) -> tuple[str, str, dict[str, Any], dict[str, Any] | None, bool]:
                fpath, req_id, submission = await _fire_one(file_path)
                if wait:
                    waited = await tracker.wait_for_terminal(
                        fpath, req_id, wait_timeout
                    )
                    return fpath, req_id, submission, waited, False

                timed_out = await tracker.wait_for_confirm(
                    req_id, _WS_CONFIRM_TIMEOUT_SEC
                )
                return fpath, req_id, submission, None, timed_out

            def _schedule_next() -> bool:
                try:
                    next_file = next(file_iter)
                except StopIteration:
                    return False

                in_flight.add(asyncio.create_task(_submit_and_gate(next_file)))
                return True

            try:
                progress = None
                progress_task_id = None
                completed_count = 0
                if wait:
                    progress = Progress(
                        SpinnerColumn(),
                        TextColumn("[bold blue]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        TimeElapsedColumn(),
                        console=console,
                        transient=True,
                    )
                    progress.__enter__()
                    progress_task_id = progress.add_task(
                        "ingesting files", total=len(unique_files)
                    )

                for _ in range(min(batch_size, len(unique_files))):
                    _schedule_next()

                while in_flight:
                    done, pending = await asyncio.wait(
                        in_flight, return_when=asyncio.FIRST_COMPLETED
                    )
                    in_flight = pending

                    for done_task in done:
                        file_path, req_id, submission, waited, timed_out = (
                            await done_task
                        )
                        file_req_map[file_path] = req_id
                        if req_id:
                            fired_meta[req_id] = submission
                        if timed_out and req_id:
                            timed_out_req_ids.add(req_id)
                        if waited is not None:
                            completed_by_file[file_path] = waited
                            completed_count += 1
                            if show_per_file_progress:
                                console.print(_format_per_file_progress_line(waited))
                            if progress is not None and progress_task_id is not None:
                                progress.update(
                                    progress_task_id,
                                    advance=1,
                                    description=(
                                        f"ingesting files (done={completed_count}/{len(unique_files)}, "
                                        f"running={len(in_flight)})"
                                    ),
                                )

                        _schedule_next()
            finally:
                if wait and progress is not None:
                    progress.__exit__(None, None, None)
                tracker.close()

            if wait:
                results = [
                    completed_by_file.get(
                        fp,
                        {
                            "file": fp,
                            "req_id": file_req_map.get(fp, ""),
                            "status": "unknown",
                            "ingested": 0,
                            "skipped": 0,
                            "failed": 0,
                            "result": {},
                            "timed_out": False,
                        },
                    )
                    for fp in unique_files
                ]
                if not get_runtime_verbose():
                    results = [
                        {
                            "file": item.get("file"),
                            "req_id": item.get("req_id"),
                            "status": item.get("status", "unknown"),
                            "ingested": item.get("ingested", 0),
                            "skipped": item.get("skipped", 0),
                            "failed": item.get("failed", 0),
                        }
                        for item in results
                    ]
                else:
                    results = [
                        {
                            "file": item.get("file"),
                            "req_id": item.get("req_id"),
                            "status": item.get("status", "unknown"),
                            "ingested": item.get("ingested", 0),
                            "skipped": item.get("skipped", 0),
                            "failed": item.get("failed", 0),
                            "result": item.get("result", {}),
                            "ws_only": True,
                        }
                        for item in results
                    ]
            else:
                timed_out_set = set(timed_out_req_ids)
                if timed_out_set and not get_runtime_verbose():
                    print_warning(
                        f"{len(timed_out_set)} request(s) did not receive STATS_CREATE "
                        f"within {_WS_CONFIRM_TIMEOUT_SEC:.0f}s - backend may still be processing: "
                        + ", ".join(sorted(timed_out_set))
                    )
                if get_runtime_verbose():
                    results = [
                        {
                            "file": fp,
                            "req_id": rid,
                            "submitted": fired_meta.get(rid, {"req_id": rid}),
                            "ws_confirmed": rid not in timed_out_set,
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
    zip_file: str = typer.Argument(
        ...,
        help="Path to a ZIP file which must contain a `metadata.json` in the root, describing the content as specified in gulp's `ingest_zip` docs.",
    ),
    context_name: str = typer.Option("sdk_context", "--context-name"),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpIngestionFilter"
    ),
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
    wait_timeout: int = typer.Option(
        300, "--timeout", help="Seconds to wait for completion (only used with --wait)"
    ),
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
                print_result(
                    waited[0]
                    if waited
                    else {"file": zip_file, "req_id": req_id, "status": "unknown"}
                )
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
                    print_result(
                        {"file": zip_file, "req_id": req_id, "status": "pending"}
                    )

    asyncio.run(_run())


@app.command("zip-create")
def ingest_zip_create(
    output_zip: str = typer.Argument(
        ...,
        help="Path to the ZIP file to create (supports $VARS and ~)",
    ),
    path_patterns: list[str] = typer.Argument(
        None,
        help="One or more files, directories, or glob patterns to archive (supports $VARS and ~)",
    ),
    paths_file: str | None = typer.Option(
        None,
        "--paths-file",
        help="Text file with one file, directory, or glob pattern per line (supports $VARS and ~ per line)",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite the ZIP file if it already exists",
    ),
) -> None:
    """Create a ZIP archive from files, directories, or glob patterns."""

    output_path = _resolve_path(output_zip)
    source_paths = _expand_zip_source_patterns(path_patterns or [], paths_file)

    if output_path.exists() and not overwrite:
        raise typer.BadParameter(
            f"Output ZIP already exists: {output_path}. Use --overwrite to replace it"
        )

    archived_count, archived_entries = _build_zip_from_sources(
        output_path, source_paths
    )
    print_result(
        {
            "zip_file": str(output_path),
            "sources": [str(path) for path, _ in source_paths],
            "files_archived": archived_count,
            "entries": archived_entries,
        },
        formatter=lambda data: console.print(
            f"Created ZIP {data['zip_file']} from {len(data['sources'])} source"
            f"{'s' if len(data['sources']) != 1 else ''} with {data['files_archived']} file(s)."
        ),
    )


@app.command("raw")
def ingest_raw(
    operation_id: str,
    data: str | None = typer.Option(
        None, "--data", help="Raw payload text (JSON recommended)"
    ),
    data_file: str | None = typer.Option(
        None, "--data-file", help="Path to file containing raw payload"
    ),
    plugin: str = typer.Option(
        "raw", "--plugin", help="Plugin used to process the raw payload"
    ),
    plugin_params: str | None = typer.Option(
        None, "--plugin-params", help="JSON object for plugin_params"
    ),
    flt: str | None = typer.Option(
        None, "--flt", help="JSON object for GulpIngestionFilter"
    ),
    req_id: str | None = typer.Option(
        None, "--req-id", help="Optional request ID for chunked ingestion"
    ),
    last: bool = typer.Option(
        False, "--last", help="Mark this payload as the last raw chunk"
    ),
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
    wait_timeout: int = typer.Option(
        300, "--timeout", help="Seconds to wait for completion (only used with --wait)"
    ),
) -> None:
    """Ingest raw payload into an operation."""

    if (data is None and data_file is None) or (
        data is not None and data_file is not None
    ):
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
                payload_data: dict[str, Any] | str | bytes = Path(
                    data_file
                ).read_bytes()
            else:
                assert data is not None
                try:
                    payload_data = json.loads(data)
                except json.JSONDecodeError:
                    payload_data = data

            params: dict[str, Any] = {
                "plugin_params": parse_json_option(
                    plugin_params, field_name="plugin-params"
                )
                or {},
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
                    else {
                        "file": request_label,
                        "req_id": resolved_req_id,
                        "status": "unknown",
                    }
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
                        {
                            "file": request_label,
                            "req_id": resolved_req_id,
                            "status": "pending",
                        }
                    )

    asyncio.run(_run())
